"""Model/object definitions for commonly used types in Irisett.

This modules uses the attrs module to define models for Irisett objects
(monitors, alerts, contacts etc).

The model definitions should exactly match the attributes and order of the
objects in the database.
"""

# noinspection PyPackageRequirements
import attr
# noinspection PyPackageRequirements
from attr import asdict


@attr.s
class ActiveMonitorAlert:
    id = attr.ib()
    monitor_id = attr.ib()
    start_ts = attr.ib()
    end_ts = attr.ib()
    alert_msg = attr.ib()
    model_type = attr.ib(init=False, default='active_monitor_alert')


@attr.s
class Contact:
    id = attr.ib()
    name = attr.ib()
    email = attr.ib()
    phone = attr.ib()
    active = attr.ib()
    model_type = attr.ib(init=False, default='contact')


@attr.s
class ContactGroup:
    id = attr.ib()
    name = attr.ib()
    active = attr.ib()
    model_type = attr.ib(init=False, default='contact_group')


@attr.s
class MonitorGroup:
    id = attr.ib()
    parent_id = attr.ib()
    name = attr.ib()
    model_type = attr.ib(init=False, default='monitor_group')


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
    model_type = attr.ib(init=False, default='active_monitor')
