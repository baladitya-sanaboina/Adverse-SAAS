"""In-app notifications: store, deliver live, list and mark read (Phase 10).

`notify()` is called by other services after their change has been saved. It never raises, so a
notification problem cannot undo or fail the user's action.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from app.repositories.notification_repository import NotificationRepository, NotificationRow
from app.schemas.authentication import AuthContext
from app.schemas.notifications import (
    MarkedReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services import realtime
from app.services.authentication_service import AuthenticationError

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, repository: NotificationRepository | None = None):
        self.repository = repository or NotificationRepository()

    # -- sending ---------------------------------------------------------------------------

    def notify(
        self,
        company_id: UUID,
        recipients: Iterable[UUID | None],
        type_: str,
        title: str,
        body: str = "",
        link: str = "",
        data: dict[str, Any] | None = None,
        exclude: UUID | None = None,
    ) -> None:
        user_ids = [
            user_id for user_id in dict.fromkeys(recipients) if user_id and user_id != exclude
        ]
        if not user_ids:
            return
        try:
            stored = self.repository.insert_many(
                company_id, user_ids, type_, title, body, link, data or {}
            )
        except Exception:  # noqa: BLE001 - never fail the caller's action
            logger.warning("Could not store notification %s", type_, exc_info=True)
            return
        for user_id, row in stored.items():
            realtime.publish([user_id], "notification", self._response(row).model_dump(mode="json"))
        for user_id, row in stored.items():
            self._push([user_id], title, body, link, type_, str(row.id))

    @staticmethod
    def _push(
        user_ids: list[UUID], title: str, body: str, link: str, type_: str, tag: str = ""
    ) -> None:
        """The same alert as a Web Push to the person's devices (never raises)."""
        from app.services.push_service import push_service

        push_service.send(
            user_ids,
            {
                "title": title,
                "body": body[:300],
                "link": link or "/",
                "type": type_,
                "tag": tag or type_,
            },
        )

    def notify_chat(
        self,
        company_id: UUID,
        recipients: Iterable[UUID],
        conversation_id: UUID,
        title: str,
        preview: str,
    ) -> None:
        """Chat messages in the bell (owner request 2026-11-14): one notification per chat that
        counts up, so a busy room does not flood it. Read when the chat is opened."""
        for user_id in dict.fromkeys(recipients):
            try:
                result = self.repository.upsert_chat(
                    company_id,
                    user_id,
                    str(conversation_id),
                    title,
                    preview,
                    f"/chat?c={conversation_id}",
                )
            except Exception:  # noqa: BLE001 - never fail sending the message
                logger.warning("Could not store the chat notification", exc_info=True)
                continue
            if result is None:
                continue
            row, replaced = result
            payload = self._response(row).model_dump(mode="json")
            realtime.publish([user_id], "notification", {**payload, "replaced": replaced})
            self._push(
                [user_id], row.title, row.body, row.link, "chat.message", f"chat:{conversation_id}"
            )

    def read_chat(self, company_id: UUID, user_id: UUID, conversation_id: UUID) -> None:
        try:
            if self.repository.mark_chat_read(company_id, user_id, str(conversation_id)):
                unread = self.repository.unread_count(company_id, user_id)
                realtime.publish([user_id], "notification.read", {"unread_count": unread})
        except Exception:  # noqa: BLE001
            logger.warning("Could not mark chat notifications read", exc_info=True)

    def refresh_admins(self, company_id: UUID, kind: str) -> None:
        """Tell every Admin's open pages that money or work changed, including the Admin who made
        the change (owner report 2026-11-28: revenue did not update; notifications skip the
        actor). No bell notice, only a live refresh. Never raises."""
        try:
            realtime.publish(self.admins(company_id), "refresh", {"type": kind})
        except Exception:  # noqa: BLE001 - live refresh is best effort
            logger.warning("Admin refresh failed", exc_info=True)

    def admins(self, company_id: UUID) -> list[UUID]:
        try:
            return self.repository.company_admin_ids(company_id)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load company admins", exc_info=True)
            return []

    def client_user(self, company_id: UUID, client_id: UUID) -> UUID | None:
        try:
            return self.repository.client_user_id(company_id, client_id)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load the client login", exc_info=True)
            return None

    # -- reading (any signed-in company user, own notifications only) ----------------------

    @staticmethod
    def _owner(context: AuthContext) -> tuple[UUID, UUID]:
        if context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_REQUIRED", "Notifications belong to a company workspace."
            )
        return context.company_id, context.user_id

    @staticmethod
    def _response(row: NotificationRow) -> NotificationResponse:
        return NotificationResponse(
            id=row.id,
            type=row.type,
            title=row.title,
            body=row.body,
            link=row.link,
            data=row.data or {},
            read=row.read_at is not None,
            created_at=row.created_at,
        )

    def list(
        self, context: AuthContext, limit: int, before: datetime | None, unread_only: bool
    ) -> NotificationListResponse:
        company_id, user_id = self._owner(context)
        rows = self.repository.list_for_user(company_id, user_id, limit, before, unread_only)
        return NotificationListResponse(
            items=[self._response(row) for row in rows],
            unread_count=self.repository.unread_count(company_id, user_id),
        )

    def unread_count(self, context: AuthContext) -> UnreadCountResponse:
        company_id, user_id = self._owner(context)
        return UnreadCountResponse(unread_count=self.repository.unread_count(company_id, user_id))

    def mark_read(self, context: AuthContext, notification_id: UUID | None) -> MarkedReadResponse:
        company_id, user_id = self._owner(context)
        marked = self.repository.mark_read(company_id, user_id, notification_id)
        unread = self.repository.unread_count(company_id, user_id)
        realtime.publish([user_id], "notification.read", {"unread_count": unread})
        return MarkedReadResponse(marked=marked, unread_count=unread)


notification_service = NotificationService()
