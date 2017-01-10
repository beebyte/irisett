# noinspection PyPackageRequirements
import pytest
import asyncio
from irisett.sql import DBConnection
from irisett.notify.manager import NotificationManager
from irisett.monitor import active_sql
from irisett.monitor.active import (
    ActiveMonitorManager,
    ActiveMonitorDef,
    create_active_monitor_def,
)
from irisett import (
    monitor_group,
    object_models,
    contact
)
from sqlsetup import get_dbcon


@pytest.fixture
def notification_manager():
    notification_manager = NotificationManager(config=None)
    return notification_manager


@pytest.mark.asyncio
async def test_monitor_group_basic():
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
    contact_id = await contact.create_contact(dbcon, 'Name', 'test@example.com', '12345', True)
    await contact.add_contact_to_active_monitor(dbcon, contact_id, monitor_id)
    monitor_contacts = await contact.get_all_contacts_for_active_monitor(dbcon, monitor_id)
    assert len(monitor_contacts) == 1



#@pytest.mark.asyncio
#async def test_active_monitor_manager(notification_manager):
#    dbcon = DBConnection(host=DB_HOST, user=DB_USERNAME, passwd=DB_PASSWORD, dbname=DB_NAME)
#    await dbcon.initialize(only_init_tables=True)
#    mon_manager = ActiveMonitorManager(dbcon, notification_manager, 10)
#    assert isinstance(mon_manager, ActiveMonitorManager)


#@pytest.mark.asyncio
#async def test_create_active_monitor_def(notification_manager):
#    dbcon = DBConnection(host=DB_HOST, user=DB_USERNAME, passwd=DB_PASSWORD, dbname=DB_NAME)
#    await dbcon.initialize(only_init_tables=True)
#    mon_manager = ActiveMonitorManager(dbcon, notification_manager, 10)
#    await mon_manager.load()
#    num_defs = len(mon_manager.monitor_defs)
#    monitor_def = await create_active_monitor_def(
#        mon_manager, 'Ping monitor', '',
#        True, '/usr/lib/nagios/plugins/check_http',
#        '-H {{hostname}} -w {{rtt}},{{pl}}% -c {{rtt}},{{pl}}%',
#        'Ping monitor for {{hostname}}')
#    assert isinstance(monitor_def, ActiveMonitorDef)
#    assert len(mon_manager.monitor_defs) > num_defs
#    await dbcon.close()
