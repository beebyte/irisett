"""SQL management.

Provides a connection to a database and convenience functions for accessing
it.
"""

from typing import Optional, Iterable, Any, List, Callable
import asyncio
import aiosqlite
import os
import os.path
import sqlite3

from irisett import (
    log,
    stats,
)

from irisett.sql import sqlite_data as sql_data
import irisett.sql.base


class DBConnection(irisett.sql.base.DBConnection):
    """A sqlite connection manager."""

    def __init__(self, filename: str, loop: asyncio.AbstractEventLoop = None) -> None:
        self.filename = filename
        self.loop = loop or asyncio.get_event_loop()
        stats.set("queries", 0, "SQL")
        stats.set("transactions", 0, "SQL")
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))

    async def initialize(
        self, *, only_init_tables: bool = False, reset_db: bool = False
    ):
        """Initialize the DBConnection.

        Creates a connection pool using aiosqlite and initializes the database
        if necessary.
        """
        if reset_db:
            if os.path.isfile(self.filename):
                os.unlink(self.filename)
        db_exists = False
        if os.path.isfile(self.filename):
            db_exists = True
        if not db_exists:
            await self._init_db(only_init_tables)
        await self._upgrade_db()
        log.msg("Database initialized")

    async def close(self) -> None:
        pass

    def prep_query(self, query: str) -> str:
        """Preps query to work with multiple sql module param styles."""
        return query.replace("%s", "?")

    async def _init_db(self, only_init_tables: bool) -> None:
        log.msg("Initializing empty database")
        commands = sql_data.SQL_ALL
        if only_init_tables:
            commands = sql_data.SQL_BARE
        await self.multi_operation(commands)

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
        query = self.prep_query(query)
        async with aiosqlite.connect(
            self.filename, detect_types=sqlite3.PARSE_DECLTYPES
        ) as db:
            async with db.execute(query, args) as cur:
                ret = await cur.fetchall()
        return ret

    async def fetch_row(self, query: str, args: Optional[Iterable] = None) -> List:
        """Run a query and fetch a single returned row."""
        stats.inc("queries", "SQL")
        query = self.prep_query(query)
        async with aiosqlite.connect(
            self.filename, detect_types=sqlite3.PARSE_DECLTYPES
        ) as db:
            async with db.execute(query, args) as cur:
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
        query = self.prep_query(query)
        async with aiosqlite.connect(
            self.filename, detect_types=sqlite3.PARSE_DECLTYPES
        ) as db:
            cur = await db.execute(query, args)
            ret = cur.lastrowid
            await cur.close()
            await db.commit()
        return ret

    async def multi_operation(self, queries) -> Any:
        """Run multiple sql operations as a transaction."""
        async with aiosqlite.connect(
            self.filename, detect_types=sqlite3.PARSE_DECLTYPES
        ) as db:
            async with db.cursor() as cur:
                for _query in queries:
                    if type(_query) == str:
                        query = _query
                        args = []
                    else:
                        query = _query[0]
                        args = _query[1]
                    stats.inc("queries", "SQL")
                    await cur.execute(self.prep_query(query), args)
                await db.commit()

    async def transact(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Create a db cursor and hand it to a callback.

        This can be used to simulate transactions.
        commit will be called when the callback returns. If an exception is
        raised in the callback a rollback is performed.
        """
        stats.inc("transactions", "SQL")
        async with aiosqlite.connect(
            self.filename, detect_types=sqlite3.PARSE_DECLTYPES
        ) as db:
            async with db.cursor() as cur:
                try:
                    ret = await func(cur, *args, **kwargs)
                    await cur.close()
                except:
                    await db.rollback()
                    raise
                else:
                    await db.commit()
        return ret
