"""Web Push (owner request 2026-11-15): every bell notification also reaches the person's
phones and computers that allowed notifications, even when the app is closed. The installed
app's service worker shows it (and stays quiet when the app is open and in front, where the page
shows its own alert). Sending runs in the background and never slows down or fails the action.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

from app.core.settings import settings
from app.repositories.push_repository import PushRepository, SubscriptionRow
from app.schemas.authentication import AuthContext
from app.schemas.push import PushKeyResponse, PushSubscribeRequest
from app.services.authentication_service import AuthenticationError

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="push")


class PushService:
    def __init__(self, repository: PushRepository | None = None) -> None:
        self.repository = repository or PushRepository()

    @staticmethod
    def enabled() -> bool:
        return bool(settings.vapid_public_key and settings.vapid_private_key.get_secret_value())

    def key(self) -> PushKeyResponse:
        return PushKeyResponse(enabled=self.enabled(), public_key=settings.vapid_public_key)

    def subscribe(self, context: AuthContext, request: PushSubscribeRequest, agent: str) -> None:
        if not self.enabled():
            raise AuthenticationError(409, "PUSH_OFF", "Push notifications are not set up here.")
        self.repository.save(
            context.user_id, request.endpoint, request.keys.p256dh, request.keys.auth, agent
        )

    def unsubscribe(self, context: AuthContext, endpoint: str) -> None:
        self.repository.remove(context.user_id, endpoint)

    def send(self, user_ids: list[UUID], payload: dict[str, Any]) -> None:
        """Queue a push to every device of these people. Never raises."""
        if not self.enabled() or not user_ids:
            return
        try:
            _pool.submit(self._send_now, list(dict.fromkeys(user_ids)), payload)
        except Exception:  # noqa: BLE001
            logger.warning("Push could not be queued", exc_info=True)

    def _send_now(self, user_ids: list[UUID], payload: dict[str, Any]) -> None:
        try:
            subscriptions = self.repository.for_users(user_ids)
        except Exception:  # noqa: BLE001
            logger.warning("Push subscriptions could not be read", exc_info=True)
            return
        data = json.dumps(payload)[:3500]
        for subscription in subscriptions:
            self._deliver(subscription, data)

    def _deliver(self, subscription: SubscriptionRow, data: str) -> None:
        from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=data,
                vapid_private_key=settings.vapid_private_key.get_secret_value(),
                vapid_claims={"sub": settings.vapid_subject},
                ttl=6 * 3600,
                headers={"Urgency": "high"},
                timeout=10,
            )
            self.repository.sent(subscription.id)
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            self.repository.failed(subscription.id, gone=status in (404, 410))
            if status not in (404, 410):
                logger.info("Push failed (%s) for one device", status)
        except Exception:  # noqa: BLE001
            self.repository.failed(subscription.id, gone=False)
            logger.info("Push failed for one device", exc_info=True)


push_service = PushService()
