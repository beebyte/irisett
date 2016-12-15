"""Irisett active monitoring (service checks).

This is the core of irisetts monitoring. Monitor definitions and monitors
are both loaded into memory and kept there so they must be updated both
in the database and in memory.

A monitor managed is used for scheduling monitor service checks and starting
each check.
"""

from typing import Dict, Any, List, Union, Optional
import time
import random
import jinja2
import shlex
import asyncio

from irisett import (
    log,
    nagios,
    utils,
    errors,
    contact,
    stats,
)
from irisett.metadata import get_metadata
from irisett.notify.manager import NotificationManager
from irisett.sql import DBConnection

DEFAULT_MONITOR_INTERVAL = 180
DOWN_THRESHOLD = 3
# DOWN_THRESHOLD = 0
UNKNOWN_THRESHOLD = 5


async def load_monitor_defs(manager: 'ActiveMonitorManager') -> Dict[int, 'ActiveMonitorDef']:
    """Load all monitor definitions.

    Return a dict mapping def id to def instance.
    """
    sql_defs = await _sql_load_monitor_defs(manager.dbcon)
    await _sql_load_monitor_defs_args(manager.dbcon, sql_defs)
    cls_defs = {}
    for def_id, sql_def in sql_defs.items():
        cls_defs[def_id] = ActiveMonitorDef(
            def_id, sql_def['name'], sql_def['active'], sql_def['cmdline_filename'],
            sql_def['cmdline_args_tmpl'], sql_def['description_tmpl'],
            sql_def['args'], manager)
    return cls_defs


async def _sql_load_monitor_defs(dbcon: DBConnection) -> Dict[int, Dict[str, Any]]:
    """Load monitor defs from the database.

    Returns a dict mapping def it to a dict of def data.
    """
    q = """select id, name, active, cmdline_filename, cmdline_args_tmpl, description_tmpl from active_monitor_defs"""
    rows = await dbcon.fetch_all(q)
    defs = {}
    for id, name, active, cmdline_filename, cmdline_args_tmpl, description_tmpl in rows:
        defs[id] = {
            'id': id,
            'name': name,
            'active': active,
            'cmdline_filename': cmdline_filename,
            'cmdline_args_tmpl': cmdline_args_tmpl,
            'description_tmpl': description_tmpl,
            'args': []
        }
    return defs


async def _sql_load_monitor_defs_args(dbcon: DBConnection, defs: Dict[int, Dict[str, Any]]):
    """Take the output from _sql_load_monitor_defs and add in def arguments."""
    q = """select id, active_monitor_def_id, name, required, default_value from active_monitor_def_args"""
    rows = await dbcon.fetch_all(q)
    for id, def_id, name, required, default_value in rows:
        defs[def_id]['args'].append({
            'id': id,
            'name': name,
            'required': required,
            'default_value': default_value,
        })


async def load_monitors(manager: 'ActiveMonitorManager') -> Dict[int, 'ActiveMonitor']:
    """Load all monitors.

    Return a dict mapping monitor id to monitor instance.
    """
    sql_monitors = await _sql_load_monitors(manager.dbcon)
    await _sql_load_monitor_args(manager.dbcon, sql_monitors)
    cls_monitors = {}
    for monitor_id, sql_monitor in sql_monitors.items():
        monitor_def = manager.monitor_defs[sql_monitor['def_id']]
        cls_monitors[monitor_id] = ActiveMonitor(
            monitor_id, sql_monitor['args'],
            monitor_def,
            sql_monitor['state'],
            sql_monitor['state_ts'],
            sql_monitor['msg'],
            sql_monitor['alert_id'],
            sql_monitor['checks_enabled'],
            sql_monitor['alerts_enabled'],
            manager)
    return cls_monitors


async def _sql_load_monitors(dbcon: DBConnection) -> Dict[int, Dict[str, Any]]:
    """Load monitors from the database.

    Returns a dict mapping monitor to a dict of monitor data.
    """
    q = """select id, def_id, state, state_ts, msg, alert_id, checks_enabled, alerts_enabled from active_monitors"""
    rows = await dbcon.fetch_all(q)
    monitors = {}
    for id, def_id, state, state_ts, msg, alert_id, checks_enabled, alerts_enabled in rows:
        monitors[id] = {
            'id': id,
            'def_id': def_id,
            'state': state,
            'state_ts': state_ts,
            'msg': msg,
            'alert_id': alert_id,
            'checks_enabled': checks_enabled,
            'alerts_enabled': alerts_enabled,
            'args': {}
        }
    return monitors


async def _sql_load_monitor_args(dbcon: DBConnection, monitors: Dict[int, Dict[str, Any]]):
    """Take the output from _sql_load_monitors and add in monitor arguments."""
    q = """select monitor_id, name, value from active_monitor_args"""
    rows = await dbcon.fetch_all(q)
    for monitor_id, name, value in rows:
        monitors[monitor_id]['args'][name] = value


class ActiveMonitorManager:
    """The manager and main loop for active monitors.

    The monitor manager keeps track of monitor definitions and monitors.
    It does the initial scheduling of monitor jobs and supports the loop that
    keep monitor jobs running.
    """

    def __init__(self, dbcon: DBConnection, notification_manager: NotificationManager,
                 max_concurrent_jobs: int, *, debug_mode: bool=False, loop: asyncio.AbstractEventLoop=None) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.dbcon = dbcon
        self.notification_manager = notification_manager
        self.max_concurrent_jobs = max_concurrent_jobs
        self.debug_mode = debug_mode
        if debug_mode:
            log.debug('Debug mode active, all monitors will be started immediately')
        self.monitor_defs = {}  # type: Dict[int, ActiveMonitorDef]
        self.monitors = {}  # type: Dict[int, ActiveMonitor]
        self.num_running_jobs = 0
        stats.set('total_jobs_run', 0, 'ACT_MON')
        stats.set('cur_running_jobs', 0, 'ACT_MON')
        stats.set('num_monitors', 0, 'ACT_MON')
        stats.set('jobs_deferred', 0, 'ACT_MON')
        stats.set('checks_up', 0, 'ACT_MON')
        stats.set('checks_down', 0, 'ACT_MON')
        stats.set('checks_unknown', 0, 'ACT_MON')

    async def initialize(self):
        """Load all data required for the managed main loop to run.

        This can't be called from __init__ as it is an async call.
        """
        await remove_deleted_monitors(self.dbcon)
        self.monitor_defs = await load_monitor_defs(self)
        self.monitors = await load_monitors(self)
        log.msg('Loaded %d active monitor definitions' % (len(self.monitor_defs)))
        log.msg('Loaded %d active monitors' % (len(self.monitors)))

    def start(self):
        for monitor in self.monitors.values():
            start_delay = 0
            if not self.debug_mode:
                start_delay = random.randint(1, DEFAULT_MONITOR_INTERVAL)
            self.schedule_monitor(monitor, start_delay)
        # self.scheduleMonitor(monitor, 0)
        self.check_missing_schedules()

    def check_missing_schedules(self):
        """Failsafe to check that no monitors are missing scheduled checks.

        This will detect monitors that are lacking missing scheduled jobs.
        This shouldn't happen, this is a failsafe in case somthing is buggy.
        """
        log.debug('Running monitor missing schedule check')
        self.loop.call_later(600, self.check_missing_schedules)
        for monitor in self.monitors.values():
            if not monitor.deleted and not monitor.monitoring and not monitor.scheduled_job:
                log.msg('%s is missing scheduled job, this is probably a bug, scheduling now' % monitor)
                self.schedule_monitor(monitor, DEFAULT_MONITOR_INTERVAL)

    def run_monitor(self, monitor_id: int):
        """Run self._run_monitor.

        _run_monitor is a coroutine and can't be called directly from
        loop.call_later.
        """
        self.loop.create_task(self._run_monitor(monitor_id))  # type: ignore

    async def _run_monitor(self, monitor_id: int):
        monitor = self.monitors.get(monitor_id)
        if not monitor:
            log.debug('Skipping scheduled job for missing monitor %s' % monitor_id)
            return None
        monitor.scheduled_job = None
        if self.num_running_jobs > self.max_concurrent_jobs:
            log.msg('Deferred monitor %s due to to many running jobs' % monitor)
            self.schedule_monitor(monitor, random.randint(10, 30))
            stats.inc('jobs_deferred', 'ACT_MON')
            return None
        self.num_running_jobs += 1
        stats.inc('total_jobs_run', 'ACT_MON')
        stats.inc('cur_running_jobs', 'ACT_MON')
        try:
            await monitor.run()
        except Exception as e:
            stats.dec('cur_running_jobs', 'ACT_MON')
            self.num_running_jobs -= 1
            log.msg('Monitor run raised error: %s' % (str(e)))
            if not monitor.scheduled_job:
                self.schedule_monitor(monitor, DEFAULT_MONITOR_INTERVAL)
            raise
        self.num_running_jobs -= 1
        stats.dec('cur_running_jobs', 'ACT_MON')

    def schedule_monitor(self, monitor: 'ActiveMonitor', interval: int):
        log.debug('Scheduling %s for %ds' % (monitor, interval))
        if monitor.scheduled_job:
            try:
                monitor.scheduled_job.cancel()
            except ValueError:
                pass
        monitor.scheduled_job = self.loop.call_later(interval, self.run_monitor, monitor.id)  # type: ignore

    def add_monitor(self, monitor: 'ActiveMonitor'):
        self.monitors[monitor.id] = monitor
        self.schedule_monitor(monitor, 0)


class ActiveMonitorDef(log.LoggingMixin):
    def __init__(self, id: int, name: str, active: bool, cmdline_filename: str, cmdline_args_tmpl: str,
                 description_tmpl: str, arg_spec: List[Dict[str, str]], manager: ActiveMonitorManager) -> None:
        self.id = id
        self.name = name
        self.active = active
        self.cmdline_filename = cmdline_filename
        self.cmdline_args_tmpl = cmdline_args_tmpl
        self.description_tmpl = description_tmpl
        self.arg_spec = arg_spec
        self.manager = manager
        self.jinja_cmdline_args = jinja2.Template(cmdline_args_tmpl)
        self.jinja_description_tmpl = jinja2.Template(description_tmpl)

    def __str__(self):
        return '<ActiveMonitorDef(%s/%s)>' % (self.id, self.cmdline_filename)

    def get_arg_with_name(self, name: str) -> Optional[Dict[str, Any]]:
        match = None
        for arg in self.arg_spec:
            if arg['name'] == name:
                match = arg
                break
        return match

    def expand_monitor_args(self, monitor_args: Dict[str, str]) -> List[str]:
        """Expand the monitors command line arguments.

        The monitor command line arguments are based on monitor def
        cmdline_args_tmpl template.
        """
        args = {a['name']: a['default_value'] for a in self.arg_spec}
        args.update(monitor_args)
        expanded = self.jinja_cmdline_args.render(**args)
        ret = shlex.split(expanded)  # Supports "" splitting etc.
        return ret

    def get_monitor_description(self, monitor_args: Dict[str, str]) -> str:
        """Return a monitor description based on this monitor def.

        This uses the monitor def description_tmpl to create a useful
        monitor description based on the monitors (commandline) arguments
        and the monitor defs default values.

        This is used when sending monitor notifications.
        """
        args = {a['name']: a['default_value'] for a in self.arg_spec}
        args.update(monitor_args)
        description = self.jinja_description_tmpl.render(**args)
        return description

    def validate_monitor_args(self, monitor_args: Dict[str, str], permit_missing: bool = False) -> bool:
        if not permit_missing:
            for arg in self.arg_spec:
                if arg['required'] and arg['name'] not in monitor_args:
                    raise errors.InvalidArguments('missing argument %s' % arg['name'])
        arg_name_set = {a['name'] for a in self.arg_spec}
        for key, value in monitor_args.items():
            if key not in arg_name_set:
                raise errors.InvalidArguments('invalid argument %s' % key)
        return True

    async def delete(self):
        for monitor in self.manager.monitors.values():
            if monitor.monitor_def.id == self.id:
                raise errors.IrisettError('can\'t remove active monitor def that is in use')
        del self.manager.monitor_defs[self.id]
        await remove_monitor_def_from_db(self.manager.dbcon, self.id)

    async def update(self, update_params: Dict[str, Any]):
        async def _run(cur):
            for param in ['name', 'description', 'active', 'cmdline_filename', 'cmdline_args_tmpl', 'description_tmpl']:
                if param in update_params:
                    q = """update active_monitor_defs set %s=%%s where id=%%s""" % param
                    q_args = (update_params[param], self.id)
                    await cur.execute(q, q_args)

        self.log_msg('updating monitor def')
        if 'name' in update_params:
            self.name = update_params['name']
        if 'active' in update_params:
            self.active = update_params['active']
        if 'cmdline_filename' in update_params:
            self.cmdline_filename = update_params['cmdline_filename']
        if 'cmdline_args_tmpl' in update_params:
            self.cmdline_args_tmpl = update_params['cmdline_args_tmpl']
            self.jinja_cmdline_args = jinja2.Template(self.cmdline_args_tmpl)
            self.update_monitor_expanded_args()
        if 'description_tmpl' in update_params:
            self.description_tmpl = update_params['description_tmpl']
            self.jinja_description_tmpl = jinja2.Template(self.description_tmpl)
        await self.manager.dbcon.transact(_run)

    def update_monitor_expanded_args(self):
        for monitor in self.manager.monitors.values():
            if monitor.monitor_def.id == self.id:
                monitor.expanded_args = self.expand_monitor_args(monitor.args)

    async def set_arg(self, name: str, display_name: str, description: str, required: bool, default_value: str):
        arg = self.get_arg_with_name(name)
        if arg:
            arg['name'] = name
            arg['required'] = required
            arg['default_value'] = default_value
            await update_monitor_def_arg_in_db(self.manager.dbcon, arg['id'], name,
                                               display_name, description, required, default_value)
        else:
            arg = {
                'name': name,
                'required': required,
                'default_value': default_value
            }
            arg['id'] = await add_monitor_def_arg_to_db(self.manager.dbcon,
                                                        self.id, name, display_name,
                                                        description, required, default_value)
            self.arg_spec.append(arg)
        self.update_monitor_expanded_args()
        return arg

    async def delete_arg(self, name):
        arg = self.get_arg_with_name(name)
        if arg:
            self.arg_spec.remove(arg)
            await delete_monitor_def_arg_from_db(self.manager.dbcon, arg['id'])
            self.update_monitor_expanded_args()

    async def get_notify_data(self):
        q = """select name, description from active_monitor_defs where id=%s"""
        q_args = (self.id,)
        res = await self.manager.dbcon.fetch_all(q, q_args)
        name, description = res[0]
        ret = {
            'name': name,
            'description': description,
        }
        return ret


class ActiveMonitor(log.LoggingMixin):
    def __init__(self, id: int, args: Dict[str, str], monitor_def: ActiveMonitorDef, state: str, state_ts: float,
                 msg: str, alert_id: Union[int, None], checks_enabled: bool,
                 alerts_enabled: bool, manager: ActiveMonitorManager) -> None:
        self.id = id
        self.args = args
        self.monitor_def = monitor_def
        self.expanded_args = monitor_def.expand_monitor_args(args)
        self.state = state
        self.manager = manager
        self.last_check_state = None  # type: Optional[str]
        self.consecutive_checks = 0
        self.last_check = time.time()
        self.msg = msg
        self.alert_id = alert_id
        self.state_ts = state_ts
        if not self.state_ts:
            self.state_ts = time.time()
        self.monitoring = False
        self.deleted = False
        self.checks_enabled = checks_enabled
        self.alerts_enabled = alerts_enabled
        self._pending_reset = False
        self.scheduled_job = None  # type: Optional[asyncio.Handle]
        stats.inc('num_monitors', 'ACT_MON')

    def __str__(self):
        return '<ActiveMonitor(%s/%s/%s)>' % (self.id, self.state, self.last_check_state)

    async def run(self):
        if self.deleted or self.monitoring:
            return False
        self.monitoring = True
        self.last_check = time.time()
        try:
            await self._run()
        except:
            self.monitoring = False
            raise
        self.monitoring = False

    async def _run(self):
        if self._pending_reset:
            await self.reset_monitor()
        if not self.checks_enabled:
            self.log_debug('skipping monitor check, disabled')
            self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            return
        self.log_debug('monitoring: %s %s' % (self.monitor_def.cmdline_filename, self.expanded_args))
        try:
            msg = await nagios.run_plugin(self.monitor_def.cmdline_filename, self.expanded_args, 30)
            msg, perf = msg
            check_state = 'UP'
        except nagios.MonitorFailedError as e:
            msg = e.args[0]
            self.log_debug('monitoring failed: %s' % msg)
            check_state = 'DOWN'
        except nagios.NagiosError as e:
            self.log_debug('monitoring unknown error: %s' % (str(e)))
            check_state = 'UNKNOWN'
            msg = str(e)
        msg = msg[:199]  # Set a reasonable max length for stored monitor messages.
        if type(msg) == bytes:
            msg = msg.decode('utf-8', errors='ignore')
        self.msg = msg
        self.update_consecutive_checks(check_state)
        await self.handle_check_result(check_state, msg)
        self.log_debug('monitoring complete')
        if self.deleted:
            await self._purge()

    async def handle_check_result(self, check_state: str, msg: str):
        if check_state == 'UP' and self.state == 'UP':
            # Introduce a slight variation in monitoring intervals when
            # everything is going ok for a monitor. This will help spread
            # the service check times out.
            self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL + random.randint(-5, 5))
            stats.inc('checks_up', 'ACT_MON')
        elif check_state == 'UP' and self.state != 'UP':
            self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            await self.state_change('UP', msg)
            stats.inc('checks_up', 'ACT_MON')
        elif check_state == 'DOWN' and self.state == 'DOWN':
            self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            stats.inc('checks_down', 'ACT_MON')
        elif check_state == 'DOWN' and self.state == 'UNKNOWN':
            await self.state_change('DOWN', msg)
            self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            stats.inc('checks_down', 'ACT_MON')
        elif check_state == 'DOWN' and self.state != 'DOWN':
            if self.consecutive_checks >= DOWN_THRESHOLD:
                await self.state_change('DOWN', msg)
                self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            else:
                self.manager.schedule_monitor(self, 30)
            stats.inc('checks_down', 'ACT_MON')
        elif check_state == 'UNKNOWN' and self.state == 'UNKNOWN':
            self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            stats.inc('checks_unknown', 'ACT_MON')
        elif check_state == 'UNKNOWN' and self.state != 'UNKNOWN':
            if self.consecutive_checks >= UNKNOWN_THRESHOLD:
                await self.state_change('UNKNOWN', msg)
                self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            else:
                self.manager.schedule_monitor(self, 120)
            stats.inc('checks_unknown', 'ACT_MON')

    async def _set_monitor_checks_disabled(self):
        self.state = 'UNKNOWN'
        self.state_ts = int(time.time())
        self.msg = ''

    async def state_change(self, new_state: str, msg: str):
        prev_state = self.state
        prev_state_ts = self.state_ts
        self.state = new_state
        self.state_ts = int(time.time())
        self.msg = msg
        self.log_msg('changed state to %s - %s' % (new_state, msg))
        if new_state == 'DOWN':
            await self.set_down()
            await self.notify_state_change(prev_state, prev_state_ts)
        elif new_state == 'UP':
            await self.set_up()
            if prev_state == 'DOWN':
                await self.notify_state_change(prev_state, prev_state_ts)
        else:
            await self.set_unknown()

    async def notify_state_change(self, prev_state: str, prev_state_ts: float):
        if not self.alerts_enabled:
            self.log_debug('skipping alert notifications, disabled')
            return
        contacts = await contact.get_contact_dict_for_active_monitor(
            self.manager.dbcon, self)
        metadata = await self.get_metadata()
        tmpl_data = {}  # type: Dict[str, Any]
        for key, value in metadata.items():
            tmpl_data['meta_%s' % key] = value
        if prev_state_ts and self.state_ts - prev_state_ts:
            tmpl_data['state_elapsed'] = utils.get_display_time(self.state_ts - prev_state_ts)
        tmpl_data['state'] = self.state
        tmpl_data['prev_state'] = prev_state
        tmpl_data['type'] = 'active_monitor'
        tmpl_data['id'] = self.id
        tmpl_data['monitor_description'] = self.get_description()
        tmpl_data['msg'] = self.msg
        # Don't wait for notifications to be sent, it may or may not take a
        # while and we don't want to pause the monitoring to wait for it.
        self.manager.loop.create_task(
            self.manager.notification_manager.send_notification(contacts, tmpl_data))  # type: ignore

    def get_description(self) -> str:
        return self.monitor_def.get_monitor_description(self.args)

    def update_consecutive_checks(self, state):
        """Update the counter for consecutive checks with the same result."""
        if state == self.last_check_state:
            self.consecutive_checks += 1
        else:
            self.consecutive_checks = 0
        self.last_check_state = state

    async def set_up(self):
        """Set a monitor up (in the database)."""

        async def _run(cur):
            if self.alert_id:
                await self.txn_close_alert(cur)
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)

    async def set_down(self):
        """Set a monitor down (in the database)."""

        async def _run(cur):
            await self.txn_create_alert(cur)
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)

    async def set_unknown(self):
        """Set a monitor in unknown state (in the database)."""

        async def _run(cur):
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)

    async def txn_create_alert(self, cur):
        q = """insert into active_monitor_alerts (monitor_id, start_ts, end_ts, alert_msg) values (%s, %s, %s, %s)"""
        q_args = (self.id, self.state_ts, 0, self.msg)
        await cur.execute(q, q_args)
        self.alert_id = cur.lastrowid

    async def txn_close_alert(self, cur):
        q = """update active_monitor_alerts set end_ts=%s where id=%s"""
        q_args = (self.state_ts, self.alert_id)
        await cur.execute(q, q_args)
        self.alert_id = None

    async def txn_save_state(self, cur):
        q = """update active_monitors set state=%s, state_ts=%s, msg=%s, alert_id=%s where id=%s"""
        q_args = (self.state, self.state_ts, self.msg, self.alert_id, self.id)
        await cur.execute(q, q_args)

    async def delete(self):
        """Delete an existing monitor.

        If the monitor is not running it will be removed immediately.
        If the monitor is running it will be remove when the run is complete.
        """
        if self.deleted:
            return
        self.log_msg('deleting monitor')
        self.deleted = True
        if self.id in self.manager.monitors:
            del self.manager.monitors[self.id]
        if self.monitoring:
            q = """update active_monitors set deleted=true where id=%s"""
            q_args = (int(time.time()), self.id,)
            await self.manager.dbcon.operation(q, q_args)
        else:
            await self._purge()

    async def _purge(self):
        """Remove a monitor from the database."""
        self.log_msg('purging deleted monitor')
        stats.dec('num_monitors', 'ACT_MON')
        await remove_monitor_from_db(self.manager.dbcon, self.id)

    async def update_args(self, args: Dict[str, str]):
        async def _run(cur):
            q = """delete from active_monitor_args where monitor_id=%s"""
            q_args = (self.id,)
            await cur.execute(q, q_args)
            q = """insert into active_monitor_args (monitor_id, name, value) values (%s, %s, %s)"""
            for name, value in args.items():
                q_args = (self.id, name, value)
                await cur.execute(q, q_args)

        self.log_msg('updating monitor arguments')
        self.monitor_def.validate_monitor_args(args)
        self.args = args
        self.expanded_args = self.monitor_def.expand_monitor_args(args)
        await self.manager.dbcon.transact(_run)

    async def set_checks_enabled_status(self, checks_enabled: bool):
        if self.checks_enabled == checks_enabled:
            return
        self.log_debug('settings monitor checks to %s' % checks_enabled)
        self.checks_enabled = checks_enabled
        if not checks_enabled:
            await self.reset_monitor()
        q = """update active_monitors set checks_enabled=%s where id=%s"""
        q_args = (checks_enabled, self.id)
        self.schedule_immediately()
        await self.manager.dbcon.operation(q, q_args)

    async def set_alerts_enabled_status(self, alerts_enabled: bool):
        if self.alerts_enabled == alerts_enabled:
            return
        self.log_debug('settings monitor alerts to %s' % alerts_enabled)
        self.alerts_enabled = alerts_enabled
        q = """update active_monitors set alerts_enabled=%s where id=%s"""
        q_args = (alerts_enabled, self.id)
        await self.manager.dbcon.operation(q, q_args)

    def schedule_immediately(self):
        """Schedule a check for this monitor ASAP."""
        if not self.monitoring and not self.deleted:
            self.log_msg('Forcing immediate check by request')
            self.manager.schedule_monitor(self, 5)

    async def get_metadata(self) -> Dict[str, str]:
        ret = await get_metadata(self.manager.dbcon, 'active_monitor', self.id)
        return ret

    async def reset_monitor(self):
        """Reset a monitor to its initial state.

        This is currently only used when disabling checks for a monitor
        but might be useful for other purposes in the future.
        """
        if self.monitoring:
            self._pending_reset = True
            return
        self._pending_reset = False
        self.state = 'UNKNOWN'
        self.state_ts = int(time.time())
        self.msg = ''
        self.consecutive_checks = 0

        async def _run(cur):
            if self.alert_id:
                await self.txn_close_alert(cur)
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)


async def remove_monitor_from_db(dbcon: DBConnection, monitor_id: int):
    """Remove all traces of a monitor from the database."""

    async def _run(cur):
        q_args = (monitor_id,)
        q = """delete from active_monitors where id=%s"""
        await cur.execute(q, q_args)
        q = """delete from active_monitor_args where monitor_id=%s"""
        await cur.execute(q, q_args)
        q = """delete from active_monitor_alerts where monitor_id=%s"""
        await cur.execute(q, q_args)
        q = """delete from active_monitor_contacts where active_monitor_id=%s"""
        await cur.execute(q, q_args)
        q = """delete from object_metadata where object_type="active_monitor" and object_id=%s"""
        await cur.execute(q, q_args)
        q = """delete from object_bindata where object_type="active_monitor" and object_id=%s"""
        await cur.execute(q, q_args)

    await dbcon.transact(_run)


async def remove_deleted_monitors(dbcon: DBConnection):
    """Remove any monitors that have previously been set as deleted.

    This runs once every time the server starts up.
    """
    log.msg('Purging all deleted active monitor')
    q = """select id from active_monitors where deleted=true"""
    rows = await dbcon.fetch_all(q)
    for monitor_id in rows:
        await remove_monitor_from_db(dbcon, monitor_id)


async def create_active_monitor(manager: ActiveMonitorManager, args: Dict[str, str],
                                monitor_def: ActiveMonitorDef) -> ActiveMonitor:
    async def _run(cur):
        q = """insert into active_monitors (def_id, state, state_ts, msg) values (%s, %s, %s, %s)"""
        q_args = (monitor_def.id, 'UNKNOWN', 0, '')
        await cur.execute(q, q_args)
        _monitor_id = cur.lastrowid
        q = """insert into active_monitor_args (monitor_id, name, value) values (%s, %s, %s)"""
        for name, value in args.items():
            q_args = (_monitor_id, name, value)
            await cur.execute(q, q_args)
        return _monitor_id

    monitor_def.validate_monitor_args(args)
    monitor_id = await manager.dbcon.transact(_run)
    monitor = ActiveMonitor(monitor_id, args, monitor_def, 'UNKNOWN', state_ts=0, msg='', alert_id=None,
                            checks_enabled=True, alerts_enabled=True, manager=manager)
    log.msg('Created active monitor %s' % monitor)
    manager.add_monitor(monitor)
    return monitor


async def create_active_monitor_def(manager: ActiveMonitorManager, name: str, description: str,
                                    active: bool, cmdline_filename: str, cmdline_args_tmpl: str,
                                    description_tmpl: str) -> ActiveMonitorDef:
    q = """insert into active_monitor_defs
        (name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl)
        values (%s, %s, %s, %s, %s, %s)"""
    q_args = (name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl)
    monitor_def_id = await manager.dbcon.operation(q, q_args)
    monitor_def = ActiveMonitorDef(monitor_def_id, name, active, cmdline_filename,
                                   cmdline_args_tmpl, description_tmpl, [], manager)
    log.msg('Created active monitor def %s' % monitor_def)
    manager.monitor_defs[monitor_def.id] = monitor_def
    return monitor_def


async def create_active_monitor_def_arg(manager: ActiveMonitorManager, monitor_def_id: int, name: str,
                                        display_name: str,
                                        description: str, required: bool, default_value: str) -> ActiveMonitorDef:
    monitor_def = manager.monitor_defs[monitor_def_id]
    q = """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (%s, %s, %s, %s, %s, %s)"""
    q_args = (name, display_name, description, required, default_value)
    arg_id = manager.dbcon.operation(q, q_args)
    arg = {
        'id': arg_id,
        'name': name,
        'required': required,
        'default_value': default_value,
    }  # type: Dict[str, Any]
    monitor_def.arg_spec.append(arg)
    log.msg('Created active monitor def arg %s %s=%s' % (monitor_def, name, default_value))
    return monitor_def


async def remove_monitor_def_from_db(dbcon: DBConnection, monitor_def_id: int):
    """Remove all traces of a monitor def from the database."""

    def _run(cur):
        q_args = (monitor_def_id,)
        q = """delete from active_monitor_defs where id=%s"""
        cur.operation(q, q_args)
        q = """delete from active_monitor_def_args where active_monitor_def_id=%s"""
        cur.operation(q, q_args)

    await dbcon.transact(_run)


async def add_monitor_def_arg_to_db(dbcon: DBConnection, monitor_def_id: int, name: str, display_name: str,
                                    description: str, required: bool, default_value: str) -> int:
    q = """insert into active_monitor_def_args
    (active_monitor_def_id, name, display_name, description, required, default_value)
    values (%s, %s, %s, %s, %s, %s)"""
    q_args = (monitor_def_id, name, display_name, description, required, default_value)
    arg_id = await dbcon.operation(q, q_args)
    return arg_id


async def update_monitor_def_arg_in_db(dbcon: DBConnection, arg_id: int, name: str, display_name: str,
                                       description: str, required: bool, default_value: str):
    q = """update active_monitor_def_args
        set name=%s, display_name=%s, description=%s, required=%s, default_value=%s
        where id=%s"""
    q_args = (name, display_name, description, required, default_value, arg_id)
    await dbcon.operation(q, q_args)


async def delete_monitor_def_arg_from_db(dbcon: DBConnection, arg_id: int):
    q = """delete from active_monitor_def_args where id=%s"""
    q_args = (arg_id,)
    await dbcon.operation(q, q_args)


def get_monitor_def_by_name(manager: ActiveMonitorManager, name: str) -> Optional[ActiveMonitorDef]:
    """Get a monitor definition based on its name."""
    ret = None
    for monitor_def in manager.monitor_defs.values():
        if monitor_def.name == name:
            ret = monitor_def
            break
    return ret
