"""Webapi views."""

from typing import Any, Dict, List, Iterable, Optional, cast, Tuple
from aiohttp import web
import time

from irisett import (
    metadata,
    bindata,
    stats,
    utils,
)
from irisett.webapi import (
    errors,
)
from irisett.monitor.active import (
    ActiveMonitor,
    ActiveMonitorDef,
    create_active_monitor,
    create_active_monitor_def,
    get_monitor_def_by_name,
)
from irisett.contact import (
    create_contact,
    update_contact,
    delete_contact,
    contact_exists,
    add_contact_to_active_monitor,
    delete_contact_from_active_monitor,
    get_contacts_for_active_monitor,
    set_active_monitor_contacts,
)
from irisett.webapi.require import (
    require_int,
    require_str,
    require_bool,
    require_dict,
    require_list,
)


def get_request_param(request: web.Request, name: str, error_if_missing: bool = True) -> Optional[str]:
    """Get a single value from a request GET parameter.

    Optionally error if it is missing.
    """
    if name not in request.rel_url.query:
        if error_if_missing:
            raise errors.NotFound()
        else:
            return None
    ret = request.rel_url.query[name]
    return ret


class ActiveMonitorView(web.View):
    async def get(self) -> web.Response:
        if 'id' in self.request.rel_url.query:
            ids = [require_int(cast(str, get_request_param(self.request, 'id')))]
        elif 'meta_key' in self.request.rel_url.query:
            q = """select mon.id
                from active_monitors as mon, object_metadata as meta
                where meta.key=%s and meta.value=%s and meta.object_type="active_monitor" and meta.object_id=mon.id"""
            meta_key = require_str(get_request_param(self.request, 'meta_key'))
            meta_value = require_str(get_request_param(self.request, 'meta_value'))
            q_args = (meta_key, meta_value)
            res = await self.request.app['dbcon'].fetch_all(q, q_args)
            ids = [n[0] for n in res]
        else:
            q = """select id from active_monitors"""
            res = await self.request.app['dbcon'].fetch_all(q)
            ids = [n[0] for n in res]
        include_metadata = require_bool(
            get_request_param(self.request, 'include_metadata', error_if_missing=False),
            convert=True) or False
        include_alerts = require_bool(
            get_request_param(self.request, 'include_alerts', error_if_missing=False),
            convert=True) or False
        monitors = []
        for monitor_id in ids:
            monitor = self.request.app['active_monitor_manager'].monitors.get(monitor_id, None)
            if not monitor:
                continue
            data = await self._collect_monitor_data(monitor, include_metadata, include_alerts)
            monitors.append(data)
        return web.json_response(monitors)

    async def _collect_monitor_data(self, monitor: ActiveMonitor,
                                    include_metadata: bool, include_alerts: bool) -> Dict[str, Any]:
        ret = {
            'id': monitor.id,
            'state': monitor.state,
            'state_ts': monitor.state_ts,
            'state_elapsed': utils.get_display_time(time.time() - monitor.state_ts),
            'consecutive_checks': monitor.consecutive_checks,
            'last_check': monitor.last_check,
            'msg': monitor.msg,
            'alert_id': monitor.alert_id,
            'checks_enabled': monitor.checks_enabled,
            'alerts_enabled': monitor.alerts_enabled,
            'monitoring': monitor.monitoring,
            'args': monitor.args,
            'expanded_args': monitor.expanded_args,
            'monitor_description': monitor.get_description(),
            'monitor_def': {
                'id': monitor.monitor_def.id,
                'name': monitor.monitor_def.name,
                'cmdline_filename': monitor.monitor_def.cmdline_filename,
                'cmdline_args_tmpl': monitor.monitor_def.cmdline_args_tmpl,
                'description_tmpl': monitor.monitor_def.description_tmpl,
                'arg_spec': monitor.monitor_def.arg_spec,
            },
        }
        if include_metadata:
            ret['metadata'] = await monitor.get_metadata()
        if include_alerts:
            ret['alerts'] = await self._get_monitor_alerts(monitor.id)
        return ret

    async def _get_monitor_alerts(self, monitor_id):
        q = """select id, start_ts, end_ts, alert_msg
            from active_monitor_alerts where monitor_id=%s
            order by start_ts"""
        q_args = (monitor_id,)
        ret = await self.request.app['dbcon'].fetch_all(q, q_args)
        return ret

    async def post(self):
        request_data = await self.request.json()
        args = require_dict(request_data['args'], str, None)
        if request_data.get('use_monitor_def_name', False):
            monitor_def = get_monitor_def_by_name(
                self.request.app['active_monitor_manager'],
                require_str(request_data['monitor_def']))
        else:
            monitor_def = self.request.app['active_monitor_manager'].monitor_defs.get(
                require_int(request_data['monitor_def']))
        if not monitor_def:
            raise errors.InvalidData('Monitor def not found')
        monitor = await create_active_monitor(self.request.app['active_monitor_manager'], args, monitor_def)
        if not monitor:
            raise errors.InvalidData('invalid monitor arguments')
        return web.json_response(monitor.id)

    async def put(self) -> web.Response:
        if 'schedule' in self.request.rel_url.query:
            ret = await self.schedule_monitor()
        elif 'test_notification' in self.request.rel_url.query:
            ret = await self.test_notification()
        else:
            ret = await self.update_monitor()
        return ret

    async def schedule_monitor(self) -> web.Response:
        monitor = self._get_request_monitor(self.request)
        monitor.schedule_immediately()
        return web.json_response(True)

    async def test_notification(self) -> web.Response:
        monitor = self._get_request_monitor(self.request)
        await monitor.notify_state_change('UNKNOWN', abs(monitor.state_ts - (time.time() - monitor.state_ts)))
        return web.json_response(True)

    async def update_monitor(self) -> web.Response:
        request_data = await self.request.json()
        monitor = self._get_request_monitor(self.request)
        if 'args' in request_data:
            args = cast(Dict[str, str], require_dict(request_data['args']))
            await monitor.update_args(args)
        if 'checks_enabled' in request_data:
            await monitor.set_checks_enabled_status(cast(bool, require_bool(request_data['checks_enabled'])))
        if 'alerts_enabled' in request_data:
            await monitor.set_alerts_enabled_status(cast(bool, require_bool(request_data['alerts_enabled'])))
        return web.json_response(True)

    async def delete(self) -> web.Response:
        monitor = self._get_request_monitor(self.request)
        await monitor.delete()
        return web.json_response(True)

    # noinspection PyMethodMayBeStatic
    def _get_request_monitor(self, request: web.Request) -> ActiveMonitor:
        monitor_id = require_int(cast(str, get_request_param(request, 'id')))
        monitor = request.app['active_monitor_manager'].monitors.get(monitor_id, None)
        if not monitor:
            raise errors.NotFound()
        return monitor


class ActiveMonitorAlertView(web.View):
    async def get(self) -> web.Response:
        # noinspection PyUnusedLocal
        q_args = ()  # type: Tuple
        if 'monitor_id' in self.request.rel_url.query:
            if 'only_active' in self.request.rel_url.query:
                q = """select
                    id, monitor_id, start_ts, end_ts, alert_msg
                    from active_monitor_alerts
                    where monitor_id=%s and end_ts=0
                    order by start_ts desc"""
            else:
                q = """select
                    id, monitor_id, start_ts, end_ts, alert_msg
                    from active_monitor_alerts
                    where monitor_id=%s
                    order by start_ts desc"""
            monitor_id = require_int(get_request_param(self.request, 'monitor_id'))
            q_args = (monitor_id,)
            ret = await self._get_alerts(q, q_args)
        elif 'meta_key' in self.request.rel_url.query:
            if 'only_active' in self.request.rel_url.query:
                q = """select alert.id, alert.monitor_id, alert.start_ts, alert.end_ts, alert.alert_msg
                    from object_metadata as meta
                    left join active_monitors on active_monitors.id=meta.object_id
                    right join active_monitor_alerts as alert on alert.monitor_id=active_monitors.id
                    where meta.key=%s and meta.value=%s and meta.object_type="active_monitor" and alert.end_ts=0
                    order by alert.start_ts desc"""
            else:
                q = """select alert.id, alert.monitor_id, alert.start_ts, alert.end_ts, alert.alert_msg
                    from object_metadata as meta
                    left join active_monitors on active_monitors.id=meta.object_id
                    right join active_monitor_alerts as alert on alert.monitor_id=active_monitors.id
                    where meta.key=%s and meta.value=%s and meta.object_type="active_monitor"
                    order by alert.start_ts desc"""
            meta_key = require_str(get_request_param(self.request, 'meta_key'))
            meta_value = require_str(get_request_param(self.request, 'meta_value'))
            q_args = (meta_key, meta_value)
            ret = await self._get_alerts(q, q_args)
        else:
            if 'only_active' in self.request.rel_url.query:
                q = """select
                    id, monitor_id, start_ts, end_ts, alert_msg
                    from active_monitor_alerts
                    where end_ts=0
                    order by start_ts desc"""
            else:
                q = """select
                    id, monitor_id, start_ts, end_ts, alert_msg
                    from active_monitor_alerts
                    order by start_ts desc"""
            ret = await self._get_alerts(q, ())
        return web.json_response(ret)

    async def _get_alerts(self, q: str, q_args: Iterable[Any]) -> List[Dict[str, Any]]:
        rows = await self.request.app['dbcon'].fetch_all(q, q_args)
        ret = []
        for id, monitor_id, start_ts, end_ts, alert_msg in rows:
            alert = {
                'id': id,
                'monitor_id': monitor_id,
                'start_ts': start_ts,
                'end_ts': end_ts,
                'alert_msg': alert_msg,
                'monitor_description': '',
            }
            monitor = self.request.app['active_monitor_manager'].monitors.get(monitor_id, None)  # type: ActiveMonitor
            if monitor:
                alert['monitor_description'] = monitor.get_description()
            ret.append(alert)
        return ret


class ActiveMonitorContactView(web.View):
    async def get(self) -> web.Response:
        monitor_id = cast(int, require_int(get_request_param(self.request, 'monitor_id')))
        ret = await get_contacts_for_active_monitor(self.request.app['dbcon'], monitor_id)
        return web.json_response(ret)

    async def post(self) -> web.Response:
        request_data = await self.request.json()
        await add_contact_to_active_monitor(
            self.request.app['dbcon'],
            cast(int, require_int(request_data.get('contact_id'))),
            cast(int, require_int(request_data.get('monitor_id'))))
        return web.json_response(True)

    async def delete(self) -> web.Response:
        request_data = await self.request.json()
        await delete_contact_from_active_monitor(
            self.request.app['dbcon'],
            cast(int, require_int(request_data.get('contact_id'))),
            cast(int, require_int(request_data.get('monitor_id'))))
        return web.json_response(True)

    async def put(self) -> web.Response:
        request_data = await self.request.json()
        await set_active_monitor_contacts(
            self.request.app['dbcon'],
            cast(List[int], require_list(request_data.get('contact_ids'), int)),
            cast(int, require_int(request_data.get('monitor_id'))))
        return web.json_response(True)


class ActiveMonitorDefView(web.View):
    async def get(self) -> web.Response:
        if 'id' in self.request.rel_url.query:
            ret = await self.get_monitor_def()
        else:
            ret = await self.list_monitor_defs()
        return ret

    async def get_monitor_def(self):
        monitor_def = self._get_request_monitor_def(self.request)
        q_args = (monitor_def.id,)
        q = """select
            id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl
            from active_monitor_defs where id=%s"""
        rows = await self.request.app['dbcon'].fetch_all(q, q_args)
        monitor_def = self._make_monitor_def_from_row(rows[0])
        q = """select
            id, active_monitor_def_id, name, display_name, description, required, default_value
            from active_monitor_def_args where active_monitor_def_id=%s"""
        rows = await self.request.app['dbcon'].fetch_all(q, q_args)
        for row in rows:
            arg = self._make_monitor_def_arg_from_row(row)
            monitor_def['arg_def'].append(arg)
        return web.json_response([monitor_def])

    async def list_monitor_defs(self):
        q = """select
            id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl
            from active_monitor_defs"""
        defs = []
        def_dict = {}
        rows = await self.request.app['dbcon'].fetch_all(q)
        for row in rows:
            monitor_def = self._make_monitor_def_from_row(row)
            defs.append(monitor_def)
            def_dict[monitor_def['id']] = monitor_def
        q = """select
            id, active_monitor_def_id, name, display_name, description, required, default_value
            from active_monitor_def_args"""
        rows = await self.request.app['dbcon'].fetch_all(q)
        for row in rows:
            arg = self._make_monitor_def_arg_from_row(row)
            def_dict[row[1]]['arg_def'].append(arg)
        return web.json_response([defs])

    # noinspection PyMethodMayBeStatic
    def _make_monitor_def_from_row(self, row):
        id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl = row
        monitor_def = {
            'id': id,
            'name': name,
            'description': description,
            'active': active,
            'cmdline_filename': cmdline_filename,
            'cmdline_args_tmpl': cmdline_args_tmpl,
            'description_tmpl': description_tmpl,
            'arg_def': []
        }
        return monitor_def

    # noinspection PyMethodMayBeStatic
    def _make_monitor_def_arg_from_row(self, row):
        id, active_monitor_def_id, name, display_name, description, required, default_value = row
        arg = {
            'id': id,
            'name': name,
            'display_name': display_name,
            'description': description,
            'required': required,
            'default_value': default_value,
        }
        return arg

    async def post(self) -> web.Response:
        request_data = await self.request.json()
        monitor_def = await create_active_monitor_def(
            self.request.app['active_monitor_manager'],
            cast(str, require_str(request_data['name'])),
            cast(str, require_str(request_data['description'])),
            cast(bool, require_bool(request_data['active'])),
            cast(str, require_str(request_data['cmdline_filename'])),
            cast(str, require_str(request_data['cmdline_args_tmpl'])),
            cast(str, require_str(request_data['description_tmpl'])))
        if not monitor_def:
            raise errors.InvalidData('invalid monitor def arguments')
        return web.json_response(monitor_def.id)

    async def put(self) -> web.Response:
        request_data = await self.request.json()
        monitor_def = self._get_request_monitor_def(self.request)
        await monitor_def.update(request_data)
        return web.json_response(True)

    async def delete(self) -> web.Response:
        monitor_def = self._get_request_monitor_def(self.request)
        await monitor_def.delete()
        return web.json_response(True)

    # noinspection PyMethodMayBeStatic
    def _get_request_monitor_def(self, request):
        monitor_def_id = require_int(get_request_param(request, 'id'))
        monitor_def = request.app['active_monitor_manager'].monitor_defs.get(monitor_def_id, None)
        if not monitor_def:
            raise errors.NotFound()
        return monitor_def


class ActiveMonitorDefArgView(web.View):
    async def put(self) -> web.Response:
        request_data = await self.request.json()
        monitor_def = self._get_request_monitor_def(self.request)
        await monitor_def.set_arg(
            cast(str, require_str(request_data['name'])),
            cast(str, require_str(request_data['display_name'])),
            cast(str, require_str(request_data['description'])),
            cast(bool, require_bool(request_data['required'])),
            cast(str, require_str(request_data['default_value'])))
        return web.json_response(True)

    async def delete(self) -> web.Response:
        monitor_def = self._get_request_monitor_def(self.request)
        await monitor_def.delete_arg(
            require_str(get_request_param(self.request, 'name'))
        )
        return web.json_response(True)

    def _get_request_monitor_def(self, request: web.Request) -> ActiveMonitorDef:
        monitor_def_id = require_int(get_request_param(request, 'id'))
        monitor_def = self.request.app['active_monitor_manager'].monitor_defs.get(monitor_def_id, None)
        if not monitor_def:
            raise errors.NotFound()
        return monitor_def


class ContactView(web.View):
    async def get(self) -> web.Response:
        dbcon = self.request.app['dbcon']
        # noinspection PyUnusedLocal
        q_args = ()  # type: Tuple
        if 'id' in self.request.rel_url.query:
            contact_id = require_int(get_request_param(self.request, 'id'))
            q = """select id, name, email, phone, active from contacts where id=%s"""
            q_args = (contact_id,)
            rows = await dbcon.fetch_all(q, q_args)
            meta_q = """select meta.object_id, meta.key, meta.value
                from object_metadata as meta, contacts
                where contacts.id=%s and meta.object_type="contact" and meta.object_id=contacts.id"""
            meta_rows = await dbcon.fetch_all(meta_q, q_args)
        elif 'meta_key' in self.request.rel_url.query:
            meta_key = require_str(get_request_param(self.request, 'meta_key'))
            meta_value = require_str(get_request_param(self.request, 'meta_value'))
            q = """select c.id, c.name, c.email, c.phone, c.active
                from contacts as c, object_metadata as meta
                where meta.key=%s and meta.value=%s and meta.object_type="contact" and meta.object_id=c.id"""
            q_args = (meta_key, meta_value)
            rows = await dbcon.fetch_all(q, q_args)
            meta_q = """select m2.object_id, m2.key, m2.value
                        from object_metadata as m1
                        left join contacts on contacts.id=m1.object_id
                        left join object_metadata as m2 on m2.object_id=contacts.id
                        where m1.key=%s and m1.value=%s and m2.object_type="contact"
            """
            meta_rows = await dbcon.fetch_all(meta_q, q_args)
        else:
            q = """select id, name, email, phone, active from contacts"""
            rows = await dbcon.fetch_all(q)
            meta_q = """select meta.object_id, meta.key, meta.value
                from object_metadata as meta, contacts
                where meta.object_id=contacts.id"""
            meta_rows = await dbcon.fetch_all(meta_q)
        contacts = {}
        for id, name, email, phone, active in rows:
            contact = {
                'id': id,
                'name': name,
                'email': email,
                'phone': phone,
                'active': active,
                'metadata': {}
            }
            contacts[id] = contact
        for id, key, value in meta_rows:
            if id in contacts:
                contacts[id]['metadata'][key] = value
        return web.json_response(list(contacts.values()))

    async def post(self) -> web.Response:
        request_data = await self.request.json()
        contact_id = await create_contact(
            self.request.app['dbcon'],
            require_str(request_data.get('name', None), allow_none=True),
            require_str(request_data.get('email', None), allow_none=True),
            require_str(request_data.get('phone', None), allow_none=True),
            cast(bool, require_bool(request_data.get('active', True)))
        )
        return web.json_response(contact_id)

    async def put(self) -> web.Response:
        request_data = await self.request.json()
        contact_id = cast(int, require_int(get_request_param(self.request, 'id')))
        dbcon = self.request.app['dbcon']
        exists = await contact_exists(dbcon, contact_id)
        if not exists:
            raise errors.NotFound()
        await update_contact(dbcon, contact_id, request_data)
        return web.json_response(True)

    async def delete(self) -> web.Response:
        contact_id = cast(int, require_int(get_request_param(self.request, 'id')))
        dbcon = self.request.app['dbcon']
        exists = await contact_exists(dbcon, contact_id)
        if not exists:
            raise errors.NotFound()
        await delete_contact(dbcon, contact_id)
        return web.json_response(True)


class MetadataView(web.View):
    async def get(self) -> web.Response:
        object_type = cast(str, require_str(get_request_param(self.request, 'object_type')))
        object_id = cast(int, require_int(get_request_param(self.request, 'object_id')))
        metadict = await metadata.get_metadata(self.request.app['dbcon'], object_type, object_id)
        return web.json_response(metadict)

    async def post(self):
        request_data = await self.request.json()
        await metadata.update_metadata(
            self.request.app['dbcon'],
            require_str(request_data.get('object_type')),
            require_int(request_data.get('object_id')),
            require_dict(request_data.get('metadict'), str)
        )
        return web.json_response(True)

    async def delete(self):
        request_data = await self.request.json()
        await metadata.delete_metadata(
            self.request.app['dbcon'],
            require_str(request_data.get('object_type')),
            require_int(request_data.get('object_id')),
            require_list(request_data.get('keys', None), allow_none=True))
        return web.json_response(True)


class BindataView(web.View):
    """Manage binary data objects."""

    async def get(self) -> web.Response:
        object_type = cast(str, require_str(get_request_param(self.request, 'object_type')))
        object_id = cast(int, require_int(get_request_param(self.request, 'object_id')))
        key = cast(str, require_str(get_request_param(self.request, 'key')))
        ret = await bindata.get_bindata(self.request.app['dbcon'], object_type, object_id, key)
        if ret is None:
            raise errors.NotFound()
        return web.Response(body=ret)

    async def post(self) -> web.Response:
        object_type = cast(str, require_str(get_request_param(self.request, 'object_type')))
        object_id = cast(int, require_int(get_request_param(self.request, 'object_id')))
        key = cast(str, require_str(get_request_param(self.request, 'key')))
        value = await self.request.read()
        await bindata.set_bindata(
            self.request.app['dbcon'],
            object_type,
            object_id,
            key,
            value)
        return web.Response(text='')

    async def delete(self) -> web.Response:
        object_type = cast(str, require_str(get_request_param(self.request, 'object_type')))
        object_id = cast(int, require_int(get_request_param(self.request, 'object_id')))
        key = cast(str, require_str(get_request_param(self.request, 'key')))
        await bindata.delete_bindata(self.request.app['dbcon'], object_type, object_id, key)
        return web.Response(text='')


class StatisticsView(web.View):
    """Get server statistics"""

    # noinspection PyMethodMayBeStatic
    async def get(self) -> web.Response:
        return web.json_response(stats.get_stats())
