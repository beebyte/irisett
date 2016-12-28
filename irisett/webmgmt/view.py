"""Webapi views."""

from typing import Any, Dict
import asyncio
import json
from aiohttp import web
import aiohttp
import aiohttp_jinja2

from irisett import (
    metadata,
    stats,
    contact,
    event,
    log,
)

from irisett.webmgmt import errors


class IndexView(web.View):
    @aiohttp_jinja2.template('index.html')
    async def get(self) -> Dict[str, Any]:
        context = {}
        return context


class StatisticsView(web.View):
    @aiohttp_jinja2.template('statistics.html')
    async def get(self) -> Dict[str, Any]:
        context = {
            'stats': stats.get_stats(),
        }
        return context


class AlertsView(web.View):
    @aiohttp_jinja2.template('alerts.html')
    async def get(self) -> Dict[str, Any]:
        am_manager = self.request.app['active_monitor_manager']
        active_monitors = am_manager.monitors
        context = {
            'alerting_active_monitors': [m for m in active_monitors.values() if m.state == 'DOWN']
        }
        return context


class EventsView(web.View):
    @aiohttp_jinja2.template('events.html')
    async def get(self) -> Dict[str, Any]:
        context = {}
        return context


class EventsWSProxy:
    def __init__(self, request):
        self.request = request
        self.ws = web.WebSocketResponse()
        self.running = False
        self.client_started = False

    async def run(self):
        await self.ws.prepare(self.request)
        self.running = True
        listener = event.listen(self._handle_events)
        try:
            await asyncio.gather(
                self._ws_read(),
            )
        except (asyncio.CancelledError, asyncio.TimeoutError, aiohttp.ClientDisconnectedError):
            pass
        finally:
            event.stop_listening(listener)
            if not self.ws.closed:
                self.ws.close()

    async def _ws_read(self):
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data['cmd'] == 'start':
                    self.client_started = True
                elif data['cmd'] == 'stop':
                    self.client_started = False
            elif msg.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR]:
                break
            else:
                break
        self.running = False

    async def _handle_events(self, listener, event_name, timestamp, data):
        if not self.client_started:
            return
        if not self.running or self.ws.closed:
            event.stop_listening(listener)
            return
        msg = {
            'event': event_name,
            'timestamp': timestamp,
        }
        if event_name == 'SCHEDULE_ACTIVE_MONITOR':
            msg['monitor_id'] = data['monitor'].id
            msg['monitor_description'] = data['monitor'].get_description()
            msg['interval'] = data['interval']
        elif event_name == 'CREATE_ACTIVE_MONITOR':
            msg['monitor_id'] = data['monitor'].id
            msg['monitor_description'] = data['monitor'].get_description()
        elif event_name == 'RUN_ACTIVE_MONITOR':
            msg['monitor_id'] = data['monitor'].id
            msg['monitor_description'] = data['monitor'].get_description()
        elif event_name == 'ACTIVE_MONITOR_CHECK_RESULT':
            msg['monitor_id'] = data['monitor'].id
            msg['monitor_description'] = data['monitor'].get_description()
            msg['check_state'] = data['check_state']
            msg['msg'] = data['msg']
        elif event_name == 'ACTIVE_MONITOR_STATE_CHANGE':
            msg['monitor_id'] = data['monitor'].id
            msg['monitor_description'] = data['monitor'].get_description()
            msg['new_state'] = data['new_state']
        elif event_name == 'DELETE_ACTIVE_MONITOR':
            msg['monitor_id'] = data['monitor'].id
            msg['monitor_description'] = data['monitor'].get_description()
        if msg:
            print('MMMMMMMMMM', msg)
            res = self.ws.send_json(msg)


async def events_websocket_handler(request):
    proxy = EventsWSProxy(request)
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
            'monitor': monitor,
            'metadata': await metadata.get_metadata(self.request.app['dbcon'], 'active_monitor', monitor_id),
            'contacts': await contact.get_contacts_for_active_monitor(self.request.app['dbcon'], monitor_id),
        }
        return context


def parse_active_monitor_def_row(row):
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
        am_manager = self.request.app['active_monitor_manager']
        context = {
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
            'contact': c,
        }
        return context
