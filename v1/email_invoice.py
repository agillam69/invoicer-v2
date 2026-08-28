"""
email_invoice.py
================
Send invoice PDFs by email from within the application.

Supports two backends:
  1. Windows MAPI / Outlook (win32com.client) — preferred on Windows when Outlook is installed.
  2. SMTP — configurable via settings (server, port, user, password, from_address, tls).

All send functions return a result dict: {'ok': bool, 'method': str, 'error': str|None}.
"""

import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path


def _basename(path: str) -> str:
    return Path(path).name


def has_mapi() -> bool:
    """Return True if win32com Outlook MAPI is available."""
    try:
        import win32com.client
        win32com.client.Dispatch('Outlook.Application')
        return True
    except Exception:
        return False


def has_smtp_config(settings: dict) -> bool:
    """Return True if the user has configured an SMTP server."""
    s = settings or {}
    return bool(s.get('smtp_server') and s.get('smtp_from'))


def _send_mapi(to: str, subject: str, body: str, attachment_path: str):
    """Send via Outlook MAPI. Returns result dict."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch('Outlook.Application')
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to
        mail.Subject = subject
        mail.Body = body
        mail.Attachments.Add(str(Path(attachment_path).resolve()))
        mail.Send()
        return {'ok': True, 'method': 'mapi', 'error': None}
    except Exception as e:
        return {'ok': False, 'method': 'mapi', 'error': str(e)}


def _send_smtp(to: str, subject: str, body: str, attachment_path: str, settings: dict):
    """Send via SMTP. Returns result dict."""
    s = settings or {}
    server   = s.get('smtp_server', '')
    port     = int(s.get('smtp_port', 587))
    user     = s.get('smtp_user', '')
    password = s.get('smtp_password', '')
    from_addr = s.get('smtp_from', '')
    use_tls  = str(s.get('smtp_tls', 'yes')).lower() in ('yes', 'true', '1')

    if not server or not from_addr:
        return {'ok': False, 'method': 'smtp', 'error': 'SMTP server or from address not configured'}

    try:
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        p = Path(attachment_path)
        with open(p, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{p.name}"')
        msg.attach(part)

        with smtplib.SMTP(server, port) as conn:
            if use_tls:
                conn.starttls()
            if user and password:
                conn.login(user, password)
            conn.sendmail(from_addr, [to], msg.as_string())
        return {'ok': True, 'method': 'smtp', 'error': None}
    except Exception as e:
        return {'ok': False, 'method': 'smtp', 'error': str(e)}


def send_email_with_attachment(to: str, subject: str, body: str, attachment_path: str,
                                settings: dict = None, prefer_mapi: bool = True,
                                audit_fn=None) -> dict:
    """
    Send an email with a single PDF attachment.

    - If prefer_mapi and Windows MAPI is available, use Outlook.
    - Otherwise, if SMTP is configured, use SMTP.
    - Otherwise return an error.

    audit_fn, if provided, is called with (action, detail, table, record_id).
    """
    settings = settings or {}
    path = Path(attachment_path)
    if not path.exists():
        err = f'Attachment not found: {path}'
        if audit_fn:
            audit_fn('email_failed', err, 'invoices', '')
        return {'ok': False, 'method': 'none', 'error': err}

    result = None
    if prefer_mapi and has_mapi():
        result = _send_mapi(to, subject, body, str(path))
        if result['ok']:
            if audit_fn:
                audit_fn('email_sent', f'to={to} method=mapi attachment={path.name}',
                         'invoices', '')
            return result

    if has_smtp_config(settings):
        result = _send_smtp(to, subject, body, str(path), settings)
        if result['ok']:
            if audit_fn:
                audit_fn('email_sent', f'to={to} method=smtp attachment={path.name}',
                         'invoices', '')
            return result

    # No working backend
    error = (result['error'] if result else 'No email backend available. Configure Outlook or SMTP in Settings.')
    if audit_fn:
        audit_fn('email_failed', error, 'invoices', '')
    return {'ok': False, 'method': 'none', 'error': error}


def default_invoice_subject(invoice_number: str, client_name: str) -> str:
    return f'Invoice {invoice_number} — {client_name}'


def default_invoice_body(invoice_number: str, client_name: str, settings: dict = None) -> str:
    s = settings or {}
    business = s.get('business_name', 'Our business')
    return (
        f'Hi {client_name},\n\n'
        f'Please find attached invoice {invoice_number}.\n\n'
        f'If you have any questions, please contact us.\n\n'
        f'Regards,\n{business}'
    )
