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
        self.tickets: list[dict[str, Any]] = []

    def create(self, company_id, sender_id, recipients, subject, body, **kwargs):  # type: ignore[no-untyped-def]
        message_id = uuid4()
        pairs = [item if isinstance(item, tuple) else (item, "TO") for item in recipients]
        self.sent.append(
            {
                "id": message_id,
                "sender": sender_id,
                "to": [user for user, kind in pairs if kind == "TO"],
                "pairs": pairs,
                "subject": subject,
                "status": kwargs.get("status", "SENT"),
                "kind": kwargs.get("kind", "PERSONAL"),
                "thread": kwargs.get("thread_id") or message_id,
            }
        )
        return message_id

    def get(self, company_id, me, message_id):  # type: ignore[no-untyped-def]
        found = next((item for item in self.sent if item["id"] == message_id), None)
        if found is None:
            return None
        names = {person.id: person for person in EVERYONE}
        return MailRow(
            found["id"],
            found["thread"],
            None,
            found["kind"],
            found["subject"],
            "",
            "",
            datetime(2026, 11, 15),
            found["sender"],
            "x",
            "COMPANY_ADMIN",
            None,
            None,
            [(u, names[u].name, kind, names[u].role) for u, kind in found["pairs"]],
            0,
            found["status"],
        )

    def thread(self, company_id, me, thread_id, trash=False):  # type: ignore[no-untyped-def]
        return [
            row
            for item in self.sent
            if item["thread"] == thread_id
            and (row := self.get(company_id, me, item["id"])) is not None
        ]

    def mark_thread_read(self, me, thread_id):  # type: ignore[no-untyped-def]
        return 0

    def files(self, ids):  # type: ignore[no-untyped-def]
        return []

    def ticket_for_threads(self, company_id, threads):  # type: ignore[no-untyped-def]
        return {}

    def create_ticket(self, company_id, thread_id, subject, priority, raised_by):  # type: ignore[no-untyped-def]
        self.tickets.append({"thread": thread_id, "priority": priority, "by": raised_by})
        return uuid4()

    def ticket(self, company_id, ticket_id):  # type: ignore[no-untyped-def]
        return self.ticket_row

    def update_ticket(self, ticket_id, changes):  # type: ignore[no-untyped-def]
        self.ticket_changes = changes


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
        self.assertEqual(notes.notify.call_args.args[5], f"/mail?m={self.repo.sent[0]['id']}")
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

    def test_bcc_is_private_and_cc_is_shown(self, *_: Any) -> None:
        sent = self.service.send(
            ctx(ADMIN), [MANAGER.id], "Plan", "Hi", None, [], cc=[EMPLOYEE.id], bcc=[CLIENT.id]
        )
        self.assertEqual([p.id for p in sent.items[0].bcc], [CLIENT.id])  # the sender sees Bcc
        message = sent.items[0].id
        for person, sees_bcc in ((MANAGER, []), (EMPLOYEE, []), (CLIENT, [CLIENT.id])):
            item = self.service._items([self.repo.get(COMPANY, person.id, message)], person.id)[0]
            self.assertEqual([p.id for p in item.bcc], sees_bcc, person.name)
            self.assertEqual([p.id for p in item.cc], [EMPLOYEE.id])
        with self.assertRaises(AuthenticationError):  # Cc follows the same who-to-whom rules
            self.service.send(ctx(EMPLOYEE), [MANAGER.id], "x", "y", None, [], cc=[CLIENT.id])

    def test_a_ticket_always_reaches_the_admins(self, *_: Any) -> None:
        self.service.send(
            ctx(EMPLOYEE), [MANAGER.id], "Laptop broken", "Help", None, [], ticket_priority="HIGH"
        )
        pairs = dict(self.repo.sent[0]["pairs"])
        self.assertEqual(pairs, {MANAGER.id: "TO", ADMIN.id: "CC"})
        self.assertEqual(self.repo.sent[0]["kind"], "TICKET")
        self.assertEqual(self.repo.tickets[0]["priority"], "HIGH")
        with self.assertRaises(AuthenticationError):  # tickets are new mail, sent now
            self.service.send(
                ctx(EMPLOYEE),
                [ADMIN.id],
                "x",
                "y",
                self.repo.sent[0]["id"],
                [],
                ticket_priority="LOW",
            )

    def test_schedule_send_must_be_in_the_future_and_does_not_ring(
        self, realtime: Any, notes: Any
    ) -> None:
        from datetime import UTC, timedelta

        with self.assertRaises(AuthenticationError) as past:
            self.service.send(
                ctx(ADMIN),
                [MANAGER.id],
                "x",
                "y",
                None,
                [],
                scheduled_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        self.assertEqual(past.exception.code, "SCHEDULE_IN_PAST")
        self.service.send(
            ctx(ADMIN),
            [MANAGER.id],
            "Later",
            "y",
            None,
            [],
            scheduled_at=datetime.now(UTC) + timedelta(hours=2),
        )
        self.assertEqual(self.repo.sent[0]["status"], "SCHEDULED")
        notes.notify.assert_not_called()

    def test_only_the_admin_or_assignee_changes_a_ticket(self, *_: Any) -> None:
        from app.repositories.mail_repository import TicketRow
        from app.schemas.mail import MailTicketUpdate

        now = datetime(2026, 11, 15)
        self.repo.ticket_row = TicketRow(
            uuid4(),
            7,
            uuid4(),
            "Laptop",
            "NORMAL",
            "OPEN",
            EMPLOYEE.id,
            "Employee",
            "COMPANY_EMPLOYEE",
            None,
            None,
            None,
            now,
            now,
            None,
            None,
            now,
            1,
        )
        with self.assertRaises(AuthenticationError):
            self.service.update_ticket(ctx(MANAGER), uuid4(), MailTicketUpdate(status="CLOSED"))
        with self.assertRaises(AuthenticationError):  # clients cannot be assignees
            self.service.update_ticket(ctx(ADMIN), uuid4(), MailTicketUpdate(assignee_id=CLIENT.id))
        ticket = self.service.update_ticket(ctx(ADMIN), uuid4(), MailTicketUpdate(status="CLOSED"))
        self.assertEqual(self.repo.ticket_changes, {"status": "CLOSED"})
        self.assertEqual(ticket.code, "TKT-0007")


if __name__ == "__main__":
    unittest.main()
