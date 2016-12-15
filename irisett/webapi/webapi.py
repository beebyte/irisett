"""Webapi entry point.

Set up the aiohttp environment and start listening for connections.
"""

import asyncio
from aiohttp import web

from irisett import (
    log,
    stats,
)
from irisett.webapi import (
    view,
    middleware,
)

from irisett.sql import DBConnection
from irisett.monitor.active import ActiveMonitorManager


def setup_routes(app: web.Application):
    app.router.add_route('*', '/active_monitor/', view.ActiveMonitorView)
    app.router.add_route('*', '/active_monitor_alert/', view.ActiveMonitorAlertView)
    app.router.add_route('*', '/active_monitor_contact/', view.ActiveMonitorContactView)
    app.router.add_route('*', '/active_monitor_def/', view.ActiveMonitorDefView)
    app.router.add_route('*', '/active_monitor_def_arg/', view.ActiveMonitorDefArgView)
    app.router.add_route('*', '/contact/', view.ContactView)
    app.router.add_route('*', '/metadata/', view.MetadataView)
    app.router.add_route('*', '/bindata/', view.BindataView)
    app.router.add_route('*', '/statistics/', view.StatisticsView)


def initialize(loop: asyncio.AbstractEventLoop, port: int, username: str, password: str, dbcon: DBConnection,
               active_monitor_manager: ActiveMonitorManager):
    """Initialize the webapi listener."""
    stats.set('num_calls', 0, 'WEBAPI')
    app = web.Application(loop=loop, logger=log.logger,
                          middlewares=[
                              middleware.logging_middleware_factory,
                              middleware.error_handler_middleware_factory,
                              middleware.basic_auth_middleware_factory,
                          ])
    app['username'] = username
    app['password'] = password
    app['dbcon'] = dbcon
    app['active_monitor_manager'] = active_monitor_manager
    setup_routes(app)
    listener = loop.create_server(app.make_handler(), '0.0.0.0', port)
    loop.create_task(listener)  # type: ignore
    log.msg('Webapi listening on port %s' % port)
