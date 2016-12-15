"""Send notification emails."""

from typing import Optional, Dict, Any, Union, Iterable
import aiosmtplib
import jinja2
from email import charset
charset.add_charset('utf-8', charset.SHORTEST, charset.QP)  # type: ignore
# noinspection PyPep8
from email.mime.text import MIMEText

from irisett import (
    log,
)


async def send_email(loop, mail_from: str, mail_to: Union[Iterable, str],
                     subject: str, body: str, server: str='localhost'):
    """Send an email to one or more recipients.

    Only supports plain text emails with a single message body.
    No attachments etc.
    """
    if type(mail_to) == str:
        mail_to = [mail_to]
    smtp = aiosmtplib.SMTP(hostname=server, port=25, loop=loop)
    try:
        await smtp.connect()
        for rcpt in mail_to:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = mail_from
            msg['To'] = rcpt
            await smtp.send_message(msg)
            await smtp.quit()
    except aiosmtplib.errors.SMTPException as e:
        log.msg('Error sending smtp notification: %s' % (str(e)), 'NOTIFICATIONS')


async def send_alert_notification(loop, settings: Dict[str, Any], recipients: Iterable[str], tmpl_args: Dict[str, Any]):
    subject = settings['tmpl-subject'].render(**tmpl_args)
    body = settings['tmpl-body'].render(**tmpl_args)
    await send_email(loop, settings['sender'], recipients, subject, body, settings['server'])


def parse_settings(config) -> Optional[Dict[str, Any]]:
    ret = {
        'sender': config.get('email-sender'),
        'tmpl-subject': config.get('email-tmpl-subject'),
        'tmpl-body': config.get('email-tmpl-body'),
        'server': config.get('email-server', fallback='localhost')
    }  # type: Any
    if not ret['sender'] or not ret['tmpl-subject'] or not ['tmpl-body'] or not ['server']:
        log.msg('Email settings missing, no email notifications will be sent', 'NOTIFICATIONS')
        ret = None
    else:
        log.debug('Valid email notification settings found', 'NOTIFICATIONS')
        ret['tmpl-subject'] = jinja2.Template(ret['tmpl-subject'])
        ret['tmpl-body'] = jinja2.Template(ret['tmpl-body'])
    return ret
