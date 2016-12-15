"""Webapi middleware helpers.

Middleware for common actions, authentication etc.
"""

from typing import Optional
import base64
import binascii
from aiohttp import web

from irisett import (
    log,
    stats,
)
from irisett.webapi import (
    errors,
)
from irisett.errors import IrisettError


# noinspection PyUnusedLocal
async def logging_middleware_factory(app: web.Application, handler):
    """Basic logging and accounting."""
    async def middleware_handler(request: web.Request) -> web.Response:
        stats.inc('num_calls', 'WEBAPI')
        log.msg('Received request: %s' % request, 'WEBAPI')
        return await handler(request)

    return middleware_handler


async def basic_auth_middleware_factory(app: web.Application, handler):
    """Authentication.

    Uses HTTP basic auth to check that requests are including the required
    username and password.
    """
    async def middleware_handler(request: web.Request) -> web.Response:
        ok = False
        auth_token = request.headers.get('Authorization')
        if auth_token and auth_token.startswith('Basic '):
            auth_token = auth_token[6:]
            try:
                auth_bytes = base64.b64decode(auth_token)  # type: Optional[bytes]
            except binascii.Error:
                auth_bytes = None
            if auth_bytes:
                auth_str = auth_bytes.decode('utf-8', errors='ignore')
                if ':' in auth_str:
                    username, password = auth_str.split(':', 1)
                    if username == app['username'] and password == app['password']:
                        ok = True
        if not ok:
            log.msg('Unauthorized request: %s' % request, 'WEBAPI')
            raise errors.PermissionDenied('Unauthorized')
        return await handler(request)

    return middleware_handler


# noinspection PyUnusedLocal
async def error_handler_middleware_factory(app: web.Application, handler):
    """Error handling middle.

    Catch errors raised in web views and try to return a corresponding
    HTTP error code.
    """
    async def middleware_handler(request: web.Request) -> web.Response:
        errcode = None
        errmsg = None
        ret = None
        try:
            ret = await handler(request)
        except errors.NotFound as e:
            errcode = 404
            errmsg = str(e) or 'not found'
        except errors.PermissionDenied as e:
            errcode = 401
            errmsg = str(e) or 'permission denied'
        except errors.InvalidData as e:
            errcode = 400
            errmsg = str(e) or 'invalid data'
        except errors.WebAPIError as e:
            errcode = 400
            errmsg = str(e) or 'api error'
        except IrisettError as e:
            errcode = 400
            errmsg = str(e) or 'irisett error'
        if errcode:
            log.msg('Request returning error(%d/%s): %s' % (errcode, errmsg, request), 'WEBAPI')
            ret = web.Response(status=errcode, text=errmsg)
        return ret

    return middleware_handler
