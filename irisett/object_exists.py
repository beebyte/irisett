"""Check if a number of different objects exist.

This whole module is a big workaround to avoid circular imports.
This should probaby be cleaned up in some way.
"""

from typing import Optional, Iterable
from irisett.sql import DBConnection


async def _object_exists(dbcon: DBConnection, query: str, query_args: Optional[Iterable]) -> bool:
    res = await dbcon.fetch_single(query, query_args)
    if res == 0:
        return False
    return True


async def monitor_group_exists(dbcon: DBConnection, monitor_group_id: int) -> bool:
    """Check if a monitor group id exists."""
    q = """select count(id) from monitor_groups where id=%s"""
    return await _object_exists(dbcon, q, (monitor_group_id,))


async def contact_exists(dbcon: DBConnection, contact_id: int) -> bool:
    """Check if a contact id exists."""
    q = """select count(id) from contacts where id=%s"""
    return await _object_exists(dbcon, q, (contact_id,))


async def active_monitor_exists(dbcon: DBConnection, active_monitor_id: int) -> bool:
    """Check if a contact id exists."""
    q = """select count(id) from active_monitors where id=%s"""
    return await _object_exists(dbcon, q, (active_monitor_id,))


async def contact_group_exists(dbcon: DBConnection, contact_group_id: int) -> bool:
    """Check if a contact group id exists."""
    q = """select count(id) from contact_groups where id=%s"""
    return await _object_exists(dbcon, q, (contact_group_id,))
