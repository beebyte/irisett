"""SQL management.

Provides a connection to a database and convenience functions for accessing
it.
"""

from typing import Optional, Iterable, Any, List, Callable
import asyncio
import aiomysql

from irisett import (
    log,
    stats,
)

from irisett.sql import mysql_data as sql_data
import irisett.sql.base


class DBConnection(irisett.sql.base.DBConnection):
    """A sql connection manager."""

    def __init__(
        self,
        host: str,
        user: str,
        passwd: str,
        dbname: str,
        loop: asyncio.AbstractEventLoop = None,
    ) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.host = host
        self.user = user
        self.passwd = passwd
        self.dbname = dbname
        self.pool = None  # type: Any
        stats.set("queries", 0, "SQL")
        stats.set("transactions", 0, "SQL")

    async def initialize(
        self, *, only_init_tables: bool = False, reset_db: bool = False
    ):
        """Initialize the DBConnection.

        Creates a connection pool using aiomysql and initializes the database
        if necessary.
        """
        self.pool = await aiomysql.create_pool(
            host=self.host, user=self.user, password=self.passwd, loop=self.loop
        )
        if reset_db:
            await self._drop_db()
        db_exists = await self._check_db_exists()
        if not db_exists:
            await self._create_db()
            db_initialized = False
        else:
            db_initialized = await self._check_db_initialized()
        # We close the pool and create a new one because aiomysql doesn't
        # provide an easy way to change the active database for an entire
        # pool, just individual connections.
        self.pool.terminate()
        self.pool = await aiomysql.create_pool(
            host=self.host,
            user=self.user,
            password=self.passwd,
            db=self.dbname,
            loop=self.loop,
        )
        if not db_initialized:
            await self._init_db(only_init_tables)
        await self._upgrade_db()
        log.msg("Database initialized")

    async def close(self) -> None:
        self.pool.terminate()
        await self.pool.wait_closed()

    def prep_query(self, query: str) -> str:
        """Preps query to work with multiple sql module param styles."""
        return query

    async def _drop_db(self) -> None:
        log.msg("Removing database %s" % self.dbname)
        q = """DROP DATABASE %s""" % self.dbname
        await self.operation(q)

    async def _create_db(self) -> None:
        # Yes yes, this risks sql injection, but the dbname is from the
        # irisett config file, so if you want to sql inject yourself,
        # go ahead.
        log.msg("Creating missing database %s" % self.dbname)
        q = """CREATE DATABASE %s""" % self.dbname
        await self.operation(q)

    async def _init_db(self, only_init_tables: bool) -> None:
        log.msg("Initializing empty database")
        commands = sql_data.SQL_ALL
        if only_init_tables:
            commands = sql_data.SQL_BARE
        for command in commands:
            await self.operation(command)

    async def _check_db_exists(self) -> bool:
        """Check if the database exists."""
        q = """SELECT SCHEMA_NAME
            FROM INFORMATION_SCHEMA.SCHEMATA
            WHERE SCHEMA_NAME = %s"""
        res = await self.fetch_single(q, (self.dbname,))
        if not res:
            return False
        return True

    async def _check_db_initialized(self) -> bool:
        """Check if the database has been initialized."""
        q = """SELECT count(*)
        FROM information_schema.TABLES
        WHERE (TABLE_SCHEMA = %s) AND (TABLE_NAME = %s)"""
        res = await self.fetch_single(q, (self.dbname, "version"))
        if res == 0:
            return False
        return True

    async def _upgrade_db(self) -> None:
        """Upgrade to a newer database version if required.

        Loops through the commands in sql_data.SQL_UPGRADES and runs them.
        """
        cur_version = await self._get_db_version()
        for n in range(cur_version + 1, sql_data.CUR_VERSION + 1):
            log.msg("Upgrading database to version %d" % n)
            if n in sql_data.SQL_UPGRADES:
                for command in sql_data.SQL_UPGRADES[n]:
                    await self.operation(command)
        if cur_version != sql_data.CUR_VERSION:
            await self._set_db_version(sql_data.CUR_VERSION)

    async def _get_db_version(self) -> int:
        q = """select version from version limit 1"""
        str_version = await self.fetch_single(q)
        version = int(str_version)
        return version

    async def _set_db_version(self, version: int):
        q = """update version set version=%s"""
        q_args = (version,)
        await self.operation(q, q_args)

    async def fetch_all(self, query: str, args: Optional[Iterable] = None) -> List:
        """Run a query and fetch all returned rows."""
        stats.inc("queries", "SQL")
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args)
                ret = await cur.fetchall()
        return ret

    async def fetch_row(self, query: str, args: Optional[Iterable] = None) -> List:
        """Run a query and fetch a single returned row."""
        stats.inc("queries", "SQL")
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args)
                ret = await cur.fetchone()
        return ret

    async def fetch_single(self, query: str, args: Optional[Iterable] = None) -> Any:
        """Run a query and fetch a single returned value from a single row."""
        res = await self.fetch_row(query, args)
        ret = None
        if res and len(res) == 1:
            ret = res[0]
        return ret

    async def count_rows(self, query: str, args: Optional[Iterable] = None) -> float:
        """Count the number of returned rows for a query.

        This is not equivalent to select count(*), this will actually fetch
        all the rows then count them and is thus much slower.
        """
        res = await self.fetch_all(query, args)
        return len(res)

    async def operation(self, query: str, args: Optional[Iterable] = None) -> Any:
        """Run a sql operation (query).

        Ie. insert, update etc. not select.
        Returns the row id of the created row if any.
        """
        stats.inc("queries", "SQL")
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args)
                ret = cur.lastrowid
                await conn.commit()
        return ret

    async def multi_operation(self, queries) -> Any:
        """Run multiple sql operations as a transaction."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                for _query in queries:
                    if type(_query) == str:
                        query = _query
                        args = []
                    else:
                        query = _query[0]
                        args = _query[1]
                    stats.inc("queries", "SQL")
                    await cur.execute(query, args)
                await conn.commit()

    async def transact(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Create a db cursor and hand it to a callback.

        This can be used to simulate transactions.
        commit will be called when the callback returns. If an exception is
        raised in the callback a rollback is performed.
        """
        stats.inc("transactions", "SQL")
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    ret = await func(cur, *args, **kwargs)
                except:
                    await conn.rollback()
                    raise
                else:
                    await conn.commit()
        return ret
