"""Email service – Gmail SMTP (primární) nebo Resend API (záložní).

Gmail nevyžaduje ověřenou doménu – stačí Gmail účet + App Password.
"""
import os
import base64
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

logger = logging.getLogger(__name__)

RESEND_API_URL = 'https://api.resend.com/emails'


# ---------------------------------------------------------------------------
# Helpers – načtení nastavení
# ---------------------------------------------------------------------------

def _get_smtp_settings():
    """Vrátí SMTP nastavení z DB (nebo prázdné hodnoty)."""
    try:
        from app.models.app_settings import get_smtp_settings
        return get_smtp_settings()
    except Exception:
        return {'server': '', 'port': '587', 'use_tls': 'true',
                'username': '', 'password': '', 'sender': ''}


def _get_resend_key():
    """Resend API klíč z env nebo DB (záložní metoda)."""
    key = os.environ.get('RESEND_API_KEY', '')
    if not key:
        try:
            from app.models.app_settings import get_setting
            key = get_setting('resend_api_key', '')
        except Exception:
            pass
    return key


def is_smtp_configured():
    """True pokud je nakonfigurováno odesílání (SMTP nebo Resend)."""
    smtp = _get_smtp_settings()
    if smtp.get('server') and smtp.get('username') and smtp.get('password'):
        return True
    return bool(_get_resend_key())


# ---------------------------------------------------------------------------
# Odeslání emailu
# ---------------------------------------------------------------------------

def send_schedule_email(to_email, employee_name, week_label, attachments):
    """Odešle rozpis směn jako přílohu emailem.

    Args:
        to_email: adresa příjemce
        employee_name: jméno zaměstnance (pro oslovení)
        week_label: popis týdne, např. "týden 15/2026"
        attachments: seznam (bytes, filename) dvojic

    Raises:
        ValueError: email není nakonfigurován
        Exception: chyba při odesílání
    """
    smtp = _get_smtp_settings()
    if smtp.get('server') and smtp.get('username') and smtp.get('password'):
        _send_via_smtp(to_email, employee_name, week_label, attachments, smtp)
    elif _get_resend_key():
        _send_via_resend(to_email, employee_name, week_label, attachments)
    else:
        raise ValueError(
            "Email není nakonfigurován. "
            "Nastavte SMTP (Gmail) v záložce Nastavení → Email."
        )


def _send_via_smtp(to_email, employee_name, week_label, attachments, smtp):
    """Odešle email přes SMTP (Gmail/jiný server)."""
    server = smtp['server'].strip()
    port = int(smtp.get('port') or 587)
    username = smtp['username'].strip()
    password = smtp['password'].strip()
    sender = (smtp.get('sender') or username).strip()

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = to_email
    msg['Subject'] = f'Rozpis směn – {week_label}'

    html_body = (
        f'<p>Dobrý den {employee_name},</p>'
        f'<p>v příloze najdete rozpis směn na <strong>{week_label}</strong>.</p>'
        f'<p>S pozdravem,<br>Plánování směn FerMato</p>'
    )
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    for file_bytes, filename in attachments:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(file_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(server, port, timeout=30) as conn:
        conn.ehlo()
        conn.starttls(context=context)
        conn.ehlo()
        conn.login(username, password)
        conn.sendmail(sender, [to_email], msg.as_bytes())

    logger.info(f"Email odeslán přes SMTP na {to_email}")


def _send_via_resend(to_email, employee_name, week_label, attachments):
    """Záložní metoda – Resend API (vyžaduje ověřenou doménu)."""
    import requests

    api_key = _get_resend_key()
    smtp = _get_smtp_settings()
    sender = smtp.get('sender') or 'onboarding@resend.dev'

    html_body = (
        f'<p>Dobrý den {employee_name},</p>'
        f'<p>v příloze najdete rozpis směn na <strong>{week_label}</strong>.</p>'
        f'<p>S pozdravem,<br>Plánování směn FerMato</p>'
    )

    resend_attachments = []
    for file_bytes, filename in attachments:
        resend_attachments.append({
            'filename': filename,
            'content': base64.b64encode(file_bytes).decode('utf-8'),
        })

    payload = {
        'from': sender,
        'to': [to_email],
        'subject': f'Rozpis směn – {week_label}',
        'html': html_body,
        'attachments': resend_attachments,
    }

    resp = requests.post(
        RESEND_API_URL,
        json=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise Exception(f"Resend API error: {resp.status_code} - {resp.text}")

    logger.info(f"Email odeslán přes Resend na {to_email}: {resp.json()}")


# ---------------------------------------------------------------------------
# Test připojení
# ---------------------------------------------------------------------------

def test_connection():
    """Test připojení – odešle testovací email na vlastní adresu."""
    smtp = _get_smtp_settings()
    if smtp.get('server') and smtp.get('username') and smtp.get('password'):
        _send_via_smtp(
            to_email=smtp.get('sender') or smtp['username'],
            employee_name='Admin',
            week_label='TEST',
            attachments=[],
        )
        return {'method': 'smtp', 'status': 'ok'}
    elif _get_resend_key():
        import requests
        api_key = _get_resend_key()
        sender = smtp.get('sender') or 'onboarding@resend.dev'
        payload = {
            'from': sender,
            'to': [sender],
            'subject': 'Test – Plánování směn FerMato',
            'html': '<p>Testovací email z aplikace Plánování směn. ✓</p>',
        }
        resp = requests.post(
            RESEND_API_URL,
            json=payload,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"Resend API: {resp.status_code} - {resp.text}")
        return resp.json()
    else:
        raise ValueError("Email není nakonfigurován.")
