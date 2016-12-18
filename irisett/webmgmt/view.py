"""Webapi views."""

from typing import Any, Dict
from aiohttp import web
import aiohttp_jinja2


class IndexView(web.View):
    @aiohttp_jinja2.template('index.html')
    async def get(self) -> Dict[str, Any]:
        am_manager = self.request.app['active_monitor_manager']
        active_monitors = am_manager.monitors
        context = {
            'active_monitors': active_monitors.values(),
        }
        return context


class ActiveMonitorDefView(web.View):
    @aiohttp_jinja2.template('active_monitor_def.html')
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