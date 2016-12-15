from typing import Dict, Any, Optional, Iterable

from irisett import (
    log,
)
from irisett.notify import (
    clicksend,
)


def parse_settings(config) -> Optional[Dict[str, Any]]:
    provider = config.get('sms-provider')
    if not provider:
        log.msg('No SMS provider specified, no sms notifications will be sent', 'NOTIFICATIONS')
        return None
    if provider not in ['clicksend']:
        log.msg('Unknown SMS provider specified, no sms notifications will be sent', 'NOTIFICATIONS')
        return None
    ret = None
    if provider == 'clicksend':
        ret = clicksend.parse_settings(config)
    return ret


async def send_alert_notification(settings: Dict[str, Any], recipients: Iterable[str], tmpl_args: Dict[str, Any]):
    if settings['provider'] == 'clicksend':
        msg = settings['tmpl'].render(**tmpl_args)
        await clicksend.send_sms(recipients, msg, settings['username'], settings['api-key'],
                                 settings['sender'])
