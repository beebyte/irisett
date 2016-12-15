from typing import Any, Optional, Dict, Iterable
import aiohttp
import json

from irisett import (
    log
)


async def send_http_notification(url: str, in_data: Any):
    out_data = json.dumps(in_data)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=out_data, timeout=10) as resp:
                if resp.status != 200:
                    log.msg('Error sending http notification: http status %s' % (str(resp.status)),
                            'NOTIFICATION')
    except aiohttp.ClientError as e:
        log.msg('Error sending http notification: %s' % (str(e)), 'NOTIFICATIONS')


async def send_alert_notification(settings: Dict[str, Any], email_recipients: Iterable[str],
                                  sms_recipients: Iterable[str], tmpl_args: Dict[str, Any]):
    data = {
        'email_recipients': email_recipients,
        'sms_recipients': sms_recipients,
        'data': tmpl_args,
    }

    await send_http_notification(settings['url'], data)


def parse_settings(config) -> Optional[Dict[str, Any]]:
    ret = {
        'url': config.get('http-url'),
    }  # type: Any
    if not ret['url']:
        log.debug('HTTP settings missing, no slack notifications will be sent', 'NOTIFICATIONS')
        ret = None
    else:
        log.debug('Valid HTTP notification settings found', 'NOTIFICATIONS')
    return ret
