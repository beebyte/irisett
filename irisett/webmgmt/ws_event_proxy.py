"""Websocket proxy for irisett events.

Setup a websocket listener that sends irisett events over the websocket
as they arrive.
"""

import asyncio
import aiohttp
import json
from aiohttp import web

from irisett import (
    event,
)


class WSEventProxy:
    def __init__(self, request):
        self.request = request
        self.ws = web.WebSocketResponse()
        self.running = False
        self.client_started = False
        self.listener = None  # type: event.EventListener

    async def run(self):
        await self.ws.prepare(self.request)
        self.running = True
        self.listener = event.listen(self._handle_events)
        try:
            await asyncio.gather(
                self._ws_read(),
            )
        except (asyncio.CancelledError, asyncio.TimeoutError, aiohttp.ClientDisconnectedError):
            pass
        finally:
            event.stop_listening(self.listener)
            self.listener = False
            if not self.ws.closed:
                self.ws.close()

    async def _ws_read(self):
        # noinspection PyTypeChecker
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data['cmd'] == 'start':
                    self.client_started = True
                elif data['cmd'] == 'stop':
                    self.client_started = False
                elif data['cmd'] == 'event_filter':
                    self.listener.set_event_filter(data['filter'])
                elif data['cmd'] == 'active_monitor_filter':
                    self.listener.set_active_monitor_filter(data['filter'])
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
            self.ws.send_json(msg)
