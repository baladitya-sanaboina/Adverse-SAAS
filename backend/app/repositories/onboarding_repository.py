"""Onboarding documents (owner request 2026-11-15): templates and the packets sent to people."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class TemplateRow:
    kind: str
    subject: str
    body: str
    updated_at: datetime


@dataclass(frozen=True)
class PacketRow:
    id: UUID
    audience: str
    client_id: UUID | None
    user_id: UUID | None
    recipient_name: str
    recipient_email: str
    documents: list[str]
    fields: dict[str, Any]
    status: str
    expires_at: datetime
    form_data: dict[str, Any]
    signed_name: str | None
    signed_at: datetime | None
    signed_ip: str | None
    opened_at: datetime | None
    sent_count: int
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    company_id: UUID
    invitation_id: UUID | None = None
    uploads: dict[str, Any] = field(default_factory=dict)
    created_by_id: UUID | None = None


@dataclass(frozen=True)
class InvitationTarget:
    """The person an invitation sets up, with what the onboarding mail and page need."""

    id: UUID
    company_id: UUID
    user_id: UUID | None
    client_id: UUID | None
    role_code: str
    name: str
    login_email: str
    gmail: str
    designation: str
    joining_date: date | None
    status: str
    expires_at: datetime
    client_created_at: datetime | None


@dataclass(frozen=True)
class Signer:
    name: str
    title: str | None


@dataclass(frozen=True)
class ClientInfo:
    id: UUID
    name: str
    email: str | None
    contact_name: str | None
    contact_email: str | None
    created_at: datetime
    status: str


@dataclass(frozen=True)
class StaffInfo:
    id: UUID
    name: str
    email: str
    role: str
    created_at: datetime


_PACKET = """
    SELECT p.id, p.audience, p.client_id, p.user_id, p.recipient_name, p.recipient_email,
      p.documents, p.fields, p.status, p.expires_at, p.form_data, p.signed_name, p.signed_at,
      p.signed_ip, p.opened_at, p.sent_count, u.name, p.created_at, p.updated_at, p.company_id,
      p.invitation_id, p.uploads, p.created_by_id
    FROM onboarding_packets p LEFT JOIN users u ON u.id = p.created_by_id
"""


def _packet(row: tuple[Any, ...]) -> PacketRow:
    data = list(row)
    data[6] = list(data[6] or [])
    data[7] = dict(data[7] or {})
    data[10] = dict(data[10] or {})
    data[21] = dict(data[21] or {})
    return PacketRow(*data)


class OnboardingRepository:
    # -- templates ----------------------------------------------------------------------------

    def templates(self, company_id: UUID) -> dict[str, TemplateRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT kind, subject, body, updated_at FROM document_templates WHERE company_id=%s",
                (company_id,),
            )
            return {row[0]: TemplateRow(*row) for row in cursor.fetchall()}

    def save_template(
        self, company_id: UUID, actor_id: UUID, kind: str, subject: str, body: str
    ) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO document_templates (id, company_id, kind, subject, body, updated_by_id, "
                "updated_at) VALUES (%s,%s,%s,%s,%s,%s, NOW() AT TIME ZONE 'UTC') "
                "ON CONFLICT (company_id, kind) DO UPDATE SET subject=EXCLUDED.subject, "
                "body=EXCLUDED.body, updated_by_id=EXCLUDED.updated_by_id, "
                "updated_at=EXCLUDED.updated_at",
                (uuid4(), company_id, kind, subject, body, actor_id),
            )

    def reset_template(self, company_id: UUID, kind: str) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM document_templates WHERE company_id=%s AND kind=%s", (company_id, kind)
            )

    # -- packets ------------------------------------------------------------------------------

    def create_packet(
        self,
        company_id: UUID,
        actor_id: UUID | None,
        audience: str,
        client_id: UUID | None,
        user_id: UUID | None,
        name: str,
        email: str,
        documents: list[str],
        fields: dict[str, Any],
        token_hash: str,
        expires_at: datetime,
        invitation_id: UUID | None = None,
    ) -> UUID:
        packet_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO onboarding_packets (id, company_id, audience, client_id, user_id, "
                "recipient_name, recipient_email, documents, fields, token_hash, expires_at, "
                "created_by_id, invitation_id, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,"
                "%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s, NOW() AT TIME ZONE 'UTC', "
                "NOW() AT TIME ZONE 'UTC')",
                (
                    packet_id,
                    company_id,
                    audience,
                    client_id,
                    user_id,
                    name,
                    email,
                    json.dumps(documents),
                    json.dumps(fields, default=str),
                    token_hash,
                    expires_at,
                    actor_id,
                    invitation_id,
                ),
            )
        return packet_id

    def link_invitation(
        self,
        packet_id: UUID,
        invitation_id: UUID,
        user_id: UUID | None,
        documents: list[str],
        recipient_email: str,
    ) -> None:
        """An older client packet (sent before the portal login existed) joins the login's
        invitation, so the same page also sets the password."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE onboarding_packets SET invitation_id=%s, user_id=COALESCE(%s, user_id), "
                "documents=%s::jsonb, recipient_email=%s, updated_at=NOW() AT TIME ZONE 'UTC' "
                "WHERE id=%s",
                (invitation_id, user_id, json.dumps(documents), recipient_email, packet_id),
            )

    def set_upload(self, packet_id: UUID, key: str, info: dict[str, Any]) -> str | None:
        """Record an uploaded file; returns the storage path of the file it replaces."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT uploads -> %s ->> 'path' FROM onboarding_packets WHERE id=%s FOR UPDATE",
                (key, packet_id),
            )
            row = cursor.fetchone()
            cursor.execute(
                "UPDATE onboarding_packets SET uploads = uploads || jsonb_build_object(%s::text, "
                "%s::jsonb), updated_at=NOW() AT TIME ZONE 'UTC' WHERE id=%s",
                (key, json.dumps(info), packet_id),
            )
            return str(row[0]) if row and row[0] else None

    # -- invitations (one onboarding flow, 2026-11-27) ----------------------------------------

    def invitation_target(self, invitation_id: UUID) -> InvitationTarget | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT i.id, i.company_id, i.user_id, i.client_id, i.role_code, "
                "COALESCE(NULLIF(u.name,''), c.name, i.email), i.email, "
                "COALESCE(NULLIF(i.notification_email,''), i.email), COALESCE(i.designation,''), "
                "i.joining_date, i.status::text, i.expires_at, c.created_at "
                "FROM company_invitations i LEFT JOIN users u ON u.id = i.user_id "
                "LEFT JOIN clients c ON c.id = i.client_id WHERE i.id=%s",
                (invitation_id,),
            )
            row = cursor.fetchone()
            return InvitationTarget(*row) if row else None

    def pending_client_invitation(self, company_id: UUID, client_id: UUID) -> UUID | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM company_invitations WHERE company_id=%s AND client_id=%s "
                "AND status='PENDING' ORDER BY created_at DESC LIMIT 1",
                (company_id, client_id),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def packet_for_invitation(self, invitation_id: UUID) -> PacketRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _PACKET + " WHERE p.invitation_id=%s AND p.status <> 'CANCELLED' "
                "ORDER BY p.created_at DESC LIMIT 1",
                (invitation_id,),
            )
            row = cursor.fetchone()
            return _packet(row) if row else None

    def invitation_token_hash(self, invitation_id: UUID) -> str | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT token_hash FROM company_invitations WHERE id=%s AND status='PENDING'",
                (invitation_id,),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else None

    def set_invitation_expiry(self, invitation_id: UUID, expires_at: datetime) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE company_invitations SET expires_at=%s, updated_at=NOW() "
                "WHERE id=%s AND status='PENDING'",
                (
                    expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at,
                    invitation_id,
                ),
            )

    def signer(self, company_id: UUID, user_id: UUID | None) -> Signer:
        """Who the onboarding mails come from: the admin who added the person."""
        if user_id is None:
            return Signer("Team Adverse", None)
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT u.name, NULLIF(e.designation,''), r.code FROM users u "
                "JOIN roles r ON r.id = u.role_id LEFT JOIN employees e ON e.user_id = u.id "
                "WHERE u.id=%s AND u.company_id=%s",
                (user_id, company_id),
            )
            row = cursor.fetchone()
        if not row:
            return Signer("Team Adverse", None)
        name, designation, role = row
        titles = {"COMPANY_ADMIN": "Admin", "COMPANY_MANAGER": "Manager"}
        return Signer(str(name), designation or titles.get(str(role)))

    def set_profile_image(self, user_id: UUID, url: str) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET profile_image_url=%s, updated_at=NOW() WHERE id=%s",
                (url, user_id),
            )

    def resend(self, packet_id: UUID, token_hash: str, expires_at: datetime) -> None:
        """A fresh link for the same packet (the old link stops working)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE onboarding_packets SET token_hash=%s, expires_at=%s, "
                "sent_count=sent_count+1, updated_at=NOW() AT TIME ZONE 'UTC' WHERE id=%s",
                (token_hash, expires_at, packet_id),
            )

    def packets(self, company_id: UUID, audience: str) -> list[PacketRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _PACKET + " WHERE p.company_id=%s AND p.audience=%s ORDER BY p.created_at DESC",
                (company_id, audience),
            )
            return [_packet(row) for row in cursor.fetchall()]

    def packet(self, company_id: UUID, packet_id: UUID) -> PacketRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(_PACKET + " WHERE p.company_id=%s AND p.id=%s", (company_id, packet_id))
            row = cursor.fetchone()
            return _packet(row) if row else None

    def by_token(self, token_hash: str) -> PacketRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(_PACKET + " WHERE p.token_hash=%s", (token_hash,))
            row = cursor.fetchone()
            return _packet(row) if row else None

    def mark_opened(self, packet_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE onboarding_packets SET status='OPENED', opened_at=NOW() AT TIME ZONE 'UTC', "
                "updated_at=NOW() AT TIME ZONE 'UTC' WHERE id=%s AND status='SENT'",
                (packet_id,),
            )

    def complete(
        self, packet_id: UUID, form: dict[str, Any], name: str, ip: str, agent: str
    ) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE onboarding_packets SET status='COMPLETED', form_data=%s::jsonb, "
                "signed_name=%s, signed_at=NOW() AT TIME ZONE 'UTC', signed_ip=%s, signed_agent=%s, "
                "updated_at=NOW() AT TIME ZONE 'UTC' "
                "WHERE id=%s AND status IN ('SENT','OPENED')",
                (json.dumps(form, default=str), name, ip[:64], agent[:300], packet_id),
            )
            return cursor.rowcount == 1

    def cancel(self, company_id: UUID, packet_id: UUID) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE onboarding_packets SET status='CANCELLED', "
                "updated_at=NOW() AT TIME ZONE 'UTC' "
                "WHERE company_id=%s AND id=%s AND status IN ('SENT','OPENED')",
                (company_id, packet_id),
            )
            return cursor.rowcount == 1

    # -- people -------------------------------------------------------------------------------

    def clients(self, company_id: UUID) -> list[ClientInfo]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.id, c.name, COALESCE(NULLIF(c.email,''), NULLIF(u.recovery_email,''), u.email), "
                "(SELECT TRIM(cc.first_name || ' ' || cc.last_name) FROM client_contacts cc "
                "WHERE cc.client_id = c.id "
                " ORDER BY cc.is_primary DESC, cc.created_at LIMIT 1), "
                "(SELECT cc.email FROM client_contacts cc WHERE cc.client_id = c.id "
                " ORDER BY cc.is_primary DESC, cc.created_at LIMIT 1), "
                "c.created_at, c.status::text "
                "FROM clients c LEFT JOIN users u ON u.id = c.user_id "
                "WHERE c.company_id=%s ORDER BY c.created_at DESC",
                (company_id,),
            )
            return [ClientInfo(*row) for row in cursor.fetchall()]

    def staff(self, company_id: UUID) -> list[StaffInfo]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT u.id, u.name, COALESCE(NULLIF(u.recovery_email,''), u.email), r.code, u.created_at "
                "FROM users u "
                "JOIN roles r ON r.id = u.role_id WHERE u.company_id=%s "
                "AND r.code IN ('COMPANY_EMPLOYEE','COMPANY_MANAGER') AND u.status <> 'INACTIVE' "
                "ORDER BY u.name",
                (company_id,),
            )
            return [StaffInfo(*row) for row in cursor.fetchall()]
