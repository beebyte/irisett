"""Web views."""

from typing import Any, Dict, List
from aiohttp import web
# noinspection PyPackageRequirements
import aiohttp_jinja2

from irisett import (
    metadata,
    stats,
    contact,
    log,
    object_models,
)

from irisett.webmgmt import (
    errors,
    ws_event_proxy,
)


class IndexView(web.View):
    @aiohttp_jinja2.template('index.html')
    async def get(self) -> Dict[str, Any]:
        context = {'section': 'index'}  # type: Dict[str, Any]
        return context


class StatisticsView(web.View):
    @aiohttp_jinja2.template('statistics.html')
    async def get(self) -> Dict[str, Any]:
        context = {
            'section': 'statistics',
            'stats': stats.get_stats(),
        }
        return context


class ActiveAlertsView(web.View):
    @aiohttp_jinja2.template('active_alerts.html')
    async def get(self) -> Dict[str, Any]:
        am_manager = self.request.app['active_monitor_manager']
        active_monitors = am_manager.monitors
        context = {
            'section': 'alerts',
            'subsection': 'active_alerts',
            'alerting_active_monitors': [m for m in active_monitors.values() if m.state == 'DOWN']
        }
        return context


class AlertHistoryView(web.View):
    @aiohttp_jinja2.template('alert_history.html')
    async def get(self) -> Dict[str, Any]:
        alerts = await self._get_active_monitor_alerts()
        context = {
            'section': 'alerts',
            'subsection': 'alert_history',
            'alerts': alerts,
        }
        return context

    async def _get_active_monitor_alerts(self) -> List[object_models.ActiveMonitorAlert]:
        am_manager = self.request.app['active_monitor_manager']
        q = """select id, monitor_id, start_ts, end_ts, alert_msg from active_monitor_alerts order by start_ts desc"""
        alerts = []  # type: List[object_models.ActiveMonitorAlert]
        for row in await self.request.app['dbcon'].fetch_all(q):
            alert = object_models.ActiveMonitorAlert(*row)
            alert.monitor = am_manager.monitors.get(alert.monitor_id)
            alerts.append(alert)
        return alerts


class EventsView(web.View):
    """Events websocket proxy.

    This just supplies the HTML and javascript to connect the the websocket
    handler.
    """

    @aiohttp_jinja2.template('events.html')
    async def get(self) -> Dict[str, Any]:
        context = {'section': 'events'}  # type: Dict[str, Any]
        return context


async def events_websocket_handler(request):
    """GET view for events websocket.

    All the work is done in the WSEventProxy class.
    """
    proxy = ws_event_proxy.WSEventProxy(request)
    log.debug('Starting event websocket session')
    await proxy.run()
    log.debug('Ending event websocket session')
    return proxy.ws


class ListActiveMonitorsView(web.View):
    @aiohttp_jinja2.template('list_active_monitors.html')
    async def get(self) -> Dict[str, Any]:
        am_manager = self.request.app['active_monitor_manager']
        active_monitors = am_manager.monitors
        context = {
            'section': 'active_monitors',
            'active_monitors': active_monitors.values(),
        }
        return context


class DisplayActiveMonitorView(web.View):
    @aiohttp_jinja2.template('display_active_monitor.html')
    async def get(self) -> Dict[str, Any]:
        monitor_id = int(self.request.match_info['id'])
        am_manager = self.request.app['active_monitor_manager']
        monitor = am_manager.monitors[monitor_id]
        context = {
            'section': 'active_monitors',
            'notification_msg': self.request.rel_url.query.get('notification_msg'),
            'monitor': monitor,
            'metadata': await metadata.get_metadata(self.request.app['dbcon'], 'active_monitor', monitor_id),
            'contacts': await contact.get_contacts_for_active_monitor(self.request.app['dbcon'], monitor_id),
        }
        return context


async def run_active_monitor_view(request):
    """GET view to run an active monitor immediately."""
    monitor_id = int(request.match_info['id'])
    am_manager = request.app['active_monitor_manager']
    monitor = am_manager.monitors[monitor_id]
    monitor.schedule_immediately()
    return web.HTTPFound('/active_monitor/%s/?notification_msg=Monitor job scheduled' % monitor_id)


def parse_active_monitor_def_row(row):
    """Parse an SQL row for an active monitor def."""
    ret = {
        'id': row[0],
        'name': row[1],
        'description': row[2],
        'active': row[3],
        'cmdline_filename': row[4],
        'cmdline_args_tmpl': row[5],
        'description_tmpl': row[6],
    }
    return ret


class ListActiveMonitorDefsView(web.View):
    @aiohttp_jinja2.template('list_active_monitor_defs.html')
    async def get(self) -> Dict[str, Any]:
        context = {
            'section': 'active_monitor_defs',
            'monitor_defs': await self._get_active_monitor_defs(),
        }
        return context

    async def _get_active_monitor_defs(self):
        q = '''select id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl
            from active_monitor_defs'''
        rows = await self.request.app['dbcon'].fetch_all(q)
        ret = []
        for row in rows:
            active_monitor_def = parse_active_monitor_def_row(row)
            ret.append(active_monitor_def)
        return ret


class DisplayActiveMonitorDefView(web.View):
    @aiohttp_jinja2.template('display_active_monitor_def.html')
    async def get(self) -> Dict[str, Any]:
        monitor_def_id = int(self.request.match_info['id'])
        am_manager = self.request.app['active_monitor_manager']
        monitor_def = am_manager.monitor_defs[monitor_def_id]
        sql_monitor_def = await self._get_active_monitor_def(monitor_def_id)
        context = {
            'section': 'active_monitor_def',
            'monitor_def': monitor_def,
            'sql_monitor_def': sql_monitor_def,
        }
        return context

    async def _get_active_monitor_def(self, monitor_def_id):
        q = '''select id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl
            from active_monitor_defs where id=%s'''
        row = await self.request.app['dbcon'].fetch_row(q, (monitor_def_id,))
        ret = parse_active_monitor_def_row(row)
        ret['args'] = await self._get_active_monitor_def_args(monitor_def_id)
        return ret

    async def _get_active_monitor_def_args(self, monitor_def_id):
        q = '''select id, name, display_name, description, required, default_value
            from active_monitor_def_args where active_monitor_def_id=%s'''
        rows = await self.request.app['dbcon'].fetch_all(q, (monitor_def_id,))
        ret = []
        for row in rows:
            arg = {
                'id': row[0],
                'name': row[1],
                'display_name': row[2],
                'description': row[3],
                'required': row[4],
                'default_value': row[5],
            }
            ret.append(arg)
        return ret


class ListContactsView(web.View):
    @aiohttp_jinja2.template('list_contacts.html')
    async def get(self) -> Dict[str, Any]:
        context = {
            'section': 'contacts',
            'contacts': await contact.get_all_contacts(self.request.app['dbcon']),
        }
        return context


class DisplayContactView(web.View):
    @aiohttp_jinja2.template('display_contact.html')
    async def get(self) -> Dict[str, Any]:
        c = await contact.get_contact(self.request.app['dbcon'], int(self.request.match_info['id']))
        if not c:
            raise errors.NotFound()
        context = {
            'section': 'contacts',
            'contact': c,
        }
        return context
