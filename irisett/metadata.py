"""Object metadata management.

Metadata can be applied to any object type/id pair.
Metadata is managed using metadicts, ie. key/value pairs
of (short) data that are attached to an object.
"""

from typing import Dict, Iterable, Optional
from irisett.sql import DBConnection


async def get_metadata(dbcon: DBConnection, object_type: str, object_id: int) -> Dict[str, str]:
    """Return a dict of metadata for an object."""
    q = """select `key`, value from object_metadata where object_type=%s and object_id=%s"""
    q_args = (object_type, object_id)
    rows = await dbcon.fetch_all(q, q_args)
    metadict = {}
    for key, value in rows:
        metadict[key] = value
    return metadict


async def add_metadata(dbcon: DBConnection, object_type: str, object_id: int, metadict: Dict[str, str]):
    """Add metadata to an object.

    Metadict is a dictionary of key value pairs to add.
    """

    async def _run(cur):
        q = """insert into object_metadata (object_type, object_id, `key`, value) values (%s, %s, %s, %s)"""
        for key, value in metadict.items():
            q_args = (object_type, object_id, str(key), str(value))
            await cur.execute(q, q_args)

    await dbcon.transact(_run)


async def update_metadata(dbcon: DBConnection, object_type: str, object_id: int, metadict: Dict[str, str]):
    """Update metadata values for an object.

    Metadict is a dictionary of key value pairs to add.
    """

    async def _run(cur):
        for key, value in metadict.items():
            if value in [False, None]:
                q = """delete from object_metadata where object_type=%s and object_id=%s and `key`=%s"""
                q_args = (object_type, object_id, str(key))
            else:
                q = """replace into object_metadata (object_type, object_id, `key`, value) values (%s, %s, %s, %s)"""
                q_args = (object_type, object_id, str(key), str(value))
            await cur.execute(q, q_args)

    await dbcon.transact(_run)


async def delete_metadata(dbcon: DBConnection, object_type: str, object_id: int,
                          keys: Optional[Iterable[str]] = None):
    """Delete metadata for an object.

    If keys is given, only delete the specified keys, otherwise delete all
    metadata for the object.
    """

    async def _run(cur):
        if keys:
            # noinspection PyTypeChecker
            for key in keys:
                q = """delete from object_metadata where object_type=%s and object_id=%s and `key`=%s"""
                q_args = (object_type, object_id, key)
                await cur.execute(q, q_args)
        else:
            q = """delete from object_metadata where object_type=%s and object_id=%s"""
            q_args = (object_type, object_id)
            await cur.execute(q, q_args)

    await dbcon.transact(_run)
