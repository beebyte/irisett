# noinspection PyPackageRequirements
import pytest
from irisett.sql import DBConnection
from irisett.notify.manager import NotificationManager
from irisett.monitor.active import (
    ActiveMonitorManager,
    ActiveMonitorDef,
    create_active_monitor_def,
)

DB_HOST = 'localhost'
DB_USERNAME = 'irisett'
DB_PASSWORD = 'Eichee0e'
DB_NAME = 'irisett_test'


@pytest.fixture
def notification_manager():
    notification_manager = NotificationManager(config=None)
    return notification_manager


@pytest.mark.asyncio
async def test_active_monitor_manager(notification_manager):
    dbcon = DBConnection(host=DB_HOST, user=DB_USERNAME, passwd=DB_PASSWORD, dbname=DB_NAME)
    await dbcon.initialize(only_init_tables=True)
    mon_manager = ActiveMonitorManager(dbcon, notification_manager, 10)
    assert isinstance(mon_manager, ActiveMonitorManager)


@pytest.mark.asyncio
async def test_create_active_monitor_def(notification_manager):
    dbcon = DBConnection(host=DB_HOST, user=DB_USERNAME, passwd=DB_PASSWORD, dbname=DB_NAME)
    await dbcon.initialize(only_init_tables=True)
    mon_manager = ActiveMonitorManager(dbcon, notification_manager, 10)
    await mon_manager.load()
    num_defs = len(mon_manager.monitor_defs)
    monitor_def = await create_active_monitor_def(
        mon_manager, 'Ping monitor', '',
        True, '/usr/lib/nagios/plugins/check_http',
        '-H {{hostname}} -w {{rtt}},{{pl}}% -c {{rtt}},{{pl}}%',
        'Ping monitor for {{hostname}}')
    assert isinstance(monitor_def, ActiveMonitorDef)
    assert len(mon_manager.monitor_defs) > num_defs
    await dbcon.close()
