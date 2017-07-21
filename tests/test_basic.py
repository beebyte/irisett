# noinspection PyPackageRequirements
import pytest
import asyncio
from irisett.sql import DBConnection
from irisett.notify.manager import NotificationManager
from irisett.monitor import active_sql
from irisett import (
    object_models,
    contact,
    monitor_group,
)
from sqlsetup import get_dbcon


@pytest.fixture
def notification_manager():
    notification_manager = NotificationManager(config=None)
    return notification_manager


@pytest.mark.asyncio
async def test_monitor_group_basic():
    """Create/update/delete monitor groups."""
    dbcon = await get_dbcon(reinit=False)
    group_id = await monitor_group.create_monitor_group(dbcon, parent_id=None, name='Test')
    assert group_id is not None
    group = await monitor_group.get_monitor_group(dbcon, group_id)
    assert group.name == 'Test'
    await monitor_group.update_monitor_group(dbcon, group_id, {'name': 'Test2'})
    group = await monitor_group.get_monitor_group(dbcon, group_id)
    assert group.name == 'Test2'
    await monitor_group.delete_monitor_group(dbcon, group_id)
    group = await monitor_group.get_monitor_group(dbcon, group_id)
    assert group is None


@pytest.mark.asyncio
async def test_active_monitor_contacts():
    """Test that all ways to attach contacts to a monitor work.

    This includes:
        contact -> monitor
        contact -> contact group -> monitor
        contact -> monitor group -> monitor
        contact -> contact group -> monitor group -> monitor
    """
    dbcon = await get_dbcon(reinit=False)
    monitor_def_id = await active_sql.create_active_monitor_def(
        dbcon,
        object_models.ActiveMonitorDef(
            id=None,
            name='Test monitor def',
            description='',
            active=True,
            cmdline_filename='',
            cmdline_args_tmpl='',
            description_tmpl='',
        )
    )
    monitor_id = await active_sql.create_active_monitor(dbcon, monitor_def_id, {})
    contact_1_id = await contact.create_contact(dbcon, 'Name', 'test1@example.com', '12345', True)
    await contact.add_contact_to_active_monitor(dbcon, contact_1_id, monitor_id)
    monitor_contacts = await contact.get_all_contacts_for_active_monitor(dbcon, monitor_id)
    assert len(list(monitor_contacts)) == 1
    contact_group_id = await contact.create_contact_group(dbcon, 'Name', True)
    contact_2_id = await contact.create_contact(dbcon, 'Name', 'test2@example.com', '12345', True)
    await contact.add_contact_to_contact_group(dbcon, contact_group_id, contact_2_id)
    await contact.add_contact_group_to_active_monitor(dbcon, contact_group_id, monitor_id)
    monitor_contacts = await contact.get_all_contacts_for_active_monitor(dbcon, monitor_id)
    assert len(list(monitor_contacts)) == 2
    monitor_group_id = await monitor_group.create_monitor_group(dbcon, None, 'Name')
    await monitor_group.add_active_monitor_to_monitor_group(dbcon, monitor_group_id, monitor_id)
    contact_3_id = await contact.create_contact(dbcon, 'Name', 'test3@example.com', '12345', True)
    await monitor_group.add_contact_to_monitor_group(dbcon, monitor_group_id, contact_3_id)
    monitor_contacts = await contact.get_all_contacts_for_active_monitor(dbcon, monitor_id)
    assert len(list(monitor_contacts)) == 3
    contact_group_2_id = await contact.create_contact_group(dbcon, 'Name', True)
    contact_4_id = await contact.create_contact(dbcon, 'Name', 'test4@example.com', '12345', True)
    await contact.add_contact_to_contact_group(dbcon, contact_group_2_id, contact_4_id)
    await monitor_group.add_contact_group_to_monitor_group(dbcon, monitor_group_id, contact_group_2_id)
    monitor_contacts = await contact.get_all_contacts_for_active_monitor(dbcon, monitor_id)
    assert len(list(monitor_contacts)) == 4
    contacts = await contact.get_contact_dict_for_active_monitor(dbcon, monitor_id)
    assert len(contacts['email']) == 4
