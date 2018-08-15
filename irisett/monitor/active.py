"""Irisett active monitoring (service checks).

This is the core of irisetts monitoring. Monitor definitions and monitors
are both loaded into memory and kept there so they must be updated both
in the database and in memory.

A monitor managed is used for scheduling monitor service checks and starting
each check.
"""

from typing import Dict, Any, List, Union, Optional, Iterator, Tuple, cast
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
    event,
    object_models,
    sql,
)
from irisett.monitor import active_sql

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
    monitor_def_models = await active_sql.get_all_active_monitor_defs(manager.dbcon)
    monitor_def_args_map = await map_monitor_def_args_to_monitor_defs(manager.dbcon)
    monitor_defs = {}
    for monitor_def in monitor_def_models:
        monitor_defs[monitor_def.id] = ActiveMonitorDef(
            monitor_def.id, monitor_def.name, monitor_def.active, monitor_def.cmdline_filename,
            monitor_def.cmdline_args_tmpl, monitor_def.description_tmpl,
            monitor_def_args_map.get(monitor_def.id, []), manager)
    return monitor_defs


async def map_monitor_def_args_to_monitor_defs(
        dbcon: DBConnection) -> Dict[int, List[object_models.ActiveMonitorDefArg]]:
    """Get active monitor def args and map them to active monitor defs.

    List all arguments, return a dict that maps the arguments to monitor def ids.
    """
    ret = {}  # type: Dict[int, List[object_models.ActiveMonitorDefArg]]
    for arg in await active_sql.get_all_active_monitor_def_args(dbcon):
        if arg.active_monitor_def_id not in ret:
            ret[arg.active_monitor_def_id] = []
        ret[arg.active_monitor_def_id].append(arg)
    return ret


async def load_monitors(manager: 'ActiveMonitorManager') -> Dict[int, 'ActiveMonitor']:
    """Load all monitors.

    Return a dict mapping monitor id to monitor instance.
    """
    monitor_models = await active_sql.get_all_active_monitors(manager.dbcon)
    monitor_args_map = await map_monitor_args_to_monitors(manager.dbcon)
    monitors = {}
    for monitor in monitor_models:
        monitor_def = manager.monitor_defs[monitor.def_id]
        monitors[monitor.id] = ActiveMonitor(
            monitor.id,
            monitor_args_map.get(monitor.id, {}),
            monitor_def,
            monitor.state,
            monitor.state_ts,
            monitor.msg,
            monitor.alert_id,
            monitor.checks_enabled,
            monitor.alerts_enabled,
            manager)
    return monitors


async def map_monitor_args_to_monitors(
        dbcon: DBConnection) -> Dict[int, Dict[str, str]]:
    """Get active monitor args and map them to active monitors.

    List all arguments, return a dict that maps the arguments to monitor ids.
    """
    ret = {}  # type: Dict[int, Dict[str, str]]
    for arg in await active_sql.get_all_active_monitor_args(dbcon):
        if arg.monitor_id not in ret:
            ret[arg.monitor_id] = {}
        ret[arg.monitor_id][arg.name] = arg.value
    return ret


class ActiveMonitorManager:
    """The manager and main loop for active monitors.

    The monitor manager keeps track of monitor definitions and monitors.
    It does the initial scheduling of monitor jobs and supports the loop that
    keep monitor jobs running.
    """

    def __init__(self, dbcon: DBConnection, notification_manager: NotificationManager,
                 max_concurrent_jobs: int, *, debug_mode: bool = False, loop: asyncio.AbstractEventLoop = None) -> None:
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

    async def initialize(self) -> None:
        """Load all data required for the managed main loop to run.

        This can't be called from __init__ as it is an async call.
        """
        await remove_deleted_monitors(self.dbcon)
        self.monitor_defs = await load_monitor_defs(self)
        self.monitors = await load_monitors(self)
        log.msg('Loaded %d active monitor definitions' % (len(self.monitor_defs)))
        log.msg('Loaded %d active monitors' % (len(self.monitors)))

    def start(self) -> None:
        for monitor in self.monitors.values():
            start_delay = 0
            if not self.debug_mode:
                start_delay = random.randint(1, DEFAULT_MONITOR_INTERVAL)
            self.schedule_monitor(monitor, start_delay)
        # self.scheduleMonitor(monitor, 0)
        self.check_missing_schedules()

    def check_missing_schedules(self) -> None:
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

    def run_monitor(self, monitor_id: int) -> None:
        """Run self._run_monitor.

        _run_monitor is a coroutine and can't be called directly from
        loop.call_later.
        """
        asyncio.ensure_future(self._run_monitor(monitor_id))

    async def _run_monitor(self, monitor_id: int) -> None:
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

    def schedule_monitor(self, monitor: 'ActiveMonitor', interval: int) -> None:
        log.debug('Scheduling %s for %ds' % (monitor, interval))
        if monitor.scheduled_job:
            try:
                monitor.scheduled_job.cancel()
            except ValueError:
                pass
        monitor.scheduled_job = self.loop.call_later(interval, self.run_monitor, monitor.id)
        monitor.scheduled_job_ts = time.time() + interval
        event.running('SCHEDULE_ACTIVE_MONITOR', monitor=monitor, interval=interval)

    def add_monitor(self, monitor: 'ActiveMonitor') -> None:
        self.monitors[monitor.id] = monitor
        self.schedule_monitor(monitor, 0)


class MonitorTemplateCache:
    """A simple cache for monitor values.

    We cache values that have been expanded from jinja templates. We don't
    want to keep re-expanding these all the time, but they need to be
    updated for example when the template is changed in the monitor def.

    One template cache instance is stored for each monitor def, values are
    flushed when needed for example when a monitor def or monitor is
    updated.
    """

    def __init__(self) -> None:
        self.cache = {}  # type: Dict[int, Any]

    def get(self, monitor: 'ActiveMonitor', name: str) -> Any:
        ret = None
        monitor_values = self.cache.get(monitor.id)
        if monitor_values:
            ret = monitor_values.get(name)
        return ret

    def set(self, monitor: 'ActiveMonitor', name: str, value: Any) -> Any:
        if monitor.id not in self.cache:
            self.cache[monitor.id] = {}
        self.cache[monitor.id][name] = value
        return value

    def flush_all(self) -> None:
        self.cache = {}

    def flush_monitor(self, monitor: 'ActiveMonitor') -> None:
        if monitor.id in self.cache:
            del self.cache[monitor.id]


class ActiveMonitorDef(log.LoggingMixin):
    def __init__(self, id: int, name: str, active: bool, cmdline_filename: str, cmdline_args_tmpl: str,
                 description_tmpl: str, arg_spec: List[object_models.ActiveMonitorDefArg],
                 manager: ActiveMonitorManager) -> None:
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
        self.tmpl_cache = MonitorTemplateCache()

    def __str__(self) -> str:
        return '<ActiveMonitorDef(%s/%s)>' % (self.id, self.cmdline_filename)

    def get_arg_with_name(self, name: str) -> Optional[object_models.ActiveMonitorDefArg]:
        match = None
        for arg in self.arg_spec:
            if arg.name == name:
                match = arg
                break
        return match

    def expand_monitor_args(self, monitor_args: Dict[str, str]) -> List[str]:
        """Expand the monitors command line arguments.

        The monitor command line arguments are based on monitor def
        cmdline_args_tmpl template.
        """
        args = {a.name: a.default_value for a in self.arg_spec}
        args.update(monitor_args)
        expanded = self.jinja_cmdline_args.render(**args)
        ret = shlex.split(expanded)  # Supports "" splitting etc.
        return ret

    def expand_monitor_description(self, monitor_args: Dict[str, str]) -> str:
        """Return a monitor description based on this monitor def.

        This uses the monitor def description_tmpl to create a useful
        monitor description based on the monitors (commandline) arguments
        and the monitor defs default values.

        This is used when sending monitor notifications.
        """
        args = {a.name: a.default_value for a in self.arg_spec}
        args.update(monitor_args)
        description = self.jinja_description_tmpl.render(**args)
        return description

    def validate_monitor_args(self, monitor_args: Dict[str, str], permit_missing: bool = False) -> bool:
        if not permit_missing:
            for arg in self.arg_spec:
                if arg.required and arg.name not in monitor_args:
                    raise errors.InvalidArguments('missing argument %s' % arg.name)
        arg_name_set = {a.name for a in self.arg_spec}
        for key, value in monitor_args.items():
            if key not in arg_name_set:
                raise errors.InvalidArguments('invalid argument %s' % key)
        return True

    async def delete(self) -> None:
        for _ in self.iter_monitors():
            raise errors.IrisettError('can\'t remove active monitor def that is in use')
        del self.manager.monitor_defs[self.id]
        self.tmpl_cache.flush_all()
        await active_sql.delete_active_monitor_def(self.manager.dbcon, self.id)

    async def update(self, update_params: Dict[str, Any]) -> None:
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
        if 'description_tmpl' in update_params:
            self.description_tmpl = update_params['description_tmpl']
            self.jinja_description_tmpl = jinja2.Template(self.description_tmpl)
        self.tmpl_cache.flush_all()
        queries = []
        for param in ['name', 'description', 'active', 'cmdline_filename', 'cmdline_args_tmpl', 'description_tmpl']:
            if param in update_params:
                q = """update active_monitor_defs set %s=%%s where id=%%s""" % param
                q_args = (update_params[param], self.id)
                queries.append(q, q_args)
        await self.manager.dbcon.multi_operation(queries)

    def iter_monitors(self) -> Iterator['ActiveMonitor']:
        """List all monitors that use this monitor def."""
        for monitor in self.manager.monitors.values():
            if monitor.monitor_def.id == self.id:
                yield monitor

    async def set_arg(self, new_arg: object_models.ActiveMonitorDefArg) -> None:
        existing_arg = self.get_arg_with_name(new_arg.name)
        if existing_arg:
            existing_arg.name = new_arg.name
            existing_arg.required = new_arg.required
            existing_arg.default_value = new_arg.default_value
            await active_sql.update_active_monitor_def_arg(self.manager.dbcon, existing_arg)
        else:
            new_arg.id = await active_sql.create_active_monitor_def_arg(self.manager.dbcon, new_arg)
            self.arg_spec.append(new_arg)
        self.tmpl_cache.flush_all()

    async def delete_arg(self, name: str) -> None:
        arg = self.get_arg_with_name(name)
        if arg:
            self.arg_spec.remove(arg)
            self.tmpl_cache.flush_all()
            await active_sql.delete_active_monitor_def_arg(self.manager.dbcon, arg.id)

    async def get_notify_data(self) -> Dict[str, str]:
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
    monitor_type = 'active'

    def __init__(self, id: int, args: Dict[str, str], monitor_def: ActiveMonitorDef, state: str, state_ts: float,
                 msg: str, alert_id: Union[int, None], checks_enabled: bool,
                 alerts_enabled: bool, manager: ActiveMonitorManager) -> None:
        self.id = id
        self.args = args
        self.monitor_def = monitor_def
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
        self.scheduled_job_ts = 0.0
        event.running('CREATE_ACTIVE_MONITOR', monitor=self)
        stats.inc('num_monitors', 'ACT_MON')

    def __str__(self) -> str:
        return '<ActiveMonitor(%s/%s/%s)>' % (self.id, self.state, self.last_check_state)

    def get_description(self) -> str:
        """Get a description for this monitor.

        The description is created from a template in the monitor defintion.
        """
        ret = self.monitor_def.tmpl_cache.get(self, 'description')
        if not ret:
            ret = self.monitor_def.tmpl_cache.set(
                self, 'description', self.monitor_def.expand_monitor_description(self.args))
        return ret

    def get_expanded_args(self) -> List[str]:
        """Get the expanded service check arguments for this monitor.

        The arguments are created from a template in the monitor definition
        """
        ret = self.monitor_def.tmpl_cache.get(self, 'args')
        if not ret:
            ret = self.monitor_def.tmpl_cache.set(
                self, 'args', self.monitor_def.expand_monitor_args(self.args))
        return ret

    async def run(self) -> bool:
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
        return True

    async def _run(self) -> None:
        if self._pending_reset:
            await self.reset_monitor()
        if not self.checks_enabled:
            self.log_debug('skipping monitor check, disabled')
            self.manager.schedule_monitor(self, DEFAULT_MONITOR_INTERVAL)
            return
        expanded_args = self.get_expanded_args()
        self.log_debug('monitoring: %s %s' % (self.monitor_def.cmdline_filename, expanded_args))
        event.running('RUN_ACTIVE_MONITOR', monitor=self)
        # noinspection PyUnusedLocal
        msg = ''  # type: Union[str, bytes]
        try:
            _msg = await nagios.run_plugin(self.monitor_def.cmdline_filename, expanded_args, 30)
            msg, perf = _msg
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
            msg = cast(bytes, msg)
            msg = msg.decode('utf-8', errors='ignore')
        msg = cast(str, msg)
        self.msg = msg
        self.update_consecutive_checks(check_state)
        await self.handle_check_result(check_state, msg)
        self.log_debug('monitoring complete')
        if self.deleted:
            await self._purge()

    async def handle_check_result(self, check_state: str, msg: str) -> None:
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
        event.running('ACTIVE_MONITOR_CHECK_RESULT', monitor=self, check_state=check_state, msg=msg)

    async def _set_monitor_checks_disabled(self) -> None:
        self.state = 'UNKNOWN'
        self.state_ts = int(time.time())
        self.msg = ''

    async def state_change(self, new_state: str, msg: str) -> None:
        event.running('ACTIVE_MONITOR_STATE_CHANGE', monitor=self, new_state=new_state)
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

    async def notify_state_change(self, prev_state: str, prev_state_ts: float) -> None:
        if not self.alerts_enabled:
            self.log_debug('skipping alert notifications, disabled')
            return
        contacts = await contact.get_contact_dict_for_active_monitor(
            self.manager.dbcon, self.id)
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
        asyncio.ensure_future(
            self.manager.notification_manager.send_notification(contacts, tmpl_data))

    def update_consecutive_checks(self, state: str) -> None:
        """Update the counter for consecutive checks with the same result."""
        if state == self.last_check_state:
            self.consecutive_checks += 1
        else:
            self.consecutive_checks = 0
        self.last_check_state = state

    async def set_up(self) -> None:
        """Set a monitor up (in the database)."""

        async def _run(cur: sql.Cursor) -> None:
            if self.alert_id:
                await self.txn_close_alert(cur)
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)

    async def set_down(self) -> None:
        """Set a monitor down (in the database)."""

        async def _run(cur: sql.Cursor) -> None:
            await self.txn_create_alert(cur)
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)

    async def set_unknown(self) -> None:
        """Set a monitor in unknown state (in the database)."""

        async def _run(cur: sql.Cursor) -> None:
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)

    async def txn_create_alert(self, cur: sql.Cursor) -> None:
        q = """insert into active_monitor_alerts (monitor_id, start_ts, end_ts, alert_msg) values (%s, %s, %s, %s)"""
        q_args = (self.id, self.state_ts, 0, self.msg)
        await cur.execute(self.manager.dbcon.prep_query(q), q_args)
        self.alert_id = cur.lastrowid

    async def txn_close_alert(self, cur: sql.Cursor) -> None:
        q = """update active_monitor_alerts set end_ts=%s where id=%s"""
        q_args = (self.state_ts, self.alert_id)
        await cur.execute(self.manager.dbcon.prep_query(q), q_args)
        self.alert_id = None

    async def txn_save_state(self, cur: sql.Cursor) -> None:
        q = """update active_monitors set state=%s, state_ts=%s, msg=%s, alert_id=%s where id=%s"""
        q_args = (self.state, self.state_ts, self.msg, self.alert_id, self.id)
        await cur.execute(self.manager.dbcon.prep_query(q), q_args)

    async def delete(self) -> None:
        """Delete an existing monitor.

        If the monitor is not running it will be removed immediately.
        If the monitor is running it will be remove when the run is complete.
        """
        if self.deleted:
            return
        self.log_msg('deleting monitor')
        event.running('DELETE_ACTIVE_MONITOR', monitor=self)
        self.deleted = True
        if self.id in self.manager.monitors:
            del self.manager.monitors[self.id]
        if self.monitoring:
            q = """update active_monitors set deleted=%s where id=%s"""
            q_args = (True, self.id)
            await self.manager.dbcon.operation(q, q_args)
        else:
            await self._purge()

    async def _purge(self) -> None:
        """Remove a monitor from the database."""
        self.log_msg('purging deleted monitor')
        stats.dec('num_monitors', 'ACT_MON')
        self.monitor_def.tmpl_cache.flush_monitor(self)
        await active_sql.delete_active_monitor(self.manager.dbcon, self.id)

    async def update_args(self, args: Dict[str, str]) -> None:
        self.log_msg('updating monitor arguments')
        self.monitor_def.validate_monitor_args(args)
        self.args = args
        self.monitor_def.tmpl_cache.flush_monitor(self)
        queries = []
        q = """delete from active_monitor_args where monitor_id=%s"""
        q_args = (self.id,)  # type: Tuple
        queries.append((q, q_args))
        q = """insert into active_monitor_args (monitor_id, name, value) values (%s, %s, %s)"""
        for name, value in args.items():
            q_args = (self.id, name, value)
            queries.append((q, q_args))
        await self.manager.dbcon.multi_operation(queries)

    async def set_checks_enabled_status(self, checks_enabled: bool) -> None:
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

    async def set_alerts_enabled_status(self, alerts_enabled: bool) -> None:
        if self.alerts_enabled == alerts_enabled:
            return
        self.log_debug('settings monitor alerts to %s' % alerts_enabled)
        self.alerts_enabled = alerts_enabled
        q = """update active_monitors set alerts_enabled=%s where id=%s"""
        q_args = (alerts_enabled, self.id)
        await self.manager.dbcon.operation(q, q_args)

    def schedule_immediately(self) -> None:
        """Schedule a check for this monitor ASAP."""
        if not self.monitoring and not self.deleted:
            self.log_msg('Forcing immediate check by request')
            self.manager.schedule_monitor(self, 5)

    async def get_metadata(self) -> Dict[str, str]:
        ret = await get_metadata(self.manager.dbcon, 'active_monitor', self.id)
        return ret

    async def reset_monitor(self) -> None:
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

        async def _run(cur: sql.Cursor) -> None:
            if self.alert_id:
                await self.txn_close_alert(cur)
            await self.txn_save_state(cur)

        await self.manager.dbcon.transact(_run)


async def remove_deleted_monitors(dbcon: DBConnection) -> None:
    """Remove any monitors that have previously been set as deleted.

    This runs once every time the server starts up.
    """
    log.msg('Purging all deleted active monitors')
    q = """select id from active_monitors where deleted=%s"""
    rows = await dbcon.fetch_all(q, (True,))
    for monitor_id in rows:
        await active_sql.delete_active_monitor(dbcon, monitor_id)


async def create_active_monitor(manager: ActiveMonitorManager, args: Dict[str, str],
                                monitor_def: ActiveMonitorDef) -> ActiveMonitor:
    monitor_def.validate_monitor_args(args)
    monitor_id = await active_sql.create_active_monitor(manager.dbcon, monitor_def.id, args)
    monitor = ActiveMonitor(monitor_id, args, monitor_def, 'UNKNOWN', state_ts=0, msg='', alert_id=None,
                            checks_enabled=True, alerts_enabled=True, manager=manager)
    log.msg('Created active monitor %s' % monitor)
    manager.add_monitor(monitor)
    return monitor


async def create_active_monitor_def(
        manager: ActiveMonitorManager, model: object_models.ActiveMonitorDef) -> ActiveMonitorDef:
    monitor_def_id = await active_sql.create_active_monitor_def(
        manager.dbcon, model)
    monitor_def = ActiveMonitorDef(monitor_def_id, model.name, model.active, model.cmdline_filename,
                                   model.cmdline_args_tmpl, model.description_tmpl, [], manager)
    log.msg('Created active monitor def %s' % monitor_def)
    manager.monitor_defs[monitor_def.id] = monitor_def
    return monitor_def


def get_monitor_def_by_name(manager: ActiveMonitorManager, name: str) -> Optional[ActiveMonitorDef]:
    """Get a monitor definition based on its name."""
    ret = None
    for monitor_def in manager.monitor_defs.values():
        if monitor_def.name == name:
            ret = monitor_def
            break
    return ret
