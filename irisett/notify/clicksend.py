from typing import Dict, Any, Iterable, Optional, List
import aiohttp
import json
import jinja2

from irisett import (
    log
)

CLICKSEND_URL = 'https://rest.clicksend.com/v3/sms/send'


async def send_sms(recipients: Iterable[str], msg: str, username: str, api_key: str, sender: str):
    data = {
        'messages': [],
    }  # type: Dict[str, List]
    for recipient in recipients:
        data['messages'].append({
            'source': 'python',
            'from': sender,
            'body': msg[:140],
            'to': recipient,
            'schedule': ''
        })
    try:
        async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'},
                                         auth=aiohttp.BasicAuth(username, api_key)) as session:
            async with session.post(CLICKSEND_URL, data=json.dumps(data), timeout=30) as resp:
                if resp.status != 200:
                    log.msg('Error sending clicksend sms notification: http status %s' % (str(resp.status)),
                            'NOTIFICATION')
    except aiohttp.ClientError as e:
        log.msg('Error sending clicksend sms notification: %s' % (str(e)), 'NOTIFICATIONS')


def parse_settings(config) -> Optional[Dict[str, Any]]:
    """Parse clicksend sms settings.

    Should only be called from sms.parse_settings.
    """
    ret = {
        'provider': 'clicksend',
        'username': config.get('sms-clicksend-username'),
        'api-key': config.get('sms-clicksend-api-key'),
        'sender': config.get('sms-clicksend-sender'),
        'tmpl': config.get('sms-tmpl'),
    }  # type: Any
    if not ret['username'] or not ret['api-key'] or not ['sender'] or not ['tmpl']:
        log.msg('SMS settings missing, no sms notifications will be sent', 'NOTIFICATIONS')
        ret = None
    else:
        log.debug('Valid SMS notification settings found', 'NOTIFICATIONS')
        ret['tmpl'] = jinja2.Template(ret['tmpl'])
    return ret
