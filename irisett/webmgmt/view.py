"""Webapi views."""

from typing import Any, Dict
from aiohttp import web
import aiohttp_jinja2

from irisett import (
    metadata,
)

class IndexView(web.View):
    @aiohttp_jinja2.template('index.html')
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
            'metadata': await metadata.get_metadata(self.request.app['dbcon'], 'active_monitor', monitor_id)
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
