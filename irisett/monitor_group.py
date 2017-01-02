"""Monitor groups.

Monitor groups are used to group monitors into.. groups. They can be used
as a cosmetic feature, but also to connect multiple monitors to contacts
without setting the contact(s) for each monitor.
"""

from typing import Optional, Dict, Any
from irisett.sql import DBConnection
from irisett import errors
from irisett.object_exists import (
    monitor_group_exists,
    contact_exists,
    active_monitor_exists,
    contact_group_exists,
)

async def create_monitor_group(dbcon: DBConnection, parent_id: Optional[int], name: str):
    """Add a monitor group to the database."""
    if parent_id:
        if not await monitor_group_exists(dbcon, parent_id):
            raise errors.InvalidArguments('parent monitor group does not exist')
        q = """insert into monitor_groups (parent_id, name) values (%s, %s)"""
        q_args = (parent_id, name)
    else:
        q = """insert into monitor_groups (name) values (%s)"""
        q_args = (name,)
    group_id = await dbcon.operation(q, q_args)
    return group_id


async def update_monitor_group(dbcon: DBConnection, monitor_group_id: int, data: Dict[str, Any]):
    """Update a monitor group in the database.

    Data is a dict with parent_id/name values that will be updated.
    """
    async def _run(cur):
        for key, value in data.items():
            if key not in ['parent_id', 'name']:
                raise errors.IrisettError('invalid monitor_group key %s' % key)
            if key == 'parent_id' and value:
                if monitor_group_id == int(value):
                    raise errors.InvalidArguments('monitor group can\'t be its own parent')
                if not await monitor_group_exists(dbcon, value):
                    raise errors.InvalidArguments('parent monitor group does not exist')
            q = """update monitor_groups set %s=%%s where id=%%s""" % key
            q_args = (value, monitor_group_id)
            await cur.execute(q, q_args)

    await dbcon.transact(_run)


async def delete_monitor_group(dbcon: DBConnection, monitor_group_id: int):
    """Remove a monitor_group from the database."""

    async def _run(cur):
        q = """delete from monitor_groups where id=%s"""
        await cur.execute(q, (monitor_group_id,))
        q = """delete from monitor_group_active_monitors where monitor_group_id=%s"""
        await cur.execute(q, (monitor_group_id,))
        q = """delete from object_metadata where object_type="monitor_group" and object_id=%s"""
        await cur.execute(q, (monitor_group_id,))

    await dbcon.transact(_run)


async def add_active_monitor_to_monitor_group(dbcon: DBConnection, monitor_group_id: int, monitor_id: int):
    """Connect a monitor_group and an active monitor."""
    if not await active_monitor_exists(dbcon, monitor_id):
        raise errors.InvalidArguments('monitor does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """replace into monitor_group_active_monitors (monitor_group_id, active_monitor_id) values (%s, %s)"""
    q_args = (monitor_group_id, monitor_id)
    await dbcon.operation(q, q_args)


async def delete_active_monitor_from_monitor_group(dbcon: DBConnection, monitor_group_id: int, monitor_id: int):
    """Remove an active monitor from a monitor group."""
    if not await active_monitor_exists(dbcon, monitor_id):
        raise errors.InvalidArguments('monitor does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """delete from monitor_group_active_monitors where monitor_group_id=%s and active_monitor_id=%s"""
    q_args = (monitor_group_id, monitor_id)
    await dbcon.operation(q, q_args)


async def add_contact_to_monitor_group(dbcon: DBConnection, monitor_group_id: int, contact_id: int):
    """Connect a monitor_group and a contact."""
    if not await contact_exists(dbcon, contact_id):
        raise errors.InvalidArguments('contact does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """replace into monitor_group_contacts (monitor_group_id, contact_id) values (%s, %s)"""
    q_args = (monitor_group_id, contact_id)
    await dbcon.operation(q, q_args)


async def delete_contact_from_monitor_group(dbcon: DBConnection, monitor_group_id: int, contact_id: int):
    """Remove a contact from a monitor group."""
    if not await contact_exists(dbcon, contact_id):
        raise errors.InvalidArguments('contact does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """delete from monitor_group_contacts where monitor_group_id=%s and contact_id=%s"""
    q_args = (monitor_group_id, contact_id)
    await dbcon.operation(q, q_args)


async def add_contact_group_to_monitor_group(dbcon: DBConnection, monitor_group_id: int, contact_group_id: int):
    """Connect a monitor_group and a contact group."""
    if not await contact_group_exists(dbcon, contact_group_id):
        raise errors.InvalidArguments('contact group does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """replace into monitor_group_contact_groups (monitor_group_id, contact_group_id) values (%s, %s)"""
    q_args = (monitor_group_id, contact_group_id)
    await dbcon.operation(q, q_args)


async def delete_contact_group_from_monitor_group(dbcon: DBConnection, monitor_group_id: int, contact_group_id: int):
    """Remove a contact group from a monitor group."""
    if not await contact_group_exists(dbcon, contact_group_id):
        raise errors.InvalidArguments('contact does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """delete from monitor_group_contact_groups where monitor_group_id=%s and contact_group_id=%s"""
    q_args = (monitor_group_id, contact_group_id)
    await dbcon.operation(q, q_args)
