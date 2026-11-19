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
from urllib.parse import urlsplit
from uuid import UUID

from app.core.settings import settings
from app.database.connectivity import database_pool
from app.services.email_service import email_service
from app.services.mail_templates import render_mail
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
    eyebrow: str | None = None,
) -> str:
    """The shared Adverse mail layout (owner request 2026-11-19)."""
    return render_mail(
        title=title,
        eyebrow=eyebrow,
        lines=lines,
        rows=rows,
        table=table,
        action_label=action_label,
        action_url=action_url,
        sign_off=company if company != "Adverse" else "Team Adverse",
        company=company,
    )


def _path(url: str | None) -> str:
    """The in-app path of a link into one of the apps ("https://x/billing?a=1" -> "/billing?a=1")."""
    if not url:
        return ""
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "") if parts.netloc else url


def _to_mailbox(
    company_id: UUID,
    user_id: UUID,
    subject: str,
    title: str,
    lines: Sequence[str],
    rows: Sequence[tuple[str, str]],
    table: Sequence[Sequence[str]],
    action_label: str | None,
    link: str,
    once_key: str | None,
    *,
    has_files: bool,
) -> None:
    try:
        from app.services.mail_service import mail_card, mail_service

        text = "\n".join(
            [
                *[line for line in lines if line],
                "",
                *[f"{label}: {value}" for label, value in rows],
            ]
        ).strip()
        mail_service.system(
            company_id,
            [user_id],
            subject,
            text,
            link,
            "PAYMENT",
            once_key=f"box:{once_key}" if once_key else None,
            notify=False,
            card=mail_card(
                title,
                lines,
                rows,
                table,
                action=action_label,
                note="The PDF was sent to your Gmail with this mail." if has_files else None,
            ),
        )
    except Exception:  # noqa: BLE001
        logger.warning("Mailbox copy of '%s' failed", subject, exc_info=True)


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
    mailbox_user: UUID | None = None,
    eyebrow: str | None = None,
) -> None:
    """Email (in the background) plus a bell notification. Never raises.
    `mailbox_user`: also put the same mail in this person's internal mailbox (owner request
    2026-11-19: payment mails reach both their Gmail and their Adverse mailbox)."""
    if notify_type and user_id:
        notification_service.notify(
            company_id, [user_id], notify_type, subject, lines[0] if lines else "", notify_link
        )
    if mailbox_user:
        _to_mailbox(
            company_id,
            mailbox_user,
            subject,
            title,
            lines,
            rows,
            table,
            action_label,
            notify_link or _path(action_url),
            once_key,
            has_files=bool(attachments),
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
        _html(
            title,
            lines,
            rows,
            table,
            action_label,
            action_url,
            company_name,
            eyebrow or ("Payment" if mailbox_user else None),
        ),
        subtype="html",
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
