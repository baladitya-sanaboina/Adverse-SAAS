"""Calendar rules (owner request 2026-11-15), without a database."""

import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.agenda_repository import EventRow, TodoRow
from app.repositories.chat_repository import PersonRef
from app.schemas.agenda import EventRequest, TodoUpdate
from app.services.agenda_service import AgendaService
from app.services.authentication_service import AuthenticationError
from tests.test_chat_service import ADMIN, CLIENT, EMPLOYEE, MANAGER, context

OTHER = PersonRef(uuid4(), "Other", "COMPANY_EMPLOYEE", None)
STAFF = [ADMIN, MANAGER, EMPLOYEE, OTHER]
NOW = datetime(2026, 11, 16, 10, 0)


class FakePeople:
    def people(self, company_id: UUID, roles: tuple[str, ...]) -> list[PersonRef]:
        return [person for person in STAFF if person.role in roles]

    def person(self, company_id: UUID, user_id: UUID) -> PersonRef | None:
        return next((person for person in STAFF if person.id == user_id), None)


class FakeAgenda:
    def __init__(self) -> None:
        self.events_: dict[UUID, EventRow] = {}
        self.todos_: dict[UUID, TodoRow] = {}
        self.asked_people: Any = "unset"

    def team(self, company_id: UUID, manager_id: UUID) -> list[UUID]:
        return [EMPLOYEE.id]  # the manager monitors the employee's tasks, not OTHER's

    def events(self, company_id, start, end, people):  # type: ignore[no-untyped-def]
        self.asked_people = people
        return []

    def meetings(self, company_id, start, end, member):  # type: ignore[no-untyped-def]
        return []

    def tasks_due(self, *args):  # type: ignore[no-untyped-def]
        return []

    def todos(self, company_id, owners, start=None, end=None):  # type: ignore[no-untyped-def]
        return [row for row in self.todos_.values() if owners is None or row.owner_id in owners]

    def todo(self, company_id, todo_id):  # type: ignore[no-untyped-def]
        return self.todos_.get(todo_id)

    def create_event(self, company_id, owner_id, fields):  # type: ignore[no-untyped-def]
        event_id = uuid4()
        owner = next(person for person in STAFF if person.id == owner_id)
        self.events_[event_id] = EventRow(
            event_id,
            company_id,
            owner_id,
            owner.name,
            owner.role,
            fields["title"],
            fields["notes"],
            fields["location"],
            fields["starts_at"],
            fields["ends_at"],
            fields["all_day"],
            fields["colour"],
            fields["video"],
            fields.get("conversation_id"),
            fields.get("meeting_id"),
            fields.get("mail_thread_id"),
            [],
        )
        return event_id

    def set_attendees(self, event_id, people):  # type: ignore[no-untyped-def]
        row = self.events_[event_id]
        names = {person.id: person for person in STAFF}
        self.events_[event_id] = row.__class__(
            **{
                **row.__dict__,
                "attendees": [(u, names[u].name, names[u].role, "PENDING") for u in people],
            }
        )

    def event(self, company_id, event_id):  # type: ignore[no-untyped-def]
        return self.events_.get(event_id)


class FakeFinance:
    def company_timezone(self, company_id: UUID) -> str:
        return "Asia/Kolkata"


@patch("app.services.agenda_service.realtime")
class AgendaRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FakeAgenda()
        self.service = AgendaService(self.repo, FakePeople(), object(), FakeFinance())  # type: ignore[arg-type]

    def feed(self, person: PersonRef, scope: Any = "team") -> Any:
        return self.service.feed(context(person), NOW, NOW + timedelta(days=7), scope, None)

    def test_who_sees_whose_calendar(self, _: Any) -> None:
        self.feed(ADMIN)
        self.assertIsNone(self.repo.asked_people)  # everyone
        self.feed(MANAGER)
        self.assertEqual(self.repo.asked_people, [MANAGER.id, EMPLOYEE.id])  # self + team
        self.feed(MANAGER, "mine")
        self.assertEqual(self.repo.asked_people, [MANAGER.id])
        self.feed(EMPLOYEE, "all")
        self.assertEqual(self.repo.asked_people, [EMPLOYEE.id])  # never more than their own
        with self.assertRaises(AuthenticationError):
            self.service.feed(context(MANAGER), NOW, NOW + timedelta(days=7), "team", OTHER.id)
        with self.assertRaises(AuthenticationError):
            self.feed(CLIENT)
        with self.assertRaises(AuthenticationError):  # at most two months at once
            self.service.feed(context(ADMIN), NOW, NOW + timedelta(days=90), "all", None)

    def test_event_times_and_people(self, _: Any) -> None:
        def make(**changes: Any) -> EventRequest:
            base = {
                "title": "Review",
                "starts_at": datetime(2026, 11, 20, 10, tzinfo=UTC),
                "ends_at": datetime(2026, 11, 20, 11, tzinfo=UTC),
                "invite": False,
            }
            return EventRequest(**{**base, **changes})

        with self.assertRaises(AuthenticationError):
            self.service.create_event(
                context(ADMIN), make(ends_at=datetime(2026, 11, 20, 9, tzinfo=UTC))
            )
        with self.assertRaises(AuthenticationError):
            self.service.create_event(
                context(ADMIN), make(ends_at=datetime(2026, 12, 20, 9, tzinfo=UTC))
            )
        with self.assertRaises(AuthenticationError):  # clients are not invited to staff events
            self.service.create_event(context(ADMIN), make(attendee_ids=[CLIENT.id]))
        event = self.service.create_event(
            context(ADMIN), make(attendee_ids=[EMPLOYEE.id, ADMIN.id])
        )
        self.assertEqual([a.person.id for a in event.attendees], [EMPLOYEE.id])  # not myself
        self.assertTrue(event.can_edit)
        day = self.service.create_event(
            context(ADMIN), make(all_day=True, ends_at=datetime(2026, 11, 20, 10, tzinfo=UTC))
        )
        self.assertEqual((day.ends_at - day.starts_at), timedelta(days=1))

    def test_only_the_admin_and_managers_host_group_video(self, _: Any) -> None:
        request = EventRequest(
            title="Sync",
            starts_at=datetime(2026, 11, 20, 10, tzinfo=UTC),
            ends_at=datetime(2026, 11, 20, 11, tzinfo=UTC),
            attendee_ids=[MANAGER.id, ADMIN.id],
            video=True,
        )
        with self.assertRaises(AuthenticationError) as blocked:
            self.service.create_event(context(EMPLOYEE), request)
        self.assertEqual(blocked.exception.code, "GROUP_NOT_ALLOWED")
        with self.assertRaises(AuthenticationError):
            self.service.create_event(
                context(EMPLOYEE), request.model_copy(update={"attendee_ids": []})
            )

    def test_todos_belong_to_their_owner(self, _: Any) -> None:
        todo_id = uuid4()
        self.repo.todos_[todo_id] = TodoRow(
            todo_id, EMPLOYEE.id, "Employee", "Export", "", None, None, "NORMAL", None, NOW
        )
        with self.assertRaises(AuthenticationError):
            self.service.update_todo(context(MANAGER), todo_id, TodoUpdate(done=True))
        with self.assertRaises(AuthenticationError):
            self.service.delete_todo(context(ADMIN), todo_id)


if __name__ == "__main__":
    unittest.main()
