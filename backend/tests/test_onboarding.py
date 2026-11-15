"""Onboarding documents (owner request 2026-11-15), without a database or mail server."""

import unittest
from datetime import timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.onboarding_repository import ClientInfo, PacketRow
from app.schemas.onboarding import PublicSubmit
from app.services.authentication_service import AuthenticationError
from app.services.document_templates import BY_KIND, render
from app.services.onboarding_service import OnboardingService, _hash, _now
from tests.test_task_service import context as make_context

ADMIN = uuid4()


class FakeRepo:
    def __init__(self, added_hours_ago: float, email: str | None = "client@agency.in") -> None:
        self.client = ClientInfo(
            uuid4(),
            "Kalpana Studio",
            email,
            "Kalpana",
            None,
            _now() - timedelta(hours=added_hours_ago),
            "ACTIVE",
        )
        self.saved: dict[UUID, PacketRow] = {}
        self.completed: dict[str, Any] = {}

    def clients(self, company_id: UUID) -> list[ClientInfo]:
        return [self.client]

    def packets(self, company_id: UUID, audience: str) -> list[PacketRow]:
        return [p for p in self.saved.values() if p.audience == audience]

    def templates(self, company_id: UUID) -> dict[str, Any]:
        return {}

    def create_packet(self, company_id, actor, audience, client_id, user_id, name, email, docs, fields, token_hash, expires):  # type: ignore[no-untyped-def]
        packet_id = uuid4()
        self.saved[packet_id] = PacketRow(
            packet_id,
            audience,
            client_id,
            user_id,
            name,
            email,
            docs,
            fields,
            "SENT",
            expires,
            {},
            None,
            None,
            None,
            None,
            1,
            "Admin",
            _now(),
            _now(),
            company_id,
        )
        self.hashes = {token_hash: packet_id}
        return packet_id

    def packet(self, company_id: UUID, packet_id: UUID) -> PacketRow | None:
        return self.saved.get(packet_id)

    def by_token(self, token_hash: str) -> PacketRow | None:
        return self.saved.get(self.hashes.get(token_hash, uuid4()))

    def mark_opened(self, packet_id: UUID) -> None:
        pass

    def complete(self, packet_id, form, name, ip, agent):  # type: ignore[no-untyped-def]
        self.completed = {"form": form, "name": name, "ip": ip}
        old = self.saved[packet_id]
        self.saved[packet_id] = old.__class__(
            **{**old.__dict__, "status": "COMPLETED", "signed_name": name}
        )
        return True


class FakeInvoices:
    def company_profile(self, company_id: UUID) -> Any:
        return type(
            "P",
            (),
            {
                "name": "Adverse",
                "email": "hi@adverse.in",
                "phone": "",
                "address": "",
                "website": "",
            },
        )()


class FakeFinance:
    def company_timezone(self, company_id: UUID) -> str:
        return "Asia/Kolkata"

    def company_currency(self, company_id: UUID) -> str:
        return "INR"


def context() -> Any:
    return make_context("COMPANY_ADMIN", ADMIN)


@patch.object(OnboardingService, "_email", lambda self, packet, token: None)
@patch.object(OnboardingService, "_after_accept", lambda self, packet: None)
class OnboardingRulesTest(unittest.TestCase):
    def service(self, repo: FakeRepo) -> OnboardingService:
        return OnboardingService(repo, FakeInvoices(), FakeFinance())  # type: ignore[arg-type]

    def test_client_documents_only_within_60_hours(self) -> None:
        fresh = FakeRepo(added_hours_ago=2)
        packet = self.service(fresh).send_client(context(), fresh.client.id)
        self.assertEqual(
            packet.documents, ["CLIENT_WELCOME", "CLIENT_ONBOARDING", "CLIENT_AGREEMENT"]
        )
        self.assertAlmostEqual(
            (packet.expires_at - fresh.client.created_at).total_seconds(), 60 * 3600, delta=1
        )
        late = FakeRepo(added_hours_ago=61)
        with self.assertRaises(AuthenticationError) as closed:
            self.service(late).send_client(context(), late.client.id)
        self.assertEqual(closed.exception.code, "ONBOARDING_WINDOW_CLOSED")
        no_email = FakeRepo(added_hours_ago=1, email=None)
        with self.assertRaises(AuthenticationError):
            self.service(no_email).send_client(context(), no_email.client.id)

    def test_link_fills_the_agreement_and_needs_acceptance(self) -> None:
        repo = FakeRepo(added_hours_ago=1)
        service = self.service(repo)
        token, token_hash = "t" * 43, _hash("t" * 43)
        with patch.object(
            OnboardingService, "_new_token", staticmethod(lambda: (token, token_hash))
        ):
            service.send_client(context(), repo.client.id)
        view = service.public_view(token)
        agreement = next(doc for doc in view.documents if doc.kind == "CLIENT_AGREEMENT")
        self.assertIn("Adverse", agreement.body)
        self.assertIn("Kalpana Studio", agreement.body)
        self.assertNotIn("{{", agreement.body)
        with self.assertRaises(AuthenticationError) as unticked:
            service.public_submit(
                token, PublicSubmit(form={}, signed_name="Ka", accept=False), "1.1.1.1", "x"
            )
        self.assertEqual(unticked.exception.code, "ACCEPT_REQUIRED")
        with self.assertRaises(AuthenticationError) as missing:
            service.public_submit(
                token, PublicSubmit(form={}, signed_name="Kalpana", accept=True), "1.1.1.1", "x"
            )
        self.assertEqual(missing.exception.code, "FORM_INCOMPLETE")
        done = service.public_submit(
            token,
            PublicSubmit(
                form={"contact_person": "Kalpana", "contact_phone": "9999999999"},
                signed_name="Kalpana",
                accept=True,
            ),
            "1.1.1.1",
            "x",
        )
        self.assertEqual(done.status, "COMPLETED")
        self.assertEqual(repo.completed["ip"], "1.1.1.1")
        with self.assertRaises(AuthenticationError):
            service.public_view("wrong-token-0123456789-abcdef")

    def test_templates_fill_known_placeholders_only(self) -> None:
        text = render(
            BY_KIND["EMPLOYEE_OFFER"].body, {"employee_name": "Ravi", "job_title": "Editor"}
        )
        self.assertIn("Dear Ravi", text)
        self.assertIn("position of Editor", text)
        self.assertNotIn("{{", text)
        lines = BY_KIND["CLIENT_AGREEMENT"].body.splitlines()
        self.assertTrue(any(len(line) > 150 for line in lines))  # paragraphs are not hard-wrapped

    def test_only_the_admin(self) -> None:
        with self.assertRaises(AuthenticationError):
            self.service(FakeRepo(1)).overview(make_context("COMPANY_MANAGER", uuid4()))


if __name__ == "__main__":
    unittest.main()
