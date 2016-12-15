"""Basic contact management functions.

Contacts are linked to monitors and are used to determine where to send
alerts for monitors.

Contacts are basic name/email/phone sets.

Contacts are only stored in the database and not in memory, they are loaded
from the database each time an alert is sent.
"""

from typing import Dict, Set, Iterable, Optional
from irisett import errors
from irisett.sql import DBConnection

if False:  # mypy circular import workaround.
    from irisett.monitor.active import ActiveMonitor


async def create_contact(dbcon: DBConnection, name: Optional[str], email: Optional[str],
                         phone: Optional[str], active: bool) -> str:
    """Add a contact to the database."""
    q = """insert into contacts (name, email, phone, active) values (%s, %s, %s, %s)"""
    q_args = (name, email, phone, active)
    contact_id = await dbcon.operation(q, q_args)
    return contact_id


async def update_contact(dbcon: DBConnection, contact_id: int, data: Dict[str, str]):
    """Update a contacts information in the database.

    Data is a dict with name/email/phone/active values that
    will be updated.
    """

    async def _run(cur):
        for key, value in data.items():
            if key not in ['name', 'email', 'phone', 'active']:
                raise errors.IrisettError('invalid contact key %s' % key)
            q = """update contacts set %s=%%s where id=%%s""" % key
            q_args = (value, contact_id)
            await cur.execute(q, q_args)

    await dbcon.transact(_run)


async def delete_contact(dbcon: DBConnection, contact_id: int):
    """Remove a contact from the database."""
    q = """delete from contacts where id=%s"""
    await dbcon.operation(q, (contact_id,))


async def contact_exists(dbcon: DBConnection, contact_id: int) -> bool:
    """Check if a contact id exists."""
    q = """select id from contacts where id=%s"""
    res = await dbcon.fetch_single(q, (contact_id,))
    ret = False
    if res:
        ret = True
    return ret


async def get_contact_dict_for_active_monitor(dbcon: DBConnection, monitor: 'ActiveMonitor') -> Dict[str, set]:
    """Get all contact addresses/numbers for a specific active monitor.

    Return: Dict[str, Set(str)] for 'email' and 'phone'.
    """
    ret = {
        'email': set(),
        'phone': set(),
    }  # type: Dict[str, set]
    await get_direct_contacts_for_active_monitor(dbcon, monitor.id, ret['email'], ret['phone'])
    await get_group_contacts_for_active_monitor(dbcon, monitor.id, ret['email'], ret['phone'])
    return ret


async def get_direct_contacts_for_active_monitor(dbcon: DBConnection, monitor_id: int,
                                                 email_set: Set[str], phone_set: Set[str]):
    """Called from get_contact_dict_for_active_monitor.

    Updates email/phone sets for contacts attached to a monitor.
    """
    q = """select
        contacts.email, contacts.phone
        from active_monitor_contacts, contacts
        where active_monitor_contacts.active_monitor_id = %s
        and active_monitor_contacts.contact_id = contacts.id
        and contacts.active = true"""
    q_args = (monitor_id,)
    rows = await dbcon.fetch_all(q, q_args)
    for email, phone in rows:
        if email:
            email_set.add(email)
        if phone:
            phone_set.add(phone)


async def get_group_contacts_for_active_monitor(dbcon: DBConnection, monitor_id: int,
                                                email_set: Set[str], phone_set: Set[str]):
    """Called from get_contact_dict_for_active_monitor.

    Updates email/phone sets for contact groups attached to a monitor.
    """
    q = """select contacts.email, contacts.phone
        from active_monitor_contact_groups, contact_groups, contact_group_contacts, contacts
        where active_monitor_contact_groups.active_monitor_id = %s
        and active_monitor_contact_groups.contact_group_id = contact_groups.id
        and contact_groups.active = true
        and contact_groups.id = contact_group_contacts.contact_group_id
        and contact_group_contacts.contact_id = contacts.id
        and contacts.active = true"""
    q_args = (monitor_id,)
    rows = await dbcon.fetch_all(q, q_args)
    for email, phone in rows:
        if email:
            email_set.add(email)
        if phone:
            phone_set.add(phone)


async def add_contact_to_active_monitor(dbcon: DBConnection, contact_id: int, monitor_id: int):
    """Connect a contact and an active monitor."""
    q = """select id from active_monitors where id=%s"""
    rows = await dbcon.fetch_row(q, (monitor_id,))
    if len(rows) != 1:
        raise errors.InvalidArguments('monitor does not exist')
    q = """select id from contacts where id=%s"""
    rows = await dbcon.fetch_row(q, (contact_id,))
    if len(rows) != 1:
        raise errors.InvalidArguments('contact does not exist')
    q = """replace into active_monitor_contacts (active_monitor_id, contact_id) values (%s, %s)"""
    q_args = (monitor_id, contact_id)
    await dbcon.operation(q, q_args)


async def delete_contact_from_active_monitor(dbcon: DBConnection, contact_id: int, monitor_id: int):
    """Disconnect a contact and an active monitor."""
    q = """delete from active_monitor_contacts where active_monitor_id=%s and contact_id=%s"""
    q_args = (monitor_id, contact_id)
    await dbcon.operation(q, q_args)


async def set_active_monitor_contacts(dbcon: DBConnection,
                                      contact_ids: Iterable[int], monitor_id: int):
    """(Re-)set contacts for an active monitor.

    Delete existing contacts for an active monitor and set the given new
    contacts.
    """
    async def _run(cur):
        q = """delete from active_monitor_contacts where active_monitor_id=%s"""
        await cur.execute(q, (monitor_id,))
        for contact_id in contact_ids:
            q = """insert into active_monitor_contacts (active_monitor_id, contact_id) values (%s, %s)"""
            q_args = (monitor_id, contact_id)
            await cur.execute(q, q_args)
    _q = """select id from active_monitors where id=%s"""
    if await dbcon.count_rows(_q, (monitor_id,)) != 1:
        raise errors.InvalidArguments('monitor does not exist')
    await dbcon.transact(_run)


async def get_contacts_for_active_monitor(dbcon: DBConnection, monitor_id: int) -> Iterable[Dict[str, str]]:
    """Get contacts for an active monitor.

    Return a list of dicts, one dict describing each contacts information.
    """
    q = """select
        contacts.id, contacts.name, contacts.email, contacts.phone, contacts.active
        from active_monitor_contacts, contacts
        where active_monitor_contacts.active_monitor_id = %s
        and active_monitor_contacts.contact_id = contacts.id"""
    q_args = (monitor_id,)
    rows = await dbcon.fetch_all(q, q_args)
    contacts = []
    for id, name, email, phone, active in rows:
        contacts.append({
            'id': id,
            'name': name,
            'email': email,
            'phone': phone,
            'active': active
        })
    return contacts
