"""SQL functions for active monitors."""

from typing import Iterable, Optional, Dict, Tuple

from irisett.sql import DBConnection
from irisett import (
    object_models,
    sql,
)


async def get_all_active_monitor_defs(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitorDef]:
    """Load monitor defs from the database."""
    q = """select id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl
        from active_monitor_defs"""
    return [object_models.ActiveMonitorDef(*row) for row in await dbcon.fetch_all(q)]


async def get_active_monitor_def(dbcon: DBConnection, id: int) -> Optional[object_models.ActiveMonitorDef]:
    """Load one monitor def from the database."""
    q = """select id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl
        from active_monitor_defs where id=%s"""
    res = [object_models.ActiveMonitorDef(*row) for row in await dbcon.fetch_all(q, (id,))]
    if res:
        active_monitor_def = res[0]  # type: Optional[object_models.ActiveMonitorDef]
    else:
        active_monitor_def = None
    return active_monitor_def


async def get_all_active_monitor_def_args(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitorDefArg]:
    """Load monitor def args from the database."""
    q = """select id, active_monitor_def_id, name, display_name, description, required, default_value
            from active_monitor_def_args"""
    return [object_models.ActiveMonitorDefArg(*row) for row in await dbcon.fetch_all(q)]


async def get_active_monitor_def_args_for_def(
        dbcon: DBConnection, def_id: int) -> Iterable[object_models.ActiveMonitorDefArg]:
    """Load the monitor def args for a monitor def."""
    q = """select id, active_monitor_def_id, name, display_name, description, required, default_value
            from active_monitor_def_args where active_monitor_def_id=%s"""
    return [object_models.ActiveMonitorDefArg(*row) for row in await dbcon.fetch_all(q, (def_id,))]


async def get_all_active_monitors(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitor]:
    """Load monitors from the database."""
    q = """select id, def_id, state, state_ts, msg, alert_id, deleted, checks_enabled, alerts_enabled
            from active_monitors"""
    return [object_models.ActiveMonitor(*row) for row in await dbcon.fetch_all(q)]


async def get_all_active_monitor_args(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitorArg]:
    """Load monitor args from the database."""
    q = """select id, monitor_id, name, value from active_monitor_args"""
    return [object_models.ActiveMonitorArg(*row) for row in await dbcon.fetch_all(q)]


async def get_active_monitors_for_metadata(dbcon: DBConnection, meta_key: str, meta_value: str):
    q = """select mon.id, mon.def_id, mon.state, mon.state_ts, mon.msg, mon.alert_id, mon.deleted,
        mon.checks_enabled, mon.alerts_enabled
        from active_monitors as mon, object_metadata as meta
        where meta.key=%s and meta.value=%s and meta.object_type="active_monitor" and meta.object_id=mon.id"""
    q_args = (meta_key, meta_value)
    return [object_models.ActiveMonitor(*row) for row in await dbcon.fetch_all(q, q_args)]


async def create_active_monitor(dbcon: DBConnection, monitor_def_id: int,
                                monitor_args: Dict[str, str]) -> int:
    async def _run(cur: sql.Cursor) -> int:
        q = """insert into active_monitors (def_id, state, state_ts, msg) values (%s, %s, %s, %s)"""
        q_args = (monitor_def_id, 'UNKNOWN', 0, '')  # type: Tuple
        await cur.execute(q, q_args)
        _monitor_id = cur.lastrowid
        q = """insert into active_monitor_args (monitor_id, name, value) values (%s, %s, %s)"""
        for name, value in monitor_args.items():
            q_args = (_monitor_id, name, value)
            await cur.execute(q, q_args)
        return _monitor_id

    monitor_id = await dbcon.transact(_run)
    return monitor_id


async def delete_active_monitor(dbcon: DBConnection, monitor_id: int) -> None:
    """Remove all traces of a monitor from the database."""

    async def _run(cur: sql.Cursor) -> None:
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
        q = """delete from active_monitor_groups where active_monitor_id=%s"""
        await cur.execute(q, q_args)

    await dbcon.transact(_run)
