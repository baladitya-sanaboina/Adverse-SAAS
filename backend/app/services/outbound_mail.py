"""Mail that leaves the company, by SMTP (owner decisions 2026-11-15).

Only things meant for outside go here: payment receipts and sheet statements to clients, salary
mail to employees, overdue invoice reminders, onboarding documents. Every such mail also puts a
web notification in the person's bell when they have an account ("mail velthe web notifications
kuda"). Sending happens in the background so the admin's click never waits on the mail server;
email_service skips test logins and repeats of the same mail.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from email.message import EmailMessage
from html import escape
from uuid import UUID

from app.core.settings import settings
from app.database.connectivity import database_pool
from app.services.email_service import email_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

APP_INDEX = {"ADMIN": 0, "MANAGER": 1, "EMPLOYEE": 2, "CLIENT": 3}


def app_url(app: str, path: str = "/") -> str:
    """A link into the right app (each role has its own)."""
    origins = settings.allowed_origins or ["http://localhost:3000"]
    index = APP_INDEX.get(app, 0)
    origin = origins[index] if len(origins) > index else origins[0]
    return f"{origin}{path}"


def user_email(user_id: UUID) -> str | None:
    """Where outside mail reaches this person: their own Gmail; the login only when no Gmail
    is on file (an internal login is then filtered out by the mail sender)."""
    with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(NULLIF(recovery_email,''), email) FROM users WHERE id=%s", (user_id,)
        )
        row = cursor.fetchone()
        return str(row[0]) if row and row[0] else None


def _html(
    title: str,
    lines: Sequence[str],
    rows: Sequence[tuple[str, str]],
    table: Sequence[Sequence[str]],
    action_label: str | None,
    action_url: str | None,
    company: str,
) -> str:
    paragraphs = "".join(
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#334155">{escape(line)}</p>'
        for line in lines
        if line
    )
    facts = "".join(
        f'<tr><td style="padding:8px 0;color:#64748b;font-size:13px">{escape(label)}</td>'
        f'<td style="padding:8px 0;text-align:right;font-size:13px;font-weight:700">{escape(value)}</td></tr>'
        for label, value in rows
    )
    grid = ""
    if table:
        head, *body = table
        cells = "".join(
            f'<th style="padding:8px;text-align:{"left" if i < 2 else "right"};font-size:11px;'
            f'color:#64748b;text-transform:uppercase;border-bottom:1px solid #e2e8f0">{escape(c)}</th>'
            for i, c in enumerate(head)
        )
        lines_html = "".join(
            "<tr>"
            + "".join(
                f'<td style="padding:8px;text-align:{"left" if i < 2 else "right"};font-size:12px;'
                f'border-bottom:1px solid #f1f5f9">{escape(c)}</td>'
                for i, c in enumerate(row)
            )
            + "</tr>"
            for row in body
        )
        grid = (
            '<table role="presentation" width="100%" style="border-collapse:collapse;margin:8px 0 16px">'
            f"<tr>{cells}</tr>{lines_html}</table>"
        )
    button = (
        f'<a href="{escape(action_url, quote=True)}" style="display:inline-block;padding:12px 18px;'
        "border-radius:10px;background:#0876ED;color:#ffffff;font-weight:700;font-size:14px;"
        f'text-decoration:none">{escape(action_label)}</a>'
        if action_label and action_url
        else ""
    )
    return f"""<!doctype html><html lang="en"><body style="margin:0;padding:24px;background:#f4f7fb;
font-family:Arial,Helvetica,sans-serif;color:#0f172a">
<table role="presentation" width="100%" style="max-width:600px;margin:0 auto;background:#ffffff;
border:1px solid #e2e8f0;border-radius:14px;border-top:4px solid #0876ED">
<tr><td style="padding:26px 28px 6px"><p style="margin:0;color:#0876ED;font-size:13px;font-weight:800">
{escape(company)}</p><h1 style="margin:10px 0 14px;font-size:21px">{escape(title)}</h1>{paragraphs}
{f'<table role="presentation" width="100%" style="margin:4px 0 12px">{facts}</table>' if facts else ""}
{grid}{button}</td></tr>
<tr><td style="padding:18px 28px 24px;color:#94a3b8;font-size:12px">Sent by {escape(company)} through Adverse.</td></tr>
</table></body></html>"""


def deliver(
    company_id: UUID,
    *,
    to_email: str | None,
    user_id: UUID | None,
    subject: str,
    title: str,
    lines: Sequence[str],
    rows: Sequence[tuple[str, str]] = (),
    table: Sequence[Sequence[str]] = (),
    action_label: str | None = None,
    action_url: str | None = None,
    company_name: str = "Adverse",
    notify_type: str | None = None,
    notify_link: str = "",
    once_key: str | None = None,
    attachments: Sequence[tuple[bytes, str, str]] = (),
) -> None:
    """Email (in the background) plus a bell notification. Never raises."""
    if notify_type and user_id:
        notification_service.notify(
            company_id, [user_id], notify_type, subject, lines[0] if lines else "", notify_link
        )
    address = to_email or (user_email(user_id) if user_id else None)
    if not address:
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["To"] = address
    text = "\n\n".join(
        [
            title,
            *[line for line in lines if line],
            "\n".join(f"{label}: {value}" for label, value in rows),
            "\n".join(" | ".join(row) for row in table),
            f"{action_label}: {action_url}" if action_label and action_url else "",
        ]
    ).strip()
    message.set_content(text)
    message.add_alternative(
        _html(title, lines, rows, table, action_label, action_url, company_name), subtype="html"
    )
    for content, filename, mime in attachments:
        main, _, sub = mime.partition("/")
        message.add_attachment(
            content, maintype=main, subtype=sub or "octet-stream", filename=filename
        )

    def send() -> None:
        try:
            email_service._send(message, once_key=once_key)
        except Exception:  # noqa: BLE001 - the action itself already happened
            logger.warning("Outgoing mail '%s' failed", subject, exc_info=True)

    threading.Thread(target=send, name="outbound-mail", daemon=True).start()
