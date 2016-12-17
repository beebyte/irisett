"""Webapi views."""

from typing import Any, Dict, List, Iterable, Optional, cast, Tuple
from aiohttp import web
import aiohttp_jinja2


class IndexView(web.View):
    # noinspection PyMethodMayBeStatic
    @aiohttp_jinja2.template('index.html')
    async def get(self) -> Dict[str, Any]:
        return {}
