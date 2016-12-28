"""Webmgmt entry point.

Set up the aiohttp environment and start listening for connections.
"""

import asyncio
from aiohttp import web
# noinspection PyPackageRequirements
import aiohttp_jinja2
import jinja2
import os

from irisett import (
    log,
    stats,
)
from irisett.webmgmt import (
    view,
    middleware,
)

from irisett.sql import DBConnection
from irisett.monitor.active import ActiveMonitorManager


def setup_routes(app: web.Application):
    r = app.router.add_route
    r('*', '/', view.IndexView)
    r('*', '/statistics/', view.StatisticsView)
    r('*', '/alerts/', view.AlertsView)
    r('*', '/events/', view.EventsView)
    r('GET', '/events/websocket/', view.events_websocket_handler)
    r('*', '/active_monitor/', view.ListActiveMonitorsView)
    r('*', '/active_monitor/{id}/', view.DisplayActiveMonitorView)
    r('*', '/active_monitor_def/', view.ListActiveMonitorDefsView)
    r('*', '/active_monitor_def/{id}/', view.DisplayActiveMonitorDefView)
    r('*', '/contact/', view.ListContactsView)
    r('*', '/contact/{id}/', view.DisplayContactView)
    static_path = '%s/static' % (os.path.dirname(os.path.realpath(__file__)))
    app.router.add_static('/static/', path=static_path, name='static')


def initialize(loop: asyncio.AbstractEventLoop, port: int, username: str, password: str, dbcon: DBConnection,
               active_monitor_manager: ActiveMonitorManager):
    """Initialize the webmgmt listener."""
    stats.set('num_calls', 0, 'WEBMGMT')
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
    aiohttp_jinja2.setup(
        app, loader=jinja2.PackageLoader('irisett.webmgmt', 'templates'))

    listener = loop.create_server(app.make_handler(), '0.0.0.0', port)
    loop.create_task(listener)  # type: ignore
    log.msg('Webmgmt listening on port %s' % port)
