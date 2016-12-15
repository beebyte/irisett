from typing import Dict, Iterable, Any, List
import asyncio

from irisett import (
    log,
)
from irisett.notify import (
    email,
    http,
    sms,
    clicksend,
    slack,
)


# noinspection PyMethodMayBeStatic
class NotificationManager:
    def __init__(self, config, *, loop: asyncio.AbstractEventLoop=None) -> None:
        self.loop = loop or asyncio.get_event_loop()
        if not config:
            log.msg('Missing config section, no alert notification will be sent', 'NOTIFICATIONS')
            self.http_settings = None
            self.email_settings = None
            self.sms_settings = None
            self.slack_webhook_url = None
        else:
            self.http_settings = http.parse_settings(config)
            self.email_settings = email.parse_settings(config)
            self.sms_settings = sms.parse_settings(config)
            self.slack_settings = slack.parse_settings(config)

    async def send_notification(self, recipient_dict: Dict[str, Any], tmpl_args: Dict[str, Any]) -> bool:
        email_recipients = list(recipient_dict['email'])
        sms_recipients = list(recipient_dict['phone'])
        if email_recipients and self.email_settings:
            await email.send_alert_notification(self.loop, self.email_settings, email_recipients, tmpl_args)
        if sms_recipients and self.sms_settings:
            await sms.send_alert_notification(self.sms_settings, sms_recipients, tmpl_args)
        if self.http_settings:
            await http.send_alert_notification(self.http_settings, email_recipients, sms_recipients, tmpl_args)
        if self.slack_settings:
            await slack.send_alert_notification(self.slack_settings, tmpl_args)
        return True

    async def send_email(self, recipients: Iterable[str], subject: str, body: str):
        if not self.email_settings:
            return
        await email.send_email(self.loop, self.email_settings['sender'], recipients, subject, body,
                               self.email_settings['server'])

    async def send_sms(self, recipients: Iterable[str], msg: str):
        if not self.sms_settings:
            return
        if self.sms_settings['provider'] == 'clicksend':
            await clicksend.send_sms(recipients, msg, self.sms_settings['username'], self.sms_settings['api-key'],
                                     self.sms_settings['sender'])

    async def send_http_notification(self, data):
        if not self.http_settings:
            return
        await http.send_http_notification(self.http_settings['url'], data)

    async def send_slack_notification(self, attachments: List[Dict]):
        if not self.slack_webhook_url:
            return
        await slack.send_slack_notification(self.slack_settings['webhook-url'], attachments)
