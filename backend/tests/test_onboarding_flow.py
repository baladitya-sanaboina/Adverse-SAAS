"""One onboarding flow for clients, employees and managers (owner request 2026-11-27), without a
database or mail server: the onboarding mail, the documents per role, uploads and the password."""

import unittest
from dataclasses import replace
from datetime import date, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.onboarding_repository import InvitationTarget, PacketRow, Signer
from app.schemas.onboarding import PublicSubmit
from app.services.authentication_service import AuthenticationError
from app.services.mail_templates import render_onboarding_mail, render_welcome_mail
from app.services.onboarding_service import OnboardingService, _hash, _now
from tests.test_onboarding import FakeFinance, FakeInvoices

COMPANY = uuid4()
ADMIN = uuid4()


class FlowRepo:
    def __init__(self, role_code: str = "COMPANY_EMPLOYEE") -> None:
        self.target = InvitationTarget(
            id=uuid4(),
            company_id=COMPANY,
            user_id=uuid4(),
            client_id=None,
            role_code=role_code,
            name="Ravi Kumar",
            login_email="ravi@adverseindia.com",
            gmail="ravi@gmail.com",
            designation="Video editor",
            joining_date=date(2026, 12, 1),
            status="PENDING",
            expires_at=_now() + timedelta(days=2),
            client_created_at=None,
        )
        self.saved: dict[UUID, PacketRow] = {}
        self.hashes: dict[str, UUID] = {}
        self.expiry: Any = None
        self.completed = False

    def invitation_target(self, invitation_id: UUID) -> InvitationTarget | None:
        return self.target if invitation_id == self.target.id else None

    def packet_for_invitation(self, invitation_id: UUID) -> PacketRow | None:
        return next((p for p in self.saved.values() if p.invitation_id == invitation_id), None)

    def packets(self, company_id: UUID, audience: str) -> list[PacketRow]:
        return [p for p in self.saved.values() if p.audience == audience]

    def templates(self, company_id: UUID) -> dict[str, Any]:
        return {}

    def create_packet(  # type: ignore[no-untyped-def]
        self,
        company_id,
        actor,
        audience,
        client_id,
        user_id,
        name,
        email,
        docs,
        fields,
        token_hash,
        expires,
        invitation_id=None,
    ):
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
            invitation_id,
            {},
            actor,
        )
        self.hashes = {token_hash: packet_id}
        return packet_id

    def resend(self, packet_id: UUID, token_hash: str, expires: Any) -> None:
        self.hashes = {token_hash: packet_id}

    def set_invitation_expiry(self, invitation_id: UUID, expires_at: Any) -> None:
        self.expiry = expires_at

    def packet(self, company_id: UUID, packet_id: UUID) -> PacketRow | None:
        return self.saved.get(packet_id)

    def by_token(self, token_hash: str) -> PacketRow | None:
        return self.saved.get(self.hashes.get(token_hash, uuid4()))

    def mark_opened(self, packet_id: UUID) -> None:
        pass

    def invitation_token_hash(self, invitation_id: UUID) -> str:
        return "invite-hash"

    def signer(self, company_id: UUID, user_id: UUID | None) -> Signer:
        return Signer("Asha Admin", "Admin")

    def complete(self, packet_id, form, name, ip, agent):  # type: ignore[no-untyped-def]
        self.completed = True
        old = self.saved[packet_id]
        self.saved[packet_id] = replace(old, status="COMPLETED", form_data=form, signed_name=name)
        return True


BASICS = {
    "full_name": "Ravi Kumar",
    "phone": "+91 98765 43210",
    "date_of_birth": "1998-04-02",
    "address": "Hyderabad",
}
STAFF_FORM = {
    **BASICS,
    "emergency_name": "Lakshmi",
    "emergency_phone": "9876500000",
    "bank_holder": "Ravi Kumar",
    "bank_account": "123456789012",
    "bank_ifsc": "hdfc0001234",
}


class OnboardingMailTemplateTest(unittest.TestCase):
    def test_onboarding_mail_is_not_a_welcome_and_carries_the_username(self) -> None:
        html = render_onboarding_mail(
            name="Ravi Kumar",
            audience="EMPLOYEE",
            company="Adverse",
            username="ravi@adverseindia.com",
            agreement_url="https://employee.adverseindia.com/onboarding/abc",
            respond_by="04 Dec 2026, 10:00 AM",
            signer_name="Asha Admin",
            signer_title="Admin",
        )
        self.assertIn("Let&#x27;s get you onboarded,", html)
        self.assertNotIn("Welcome aboard", html)
        self.assertIn("ravi@adverseindia.com", html)
        self.assertIn("Review &amp; Accept Agreement", html)
        self.assertIn("https://employee.adverseindia.com/onboarding/abc", html)
        self.assertIn("offer letter, joining letter and agreement", html)
        self.assertIn("Asha Admin", html)
        self.assertIn("adverse-email-logo-white.png", html)

    def test_welcome_mail_shows_the_password_only_when_given(self) -> None:
        common: dict[str, Any] = {
            "name": "Ravi Kumar",
            "audience": "MANAGER",
            "company": "Adverse",
            "login_url": "https://manager.adverseindia.com/login",
            "username": "ravi@adverseindia.com",
            "signer_name": "Asha Admin",
            "signer_title": "Admin",
        }
        with_password = render_welcome_mail(password="Str0ng!Passw0rd", **common)
        self.assertIn("Str0ng!Passw0rd", with_password)
        self.assertIn("https://manager.adverseindia.com/login", with_password)
        without = render_welcome_mail(password=None, **common)
        self.assertNotIn("Str0ng!Passw0rd", without)
        self.assertIn("never shown here", without)


@patch.object(OnboardingService, "_send_onboarding", lambda *args, **kwargs: None)
@patch.object(OnboardingService, "_after_accept", lambda self, packet, **_: None)
class OnboardingFlowTest(unittest.TestCase):
    def service(self, repo: FlowRepo) -> OnboardingService:
        return OnboardingService(repo, FakeInvoices(), FakeFinance())  # type: ignore[arg-type]

    def start(self, repo: FlowRepo) -> tuple[OnboardingService, str]:
        service = self.service(repo)
        with patch("app.services.onboarding_service.secrets.token_urlsafe", return_value="t" * 43):
            service.start_for_invitation(COMPANY, ADMIN, repo.target.id)
        return service, "t" * 43

    def test_employee_gets_offer_joining_and_agreement_for_seven_days(self) -> None:
        repo = FlowRepo()
        service, token = self.start(repo)
        packet = next(iter(repo.saved.values()))
        self.assertEqual(
            packet.documents, ["EMPLOYEE_OFFER", "EMPLOYEE_JOINING", "EMPLOYEE_AGREEMENT"]
        )
        self.assertEqual(packet.invitation_id, repo.target.id)
        self.assertEqual(packet.recipient_email, "ravi@gmail.com")
        self.assertAlmostEqual((packet.expires_at - _now()).total_seconds(), 7 * 86400, delta=5)
        self.assertEqual(repo.expiry, packet.expires_at)
        view = service.public_view(token)
        self.assertEqual(view.audience, "EMPLOYEE")
        self.assertEqual(view.username, "ravi@adverseindia.com")
        self.assertTrue(view.needs_password)
        self.assertEqual([item.key for item in view.uploads], ["aadhaar", "pan", "photo"])
        self.assertIn("bank_ifsc", [field.key for field in view.form])
        offer = next(doc for doc in view.documents if doc.kind == "EMPLOYEE_OFFER")
        self.assertNotIn("salary:", offer.body.lower())
        self.assertIn("01 December 2026", offer.body)

    def test_manager_gets_manager_documents(self) -> None:
        repo = FlowRepo("COMPANY_MANAGER")
        service, token = self.start(repo)
        packet = next(iter(repo.saved.values()))
        self.assertEqual(
            packet.documents, ["MANAGER_OFFER", "MANAGER_JOINING", "MANAGER_AGREEMENT"]
        )
        self.assertEqual(service.public_view(token).audience, "MANAGER")

    def test_finishing_needs_uploads_a_strong_password_and_activates(self) -> None:
        repo = FlowRepo()
        service, token = self.start(repo)

        def submit(password: str = "Str0ng!Passw0rd", confirm: str | None = None) -> Any:
            return service.public_submit(
                token,
                PublicSubmit(
                    form=STAFF_FORM,
                    signed_name="Ravi Kumar",
                    accept=True,
                    password=password,  # type: ignore[arg-type]
                    confirm_password=confirm or password,  # type: ignore[arg-type]
                ),
                "127.0.0.1",
                "test",
            )

        with self.assertRaises(AuthenticationError) as missing:
            submit()
        self.assertEqual(missing.exception.code, "UPLOADS_MISSING")
        packet_id = next(iter(repo.saved))
        self.assertIn("Profile photo", missing.exception.detail)
        self.assertNotIn("Aadhaar", missing.exception.detail)
        uploads = {
            "photo": {"label": "photo", "name": "me.png", "path": "x/p", "mime": "image/png"}
        }
        repo.saved[packet_id] = replace(repo.saved[packet_id], uploads=uploads)
        with self.assertRaises(AuthenticationError) as weak:
            submit("short")
        self.assertEqual(weak.exception.code, "WEAK_PASSWORD")
        with self.assertRaises(AuthenticationError) as mismatch:
            submit("Str0ng!Passw0rd", "Str0ng!Passw0rd2")
        self.assertEqual(mismatch.exception.code, "PASSWORD_MISMATCH")
        with patch.object(OnboardingService, "_activate") as activate:
            view = submit()
        activate.assert_called_once()
        self.assertTrue(repo.completed)
        self.assertEqual(view.status, "COMPLETED")
        stored = repo.saved[packet_id].form_data
        self.assertEqual(stored["bank_ifsc"], "HDFC0001234")
        self.assertNotIn("bank_account", view.form_data)

    def test_only_basics_are_required(self) -> None:
        repo = FlowRepo()
        service, token = self.start(repo)
        view = service.public_view(token)
        required = {field.key for field in view.form if field.required}
        self.assertEqual(required, {"full_name", "phone", "date_of_birth", "address"})
        self.assertEqual({item.key for item in view.uploads if item.required}, {"photo"})
        packet_id = next(iter(repo.saved))
        photo = {"photo": {"label": "photo", "name": "me.png", "path": "x/p", "mime": "image/png"}}
        repo.saved[packet_id] = replace(repo.saved[packet_id], uploads=photo)
        with patch.object(OnboardingService, "_activate"):
            done = service.public_submit(
                token,
                PublicSubmit(
                    form=BASICS,
                    signed_name="Ravi Kumar",
                    accept=True,
                    password="Str0ng!Passw0rd",  # type: ignore[arg-type]
                    confirm_password="Str0ng!Passw0rd",  # type: ignore[arg-type]
                ),
                "127.0.0.1",
                "test",
            )
        self.assertEqual(done.status, "COMPLETED")

    def test_bad_ifsc_is_refused(self) -> None:
        repo = FlowRepo()
        service, token = self.start(repo)
        with self.assertRaises(AuthenticationError) as bad:
            service.public_submit(
                token,
                PublicSubmit(
                    form={**STAFF_FORM, "bank_ifsc": "12345"},
                    signed_name="Ravi Kumar",
                    accept=True,
                ),
                "127.0.0.1",
                "test",
            )
        self.assertEqual(bad.exception.code, "INVALID_IFSC")

    def test_finished_invitation_cannot_start_again(self) -> None:
        repo = FlowRepo()
        repo.target = replace(repo.target, status="ACCEPTED")
        with self.assertRaises(AuthenticationError) as closed:
            self.service(repo).start_for_invitation(COMPANY, ADMIN, repo.target.id)
        self.assertEqual(closed.exception.code, "INVITATION_CLOSED")
        self.assertNotIn(_hash("t" * 43), repo.hashes)


if __name__ == "__main__":
    unittest.main()
