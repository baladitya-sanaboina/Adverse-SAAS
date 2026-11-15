"""Web Push (owner request 2026-11-15), without a database or a push service."""

import unittest
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from pydantic import SecretStr

from app.repositories.push_repository import SubscriptionRow
from app.services.push_service import PushService


class FakeRepo:
    def __init__(self) -> None:
        self.rows = [SubscriptionRow(uuid4(), uuid4(), "https://push.example/a", "k" * 20, "auth")]
        self.gone: list[Any] = []
        self.ok: list[Any] = []

    def for_users(self, user_ids: list[Any]) -> list[SubscriptionRow]:
        return self.rows

    def sent(self, subscription_id: Any) -> None:
        self.ok.append(subscription_id)

    def failed(self, subscription_id: Any, gone: bool) -> None:
        self.gone.append((subscription_id, gone))


class PushRulesTest(unittest.TestCase):
    def test_off_without_keys(self) -> None:
        with patch("app.services.push_service.settings") as config:
            config.vapid_public_key = ""
            config.vapid_private_key = SecretStr("")
            service = PushService(FakeRepo())  # type: ignore[arg-type]
            self.assertFalse(service.enabled())
            self.assertFalse(service.key().enabled)

    def test_a_browser_that_unsubscribed_is_dropped(self) -> None:
        from pywebpush import WebPushException

        repo = FakeRepo()
        service = PushService(repo)  # type: ignore[arg-type]
        gone = type("Response", (), {"status_code": 410})()
        with (
            patch("app.services.push_service.settings") as config,
            patch("pywebpush.webpush", side_effect=WebPushException("gone", response=gone)),
        ):
            config.vapid_private_key = SecretStr("x")
            service._send_now([uuid4()], {"title": "Hi"})
        self.assertEqual(repo.gone, [(repo.rows[0].id, True)])

    def test_delivered_push_is_recorded(self) -> None:
        repo = FakeRepo()
        service = PushService(repo)  # type: ignore[arg-type]
        with (
            patch("app.services.push_service.settings") as config,
            patch("pywebpush.webpush") as send,
        ):
            config.vapid_private_key = SecretStr("x")
            config.vapid_subject = "mailto:admin@localhost"
            service._send_now([uuid4()], {"title": "Hi", "link": "/mail"})
        self.assertEqual(repo.ok, [repo.rows[0].id])
        self.assertIn('"link": "/mail"', send.call_args.kwargs["data"])


if __name__ == "__main__":
    unittest.main()
