"""Object bindata management.

Bindata is binary metadata(-like) storage for arbitrary objects.
The purpose is similar to the metadata storage except that it focuses on
working with individual larger key/value pairs rather than metadata dicts.
"""

from irisett.sql import DBConnection


async def get_bindata(dbcon: DBConnection, object_type: str, object_id: int, key: str) -> bytes:
    """Return a a bindata value."""
    q = """select value from object_bindata where object_type=%s and object_id=%s and `key`=%s"""
    q_args = (object_type, object_id, key)
    ret = await dbcon.fetch_single(q, q_args)
    return ret


async def set_bindata(dbcon: DBConnection, object_type: str, object_id: int, key: str, value: bytes):
    """Set a bindata value for an object (key)."""
    q = """replace into object_bindata (object_type, object_id, `key`, value) values (%s, %s, %s, %s)"""
    q_args = (object_type, object_id, key, value)
    await dbcon.operation(q, q_args)


async def delete_bindata(dbcon: DBConnection, object_type: str, object_id: int, key: str):
    """Delete bindata for an object."""
    q = """delete from object_bindata where object_type=%s and object_id=%s and `key`=%s"""
    q_args = (object_type, object_id, key)
    await dbcon.operation(q, q_args)
