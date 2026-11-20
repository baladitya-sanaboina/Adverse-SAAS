"""Content calendar access rules (Phase 13), without a database."""

import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.calendar_repository import CalendarEntryRow
from app.repositories.task_repository import ClientRef, ServiceRef
from app.schemas.authentication import AuthContext
from app.schemas.calendar import CalendarEntryCreate, CalendarEntryUpdate
from app.services.authentication_service import AuthenticationError
from app.services.calendar_service import CalendarService

COMPANY = uuid4()
CLIENT_A = ClientRef(id=uuid4(), name="Client A", code="A", status="ACTIVE")
CLIENT_B = ClientRef(id=uuid4(), name="Client B", code="B", status="ACTIVE")
USER_A = uuid4()
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def context(role: str, user_id: UUID | None = None) -> AuthContext:
    return AuthContext(
        user_id=user_id or uuid4(),
        role=role,
        company_id=COMPANY,
        user_type="company",
        session_id=uuid4(),
        issued_at=NOW,
        expires_at=NOW,
    )


def row(client: ClientRef, **changes: Any) -> CalendarEntryRow:
    base = CalendarEntryRow(
        id=uuid4(),
        client_id=client.id,
        client_name=client.name,
        client_code=client.code,
        entry_date=date(2026, 11, 20),
        title="Diwali reel",
        reference_url="",
        notes="",
        no_post=False,
        recorded=False,
        script_ready=False,
        posted_instagram=False,
        posted_youtube=False,
        edited_manual=False,
        script_file_name=None,
        script_storage_path=None,
        script_mime_type=None,
        script_size_bytes=None,
        task_id=None,
        task_number=None,
        task_title=None,
        task_status=None,
        created_by_name="Client A",
        created_at=NOW,
        updated_at=NOW,
    )
    return replace(base, **changes)


class FakeRepository:
    def __init__(self, *rows: CalendarEntryRow) -> None:
        self.rows = {item.id: item for item in rows}
        self.updates: list[dict[str, Any]] = []
        self.deleted: list[UUID] = []
        self.task_clients: dict[UUID, UUID] = {}

    def get(self, company_id: UUID, entry_id: UUID) -> CalendarEntryRow | None:
        return self.rows.get(entry_id)

    def list(self, company_id, client_id, start, end):  # type: ignore[no-untyped-def]
        return [item for item in self.rows.values() if client_id in (None, item.client_id)]

    def create(self, company_id, client_id, actor_id, values):  # type: ignore[no-untyped-def]
        client = CLIENT_A if client_id == CLIENT_A.id else CLIENT_B
        new = row(
            client,
            title=values["title"],
            entry_date=values["entry_date"],
            no_post=values.get("no_post", False),
            service_id=values.get("service_id"),
        )
        self.rows[new.id] = new
        return new.id

    def update(self, company_id: UUID, entry_id: UUID, values: dict[str, Any]) -> None:
        self.updates.append(values)
        self.rows[entry_id] = replace(self.rows[entry_id], **values)

    def delete(self, company_id: UUID, entry_id: UUID) -> bool:
        self.deleted.append(entry_id)
        return self.rows.pop(entry_id, None) is not None

    def set_task(self, company_id: UUID, entry_id: UUID, task_id: UUID | None) -> None:
        self.rows[entry_id] = replace(self.rows[entry_id], task_id=task_id)

    def task_client(self, company_id: UUID, task_id: UUID) -> UUID | None:
        return self.task_clients.get(task_id)


class FakeTickets:
    """Stands in for TaskService's calendar-ticket methods."""

    def __init__(self, statuses: dict[UUID, str] | None = None) -> None:
        self.statuses = statuses or {}
        self.created: list[tuple[str, date]] = []
        self.synced: list[tuple[UUID, str, date]] = []
        self.cancelled: list[UUID] = []
        self.priorities: list[str | None] = []
        self.services: list[UUID | None] = []

    def create_calendar_ticket(self, company_id, client_id, actor_id, title, description, due, priority=None, service_id=None):  # type: ignore[no-untyped-def]
        task_id = uuid4()
        self.statuses[task_id] = "PENDING"
        self.created.append((title, due))
        self.priorities.append(priority)
        self.services.append(service_id)
        return task_id

    def sync_calendar_ticket(self, company_id, task_id, actor_id, title, due):  # type: ignore[no-untyped-def]
        self.synced.append((task_id, title, due))

    def cancel_calendar_ticket(self, company_id, task_id, actor_id):  # type: ignore[no-untyped-def]
        if self.statuses.get(task_id) != "PENDING":
            raise AuthenticationError(409, "ENTRY_IN_PRODUCTION", "Started.")
        self.cancelled.append(task_id)


REEL = uuid4()


class FakeTasks:
    def get_service(self, company_id: UUID, service_id: UUID) -> ServiceRef | None:
        return (
            ServiceRef(REEL, "Reel", "REEL", "ACTIVE", "PER_VIDEO") if service_id == REEL else None
        )

    def calendar_service_choices(self, company_id: UUID, client_id: UUID) -> list[UUID]:
        return [REEL]

    def get_client_for_user(self, company_id: UUID, user_id: UUID) -> ClientRef | None:
        return CLIENT_A if user_id == USER_A else None

    def get_client(self, company_id: UUID, client_id: UUID) -> ClientRef | None:
        return {CLIENT_A.id: CLIENT_A, CLIENT_B.id: CLIENT_B}.get(client_id)


class ServiceChoiceTest(unittest.TestCase):
    """Owner request 2026-11-20: the service of a video is chosen when it is added."""

    def test_service_is_required_unless_no_post(self) -> None:
        with self.assertRaises(ValueError):
            CalendarEntryCreate(entry_date=date(2026, 11, 21), title="Reel")
        CalendarEntryCreate(entry_date=date(2026, 11, 22), title="Rest day", no_post=True)


@patch("app.services.calendar_service.validate_user_action_access", return_value=True)
@patch("app.services.calendar_service.notification_service")
class CalendarServiceTest(unittest.TestCase):
    def service(
        self, *rows: CalendarEntryRow, tickets: FakeTickets | None = None
    ) -> tuple[CalendarService, FakeRepository]:
        repository = FakeRepository(*rows)
        self.tickets = tickets or FakeTickets()
        service = CalendarService(
            repository, FakeTasks(), storage=object(), tickets=self.tickets  # type: ignore[arg-type]
        )
        return service, repository

    def test_client_sees_only_own_entries(self, *_: Any) -> None:
        own, other = row(CLIENT_A), row(CLIENT_B)
        service, _ = self.service(own, other)
        items = service.client_list(context("COMPANY_CLIENT", USER_A), None, None).items
        self.assertEqual([item.id for item in items], [own.id])
        with self.assertRaises(AuthenticationError) as error:
            service.client_update(
                context("COMPANY_CLIENT", USER_A), other.id, CalendarEntryUpdate(recorded=True)
            )
        self.assertEqual(error.exception.status_code, 404)

    def test_client_ticks_progress_but_not_edited(self, *_: Any) -> None:
        entry = row(CLIENT_A)
        service, repository = self.service(entry)
        result = service.client_update(
            context("COMPANY_CLIENT", USER_A),
            entry.id,
            CalendarEntryUpdate(recorded=True, posted_instagram=True),
        )
        self.assertTrue(result.recorded and result.posted_instagram)
        with self.assertRaises(AuthenticationError) as error:
            service.client_update(
                context("COMPANY_CLIENT", USER_A), entry.id, CalendarEntryUpdate(edited_manual=True)
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_edited_follows_the_linked_task(self, *_: Any) -> None:
        service, _ = self.service()
        self.assertFalse(
            service_entry(
                row(CLIENT_A, task_id=uuid4(), task_number=7, task_status="IN_PROGRESS")
            ).edited
        )
        approved = service_entry(
            row(CLIENT_A, task_id=uuid4(), task_number=7, task_status="APPROVED")
        )
        self.assertTrue(approved.edited)
        self.assertEqual(approved.task.code if approved.task else "", "TSK-0007")
        self.assertTrue(service_entry(row(CLIENT_A, edited_manual=True)).edited)

    def test_client_cannot_delete_an_entry_in_production(self, *_: Any) -> None:
        task = uuid4()
        entry = row(CLIENT_A, task_id=task, task_number=3, task_status="IN_PROGRESS")
        service, repository = self.service(entry, tickets=FakeTickets({task: "IN_PROGRESS"}))
        with self.assertRaises(AuthenticationError) as error:
            service.client_delete(context("COMPANY_CLIENT", USER_A), entry.id)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(repository.deleted, [])

    def test_client_delete_cancels_a_pending_ticket(self, *_: Any) -> None:
        task = uuid4()
        entry = row(CLIENT_A, task_id=task, task_number=3, task_status="PENDING")
        service, repository = self.service(entry, tickets=FakeTickets({task: "PENDING"}))
        service.client_delete(context("COMPANY_CLIENT", USER_A), entry.id)
        self.assertEqual(self.tickets.cancelled, [task])
        self.assertEqual(repository.deleted, [entry.id])

    def test_client_entry_becomes_a_ticket(self, notifications: Any, _: Any) -> None:
        notifications.admins.return_value = [uuid4()]
        service, repository = self.service()
        created = service.client_create(
            context("COMPANY_CLIENT", USER_A),
            CalendarEntryCreate(service_id=REEL, entry_date=date(2026, 11, 21), title="Reel"),
        )
        self.assertEqual(self.tickets.created, [("Reel", date(2026, 11, 21))])
        self.assertIsNotNone(repository.rows[created.id].task_id)
        self.assertTrue(notifications.notify.call_args.args[5].startswith("/tasks?task="))

    def test_chosen_service_reaches_the_task(self, *_: Any) -> None:
        service, _ = self.service()
        service.client_create(
            context("COMPANY_CLIENT", USER_A),
            CalendarEntryCreate(service_id=REEL, entry_date=date(2026, 11, 21), title="Reel"),
        )
        self.assertEqual(self.tickets.services, [REEL])

    def test_an_unknown_service_is_refused(self, *_: Any) -> None:
        service, _ = self.service()
        with self.assertRaises(AuthenticationError) as refused:
            service.client_create(
                context("COMPANY_CLIENT", USER_A),
                CalendarEntryCreate(service_id=uuid4(), entry_date=date(2026, 11, 21), title="X"),
            )
        self.assertEqual(refused.exception.code, "SERVICE_NOT_AVAILABLE")

    def test_chosen_priority_reaches_the_task(self, *_: Any) -> None:
        service, _ = self.service()
        service.client_create(
            context("COMPANY_CLIENT", USER_A),
            CalendarEntryCreate(
                service_id=REEL, entry_date=date(2026, 11, 21), title="Reel", priority="URGENT"
            ),
        )
        service.client_create(
            context("COMPANY_CLIENT", USER_A),
            CalendarEntryCreate(service_id=REEL, entry_date=date(2026, 11, 22), title="Reel 2"),
        )
        self.assertEqual(self.tickets.priorities, ["URGENT", None])

    def test_links_without_https_are_fixed_and_words_refused(self, *_: Any) -> None:
        entry = CalendarEntryCreate(
            service_id=REEL,
            entry_date=date(2026, 11, 21),
            title="Reel",
            script_url="docs.google.com/document/d/x",
        )
        self.assertEqual(entry.script_url, "https://docs.google.com/document/d/x")
        with self.assertRaises(ValueError):
            CalendarEntryCreate(
                service_id=REEL, entry_date=date(2026, 11, 21), title="Reel", reference_url="testi"
            )

    def test_no_post_day_is_not_a_ticket(self, *_: Any) -> None:
        service, _ = self.service()
        service.client_create(
            context("COMPANY_CLIENT", USER_A),
            CalendarEntryCreate(
                service_id=REEL, entry_date=date(2026, 11, 22), title="No post", no_post=True
            ),
        )
        self.assertEqual(self.tickets.created, [])

    def test_ticket_follows_new_title_and_date(self, *_: Any) -> None:
        task = uuid4()
        entry = row(CLIENT_A, task_id=task, task_number=3, task_status="PENDING")
        service, _ = self.service(entry, tickets=FakeTickets({task: "PENDING"}))
        service.client_update(
            context("COMPANY_CLIENT", USER_A),
            entry.id,
            CalendarEntryUpdate(title="New idea", entry_date=date(2026, 11, 25)),
        )
        self.assertEqual(self.tickets.synced, [(task, "New idea", date(2026, 11, 25))])

    def test_started_ticket_keeps_its_title(self, *_: Any) -> None:
        entry = row(CLIENT_A, task_id=uuid4(), task_number=3, task_status="IN_PROGRESS")
        service, _ = self.service(entry)
        with self.assertRaises(AuthenticationError) as error:
            service.client_update(
                context("COMPANY_CLIENT", USER_A), entry.id, CalendarEntryUpdate(title="Changed")
            )
        self.assertEqual(error.exception.status_code, 409)
        # Saving the form with the same title and date is fine; ticks still work too.
        service.client_update(
            context("COMPANY_CLIENT", USER_A),
            entry.id,
            CalendarEntryUpdate(title=entry.title, entry_date=entry.entry_date, notes="Updated"),
        )
        service.client_update(
            context("COMPANY_CLIENT", USER_A), entry.id, CalendarEntryUpdate(posted_youtube=True)
        )

    def test_staff_other_than_admin_have_no_access(self, *_: Any) -> None:
        service, _ = self.service(row(CLIENT_A))
        for role in ("COMPANY_MANAGER", "COMPANY_EMPLOYEE"):
            with self.assertRaises(AuthenticationError):
                service.admin_list(context(role), None, None, None)
            with self.assertRaises(AuthenticationError):
                service.client_list(context(role), None, None)

    def test_admin_links_only_the_same_clients_task(self, *_: Any) -> None:
        entry = row(CLIENT_A)
        service, repository = self.service(entry)
        own_task, other_task = uuid4(), uuid4()
        repository.task_clients = {own_task: CLIENT_A.id, other_task: CLIENT_B.id}
        with self.assertRaises(AuthenticationError) as error:
            service.link_task(context("COMPANY_ADMIN"), entry.id, other_task)
        self.assertEqual(error.exception.status_code, 422)
        service.link_task(context("COMPANY_ADMIN"), entry.id, own_task)
        self.assertEqual(repository.rows[entry.id].task_id, own_task)

    def test_client_add_notifies_admins(self, notifications: Any, _: Any) -> None:
        notifications.admins.return_value = [uuid4()]
        service, _ = self.service()
        created = service.client_create(
            context("COMPANY_CLIENT", USER_A),
            CalendarEntryCreate(service_id=REEL, entry_date=date(2026, 11, 21), title="Reel"),
        )
        self.assertEqual(created.client.id, CLIENT_A.id)
        self.assertEqual(notifications.notify.call_args.args[2], "calendar.entry")

    def test_admin_must_choose_a_client(self, *_: Any) -> None:
        service, _ = self.service()
        with self.assertRaises(AuthenticationError) as error:
            service.admin_create(
                context("COMPANY_ADMIN"),
                CalendarEntryCreate(service_id=REEL, entry_date=date(2026, 11, 21), title="Reel"),
            )
        self.assertEqual(error.exception.status_code, 422)

    def test_admin_checks_use_real_permission_actions(self, _: Any, access: Any) -> None:
        # The seed defines VIEW, CREATE, EDIT, DELETE, ASSIGN, MANAGE; "UPDATE" does not exist.
        entry = row(CLIENT_A)
        service, repository = self.service(entry)
        task = uuid4()
        repository.task_clients = {task: CLIENT_A.id}
        admin = context("COMPANY_ADMIN")
        service.admin_list(admin, None, None, None)
        service.admin_update(admin, entry.id, CalendarEntryUpdate(recorded=True))
        service.link_task(admin, entry.id, task)
        service.admin_delete(admin, entry.id)
        actions = {call.args[3] for call in access.call_args_list}
        self.assertTrue(actions <= {"VIEW", "CREATE", "EDIT", "DELETE"}, actions)

    def test_reference_link_must_be_web_address(self, *_: Any) -> None:
        with self.assertRaises(ValueError):
            CalendarEntryCreate(
                service_id=REEL,
                entry_date=date(2026, 11, 21),
                title="Reel",
                reference_url="javascript:alert(1)",
            )


def service_entry(entry: CalendarEntryRow):  # type: ignore[no-untyped-def]
    from app.services.calendar_service import entry_response

    return entry_response(entry)


if __name__ == "__main__":
    unittest.main()
