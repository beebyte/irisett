"""Object metadata management.

Metadata can be applied to any object type/id pair.
Metadata is managed using metadicts, ie. key/value pairs
of (short) data that are attached to an object.
"""

from typing import Dict, Iterable, Optional, Tuple
from irisett.sql import DBConnection, Cursor
from irisett import object_models


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

    async def _run(cur: Cursor) -> None:
        q = """insert into object_metadata (object_type, object_id, `key`, value) values (%s, %s, %s, %s)"""
        for key, value in metadict.items():
            q_args = (object_type, object_id, str(key), str(value))
            await cur.execute(q, q_args)

    await dbcon.transact(_run)


async def update_metadata(dbcon: DBConnection, object_type: str, object_id: int, metadict: Dict[str, str]):
    """Update metadata values for an object.

    Metadict is a dictionary of key value pairs to add.
    """

    async def _run(cur: Cursor) -> None:
        for key, value in metadict.items():
            if value in [False, None]:
                q = """delete from object_metadata where object_type=%s and object_id=%s and `key`=%s"""
                q_args = (object_type, object_id, str(key))  # type: Tuple
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

    async def _run(cur: Cursor) -> None:
        if keys:
            # noinspection PyTypeChecker
            for key in keys:
                q = """delete from object_metadata where object_type=%s and object_id=%s and `key`=%s"""
                q_args = (object_type, object_id, key)  # type: Tuple
                await cur.execute(q, q_args)
        else:
            q = """delete from object_metadata where object_type=%s and object_id=%s"""
            q_args = (object_type, object_id)
            await cur.execute(q, q_args)

    await dbcon.transact(_run)


async def get_metadata_for_object(
        dbcon: DBConnection, object_type: str, object_id: int) -> Iterable[object_models.ObjectMetadata]:
    """Get ObjectMetadata for a single object (type, id)

    Ie. contact, [ID]
    """
    q = """select metadata.object_type, metadata.object_id, metadata.key, metadata.value
        from object_metadata as metadata
        where metadata.object_type=%s and metadata.object_id=%s"""
    q_args = (object_type, object_id)
    return [object_models.ObjectMetadata(*row) for row in await dbcon.fetch_all(q, q_args)]


async def get_metadata_for_object_type(
        dbcon: DBConnection, object_type: str) -> Iterable[object_models.ObjectMetadata]:
    """Get ObjectMetadata for all objects of object_type

    Ie. contact
    """
    q = '''select metadata.object_type, metadata.object_id, metadata.key, metadata.value
        from object_metadata as metadata
        where metadata.object_type=%s'''
    return [object_models.ObjectMetadata(*row) for row in await dbcon.fetch_all(q, (object_type,))]


async def get_metadata_for_object_metadata(
        dbcon: DBConnection, metadata_key: str, metadata_value: str,
        object_type: str, object_table: str) -> Iterable[object_models.ObjectMetadata]:
    """Get ObjectMetadata for all object matching a (key, value, object_type) set.

    Ie. Get all metadata for contacts (object_type) matching the
    (key: value): device: 123.
    """
    q = '''select m2.object_type, m2.object_id, m2.key, m2.value
                from object_metadata as m1
                left join %s on %s.id=m1.object_id
                left join object_metadata as m2 on m2.object_id=%s.id
                where m1.key=%%s and m1.value=%%s and m2.object_type=%%s''' % (object_table, object_table, object_table)
    q_args = (metadata_key, metadata_value, object_type)
    return [object_models.ObjectMetadata(*row) for row in await dbcon.fetch_all(q, q_args)]
