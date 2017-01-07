"""SQL functions for active monitors."""

from typing import Iterable

from irisett.sql import DBConnection
from irisett import (
    object_models,
)


async def get_all_active_monitor_defs(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitorDef]:
    """Load monitor defs from the database."""
    q = """select id, name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl
        from active_monitor_defs"""
    return [object_models.ActiveMonitorDef(*row) for row in await dbcon.fetch_all(q)]


async def get_all_active_monitor_def_args(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitorDefArg]:
    """Load monitor def args from the database."""
    q = """select id, active_monitor_def_id, name, display_name, description, required, default_value
            from active_monitor_def_args"""
    return [object_models.ActiveMonitorDefArg(*row) for row in await dbcon.fetch_all(q)]


async def get_all_active_monitors(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitor]:
    """Load monitors from the database."""
    q = """select id, def_id, state, state_ts, msg, alert_id, deleted, checks_enabled, alerts_enabled
            from active_monitors"""
    return [object_models.ActiveMonitor(*row) for row in await dbcon.fetch_all(q)]


async def get_all_active_monitor_args(dbcon: DBConnection) -> Iterable[object_models.ActiveMonitorArg]:
    """Load monitor args from the database."""
    q = """select id, monitor_id, name, value from active_monitor_args"""
    return [object_models.ActiveMonitorArg(*row) for row in await dbcon.fetch_all(q)]
