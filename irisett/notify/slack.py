from typing import List, Dict, Optional, Any
import aiohttp
import json
import jinja2

from irisett import (
    log
)


async def send_slack_notification(url: str, attachments: List[Dict]):
    data = {
        'attachments': attachments
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=json.dumps(data), timeout=30) as resp:
                if resp.status != 200:
                    log.msg('Error sending slack notification: http status %s' % (str(resp.status)),
                            'NOTIFICATION')
    except aiohttp.ClientError as e:
        log.msg('Error sending slack notification: %s' % (str(e)), 'NOTIFICATIONS')


async def send_alert_notification(settings: Dict, tmpl_args: Dict):
    attachment = {
        'fallback': settings['tmpl-msg'].render(**tmpl_args),
        'fields': [],
    }
    attachment['pretext'] = attachment['fallback']
    if settings['tmpl-duration']:
        attachment['fields'].append({
            'title': 'Duration',
            'value': settings['tmpl-duration'].render(**tmpl_args),
            'short': False,
        })
    if settings['tmpl-url']:
        attachment['fields'].append({
            'title': 'URL',
            'value': settings['tmpl-url'].render(**tmpl_args),
            'short': False,
        })
    await send_slack_notification(settings['webhook-url'], [attachment])


def parse_settings(config) -> Optional[Dict[str, Any]]:
    ret = {
        'webhook-url': config.get('slack-webhook-url'),
        'tmpl-msg': config.get('slack-tmpl-msg'),
        'tmpl-duration': config.get('slack-tmpl-duration', fallback=''),
        'tmpl-url': config.get('slack-tmpl-url', fallback='')
    }  # type: Any
    if not ret['webhook-url'] or not ret['tmpl-msg']:
        log.debug('Slack settings missing, no slack notifications will be sent', 'NOTIFICATIONS')
        ret = None
    else:
        log.debug('Valid slack notification settings found', 'NOTIFICATIONS')
        ret['tmpl-msg'] = jinja2.Template(ret['tmpl-msg'])
        if ret['tmpl-duration']:
            ret['tmpl-duration'] = jinja2.Template(ret['tmpl-duration'])
        if ret['tmpl-url']:
            ret['tmpl-url'] = jinja2.Template(ret['tmpl-url'])
    return ret
