"""Monitor groups.

Monitor groups are used to group monitors into.. groups. They can be used
as a cosmetic feature, but also to connect multiple monitors to contacts
without setting the contact(s) for each monitor.
"""

from typing import Optional, Dict, Any, Iterable
from irisett.sql import DBConnection, Cursor
from irisett import (
    errors,
    object_models,
)
from irisett.object_exists import (
    monitor_group_exists,
    contact_exists,
    active_monitor_exists,
    contact_group_exists,
)


async def create_monitor_group(dbcon: DBConnection, parent_id: Optional[int], name: str):
    """Add a monitor group to the database."""
    if not name:
        raise errors.InvalidArguments('missing monitor group name')
    if parent_id:
        if not await monitor_group_exists(dbcon, parent_id):
            raise errors.InvalidArguments('parent monitor group does not exist')
        q = """insert into monitor_groups (parent_id, name) values (%s, %s)"""
        q_args = (parent_id, name)  # type: Any
    else:
        q = """insert into monitor_groups (name) values (%s)"""
        q_args = (name,)
    group_id = await dbcon.operation(q, q_args)
    return group_id


async def update_monitor_group(dbcon: DBConnection, monitor_group_id: int, data: Dict[str, Any]):
    """Update a monitor group in the database.

    Data is a dict with parent_id/name values that will be updated.
    """
    queries = []
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
        queries.append(q, q_args)
    await dbcon.multi_operation(queries)


async def delete_monitor_group(dbcon: DBConnection, monitor_group_id: int) -> None:
    """Remove a monitor_group from the database."""

    queries = [
        ("""delete from monitor_groups where id=%s""", (monitor_group_id,)),
        ("""delete from monitor_group_active_monitors where monitor_group_id=%s""", (monitor_group_id,)),
        ("""delete from object_metadata where object_type="monitor_group" and object_id=%s""", (monitor_group_id,)),
    ]
    await dbcon.multi_operation(queries)


async def add_active_monitor_to_monitor_group(dbcon: DBConnection, monitor_group_id: int, monitor_id: int) -> None:
    """Connect a monitor_group and an active monitor."""
    if not await active_monitor_exists(dbcon, monitor_id):
        raise errors.InvalidArguments('monitor does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """replace into monitor_group_active_monitors (monitor_group_id, active_monitor_id) values (%s, %s)"""
    q_args = (monitor_group_id, monitor_id)
    await dbcon.operation(q, q_args)


async def delete_active_monitor_from_monitor_group(dbcon: DBConnection, monitor_group_id: int, monitor_id: int) -> None:
    """Remove an active monitor from a monitor group."""
    if not await active_monitor_exists(dbcon, monitor_id):
        raise errors.InvalidArguments('monitor does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """delete from monitor_group_active_monitors where monitor_group_id=%s and active_monitor_id=%s"""
    q_args = (monitor_group_id, monitor_id)
    await dbcon.operation(q, q_args)


async def add_contact_to_monitor_group(dbcon: DBConnection, monitor_group_id: int, contact_id: int) -> None:
    """Connect a monitor_group and a contact."""
    if not await contact_exists(dbcon, contact_id):
        raise errors.InvalidArguments('contact does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """replace into monitor_group_contacts (monitor_group_id, contact_id) values (%s, %s)"""
    q_args = (monitor_group_id, contact_id)
    await dbcon.operation(q, q_args)


async def delete_contact_from_monitor_group(dbcon: DBConnection, monitor_group_id: int, contact_id: int) -> None:
    """Remove a contact from a monitor group."""
    if not await contact_exists(dbcon, contact_id):
        raise errors.InvalidArguments('contact does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """delete from monitor_group_contacts where monitor_group_id=%s and contact_id=%s"""
    q_args = (monitor_group_id, contact_id)
    await dbcon.operation(q, q_args)


async def add_contact_group_to_monitor_group(dbcon: DBConnection, monitor_group_id: int, contact_group_id: int) -> None:
    """Connect a monitor_group and a contact group."""
    if not await contact_group_exists(dbcon, contact_group_id):
        raise errors.InvalidArguments('contact group does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """replace into monitor_group_contact_groups (monitor_group_id, contact_group_id) values (%s, %s)"""
    q_args = (monitor_group_id, contact_group_id)
    await dbcon.operation(q, q_args)


async def delete_contact_group_from_monitor_group(
        dbcon: DBConnection, monitor_group_id: int, contact_group_id: int) -> None:
    """Remove a contact group from a monitor group."""
    if not await contact_group_exists(dbcon, contact_group_id):
        raise errors.InvalidArguments('contact does not exist')
    if not await monitor_group_exists(dbcon, monitor_group_id):
        raise errors.InvalidArguments('monitor_group does not exist')
    q = """delete from monitor_group_contact_groups where monitor_group_id=%s and contact_group_id=%s"""
    q_args = (monitor_group_id, contact_group_id)
    await dbcon.operation(q, q_args)


async def get_all_monitor_groups(dbcon: DBConnection) -> Iterable[object_models.MonitorGroup]:
    q = """select id, parent_id, name from monitor_groups"""
    ret = [object_models.MonitorGroup(*row) for row in await dbcon.fetch_all(q)]
    return ret


async def get_monitor_group(dbcon: DBConnection, id: int) -> Any:  # Use any because optional returns suck.
    q = """select id, parent_id, name from monitor_groups where id=%s"""
    row = await dbcon.fetch_row(q, (id,))
    ret = None
    if row:
        ret = object_models.MonitorGroup(*row)
    return ret


async def get_contacts_for_monitor_group(dbcon: DBConnection, id: int) -> Iterable[object_models.Contact]:
    q = """select contacts.id, contacts.name, contacts.email, contacts.phone, contacts.active
            from contacts, monitor_group_contacts
            where contacts.id=monitor_group_contacts.contact_id
            and monitor_group_contacts.monitor_group_id=%s"""
    return [object_models.Contact(*row) for row in await dbcon.fetch_all(q, (id,))]


async def get_contact_groups_for_monitor_group(dbcon: DBConnection, id: int) -> Iterable[object_models.ContactGroup]:
    q = """select cg.id, cg.name, cg.active
            from contact_groups as cg, monitor_group_contact_groups
            where cg.id=monitor_group_contact_groups.contact_group_id
            and monitor_group_contact_groups.monitor_group_id=%s"""
    return [object_models.ContactGroup(*row) for row in await dbcon.fetch_all(q, (id,))]


async def get_active_monitors_for_monitor_group(dbcon: DBConnection, id: int) -> Iterable[object_models.ActiveMonitor]:
    q = """select mon.id, mon.def_id, mon.state, mon.state_ts, mon.msg, mon.alert_id, mon.deleted,
            mon.checks_enabled, mon.alerts_enabled
            from active_monitors as mon, monitor_group_active_monitors
            where mon.id=monitor_group_active_monitors.active_monitor_id
            and monitor_group_active_monitors.monitor_group_id=%s"""
    return [object_models.ActiveMonitor(*row) for row in await dbcon.fetch_all(q, (id,))]


async def get_monitor_groups_for_metadata(
        dbcon: DBConnection, meta_key: str, meta_value: str) -> Iterable[object_models.MonitorGroup]:
    q = """select mg.id, mg.parent_id, mg.name
        from monitor_groups as mg, object_metadata as meta
        where meta.key=%s and meta.value=%s and meta.object_type="monitor_group" and meta.object_id=mg.id"""
    q_args = (meta_key, meta_value)
    return [object_models.MonitorGroup(*row) for row in await dbcon.fetch_all(q, q_args)]


async def get_active_monitor_metadata_for_monitor_group(
        dbcon: DBConnection, id: int) -> Iterable[object_models.ObjectMetadata]:
    q = '''select metadata.object_type, metadata.object_id, metadata.key, metadata.value
            from monitor_group_active_monitors, object_metadata as metadata
            where monitor_group_active_monitors.monitor_group_id=%s and
            metadata.object_id=monitor_group_active_monitors.active_monitor_id
            and metadata.object_type="active_monitor"'''
    return [object_models.ObjectMetadata(*row) for row in await dbcon.fetch_all(q, (id,))]
