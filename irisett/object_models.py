"""Model/object definitions for commonly used types in Irisett.

This modules uses the attrs module to define models for Irisett objects
(monitors, alerts, contacts etc).

The model definitions should exactly match the attributes and order of the
objects in the database.
"""

from typing import Iterable, Any, List
# noinspection PyPackageRequirements
import attr
# noinspection PyPackageRequirements
from attr import asdict


def insert_values(object):
    """Get values appropriate for inserting into the DB.

    Use this as the query arguments for a plain insert of an object into
    the standard irisett DB.
    """
    return attr.astuple(object, filter=insert_filter)


def list_asdict(in_list: Iterable[Any]) -> List[Any]:
    """asdict'ify a list of objects.

    Useful when converting a list of objects to json.
    """
    return [asdict(obj) for obj in in_list]


def insert_filter(attribute, value):
    """A standard filter used to prep objects for insert into the DB."""
    if attribute.name in ['id']:
        return False
    return True


@attr.s
class Contact:
    id = attr.ib()
    name = attr.ib()
    email = attr.ib()
    phone = attr.ib()
    active = attr.ib()
    model_type = 'contact'


@attr.s
class ContactGroup:
    id = attr.ib()
    name = attr.ib()
    active = attr.ib()
    model_type = 'contact_group'


@attr.s
class ActiveMonitor:
    id = attr.ib()
    def_id = attr.ib()
    state = attr.ib()
    state_ts = attr.ib()
    msg = attr.ib()
    alert_id = attr.ib()
    deleted = attr.ib()
    checks_enabled = attr.ib()
    alerts_enabled = attr.ib()
    args = attr.ib(init=False, default=attr.Factory(dict))
    model_type = 'active_monitor'


@attr.s
class ActiveMonitorArg:
    id = attr.ib()
    monitor_id = attr.ib()
    name = attr.ib()
    value = attr.ib()
    model_type = 'active_monitor_arg'


@attr.s
class ActiveMonitorAlert:
    id = attr.ib()
    monitor_id = attr.ib()
    start_ts = attr.ib()
    end_ts = attr.ib()
    alert_msg = attr.ib()
    model_type = 'active_monitor_alert'


@attr.s
class ActiveMonitorDef:
    id = attr.ib()
    name = attr.ib()
    description = attr.ib()
    active = attr.ib()
    cmdline_filename = attr.ib()
    cmdline_args_tmpl = attr.ib()
    description_tmpl = attr.ib()
    args = attr.ib(init=False, default=attr.Factory(list))
    model_type = 'active_monitor_arg'


@attr.s
class ActiveMonitorDefArg:
    id = attr.ib()
    active_monitor_def_id = attr.ib()
    name = attr.ib()
    display_name = attr.ib()
    description = attr.ib()
    required = attr.ib()
    default_value = attr.ib()
    model_type = 'active_monitor_def_arg'


@attr.s
class ObjectMetadata:
    object_type = attr.ib()
    object_id = attr.ib()
    key = attr.ib()
    value = attr.ib()
    model_type = 'object_metadata'


@attr.s
class ObjectBindata:
    object_type = attr.ib()
    object_id = attr.ib()
    key = attr.ib()
    value = attr.ib()
    model_type = 'object_bindata'


@attr.s
class MonitorGroup:
    id = attr.ib()
    parent_id = attr.ib()
    name = attr.ib()
    model_type = 'monitor_group'
