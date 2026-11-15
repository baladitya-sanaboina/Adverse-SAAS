"""Internal mailbox rules (owner request 2026-11-15), without a database or Redis."""

import unittest
from datetime import datetime
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.chat_repository import PersonRef
from app.repositories.mail_repository import MailRow
from app.services.authentication_service import AuthenticationError
from app.services.mail_service import MailService
from tests.test_chat_service import COMPANY, context

ADMIN = PersonRef(uuid4(), "Admin", "COMPANY_ADMIN", None)
MANAGER = PersonRef(uuid4(), "Manager", "COMPANY_MANAGER", None)
EMPLOYEE = PersonRef(uuid4(), "Employee", "COMPANY_EMPLOYEE", None)
CLIENT = PersonRef(uuid4(), "Client", "COMPANY_CLIENT", None)
EVERYONE = [ADMIN, MANAGER, EMPLOYEE, CLIENT]


class FakePeople:
    def people(self, company_id: UUID, roles: tuple[str, ...]) -> list[PersonRef]:
        return [person for person in EVERYONE if person.role in roles]

    def person(self, company_id: UUID, user_id: UUID) -> PersonRef | None:
        return next((person for person in EVERYONE if person.id == user_id), None)


class FakeMail:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def create(self, company_id, sender_id, recipients, subject, body, **kwargs):  # type: ignore[no-untyped-def]
        message_id = uuid4()
        self.sent.append(
            {"id": message_id, "sender": sender_id, "to": recipients, "subject": subject}
        )
        return message_id

    def get(self, company_id, me, message_id):  # type: ignore[no-untyped-def]
        found = next((item for item in self.sent if item["id"] == message_id), None)
        if found is None:
            return None
        return MailRow(
            found["id"],
            found["id"],
            None,
            "PERSONAL",
            found["subject"],
            "",
            "",
            datetime(2026, 11, 15),
            found["sender"],
            "x",
            "COMPANY_ADMIN",
            None,
            None,
            [],
            0,
        )

    def thread(self, company_id, me, thread_id):  # type: ignore[no-untyped-def]
        row = self.get(company_id, me, thread_id)
        return [row] if row else []

    def mark_thread_read(self, me, thread_id):  # type: ignore[no-untyped-def]
        return 0

    def files(self, ids):  # type: ignore[no-untyped-def]
        return []


def ctx(person: PersonRef) -> Any:
    return context(person)


@patch("app.services.mail_service.notification_service")
@patch("app.services.mail_service.realtime")
class MailRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FakeMail()
        self.service = MailService(self.repo, FakePeople(), storage=object())  # type: ignore[arg-type]

    def test_clients_only_write_to_admins_and_only_admins_write_to_clients(self, *_: Any) -> None:
        self.assertEqual([p.id for p in self.service.people(ctx(CLIENT)).people], [ADMIN.id])
        self.assertNotIn(CLIENT.id, [p.id for p in self.service.people(ctx(MANAGER)).people])
        self.assertIn(CLIENT.id, [p.id for p in self.service.people(ctx(ADMIN)).people])
        with self.assertRaises(AuthenticationError) as blocked:
            self.service.send(ctx(CLIENT), [MANAGER.id], "Hi", "Hello", None, [])
        self.assertEqual(blocked.exception.status_code, 403)
        with self.assertRaises(AuthenticationError):
            self.service.send(ctx(EMPLOYEE), [CLIENT.id], "Hi", "Hello", None, [])

    def test_staff_mail_reaches_people_and_rings_their_bell(
        self, realtime: Any, notes: Any
    ) -> None:
        self.service.send(ctx(EMPLOYEE), [MANAGER.id, ADMIN.id], "Footage", "Uploaded", None, [])
        self.assertEqual(self.repo.sent[0]["to"], [MANAGER.id, ADMIN.id])
        self.assertEqual(notes.notify.call_args.args[2], "mail.new")
        with self.assertRaises(AuthenticationError):
            self.service.send(ctx(EMPLOYEE), [], "x", "y", None, [])

    def test_system_mail_is_sent_once_per_person_and_never_raises(
        self, realtime: Any, _: Any
    ) -> None:
        seen: set[str] = set()

        def first(key: str, seconds: int | None = None) -> bool:
            if key in seen:
                return False
            seen.add(key)
            return True

        with patch.object(MailService, "_first_time", staticmethod(first)):
            self.service.system(COMPANY, [EMPLOYEE.id], "Work submitted", "x", once_key="task:1")
            self.service.system(COMPANY, [EMPLOYEE.id], "Work submitted", "x", once_key="task:1")
        self.assertEqual(len(self.repo.sent), 1)
        self.assertIsNone(self.repo.sent[0]["sender"])
        broken = MailService(object(), FakePeople(), storage=object())  # type: ignore[arg-type]
        broken.system(COMPANY, [EMPLOYEE.id], "x", "y")  # logs, does not raise


if __name__ == "__main__":
    unittest.main()
