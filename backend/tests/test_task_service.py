import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.task_repository import (
    BudgetTotals,
    ClientRef,
    PersonRow,
    ServiceRef,
    TaskMutation,
    TaskRow,
)
from app.schemas.authentication import AuthContext
from app.schemas.production import (
    AdminTaskResponse,
    ClientWorkspaceSummaryResponse,
    TaskAssignRequest,
    TaskCreateRequest,
    TaskStatusChangeRequest,
    WorkerTaskFilters,
    WorkerTaskResponse,
    WorkspaceDashboardResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.task_service import TaskService

COMPANY = uuid4()
ADMIN = uuid4()
MANAGER = uuid4()
OTHER_MANAGER = uuid4()
EMPLOYEE = uuid4()
CLIENT = uuid4()
SERVICE = uuid4()
NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)


def context(role: str, user_id: UUID) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        role=role,
        company_id=COMPANY,
        user_type="company",
        session_id=uuid4(),
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def task_row(**overrides: Any) -> TaskRow:
    base = TaskRow(
        id=uuid4(),
        number=1,
        title="Reel for launch",
        description="",
        priority="MEDIUM",
        status="ASSIGNED",
        client_id=CLIENT,
        client_name="Client B",
        client_code="CLI-B",
        service_id=SERVICE,
        service_name="Reel",
        service_code="REEL",
        assignee_user_id=MANAGER,
        assignee_name="Manager X",
        assignee_type="MANAGER",
        monitor_user_id=OTHER_MANAGER,
        monitor_name="Manager Y",
        due_date=None,
        currency="INR",
        client_pricing_model="PER_VIDEO",
        client_price_default=Decimal("400.00"),
        client_price_final=Decimal("400.00"),
        client_price_reason="",
        commission_default=Decimal("300.00"),
        commission_final=Decimal("300.00"),
        commission_reason="",
        created_by_name="Admin",
        created_at=NOW,
        updated_at=NOW,
        assigned_at=NOW,
        started_at=None,
        submitted_at=None,
        approved_at=None,
        completed_at=None,
        cancelled_at=None,
    )
    return replace(base, **overrides)


class FakeTaskRepository:
    def __init__(self) -> None:
        self.rates: dict[tuple[str, UUID], Decimal] = {
            ("CLIENT", CLIENT): Decimal("400.00"),
            ("MANAGER", MANAGER): Decimal("300.00"),
        }
        self.people = {
            MANAGER: PersonRow(MANAGER, "Manager X", "MANAGER", "MGR-1", "x@example.com"),
            OTHER_MANAGER: PersonRow(
                OTHER_MANAGER, "Manager Y", "MANAGER", "MGR-2", "y@example.com"
            ),
            EMPLOYEE: PersonRow(EMPLOYEE, "Employee E", "EMPLOYEE", "EMP-1", "e@example.com"),
        }
        self.task = task_row()
        self.created: dict[str, Any] | None = None
        self.created_price_changes: list[Any] = []
        self.applied: TaskMutation | None = None

    def get_client(self, company_id: UUID, client_id: UUID) -> ClientRef | None:
        return ClientRef(CLIENT, "Client B", "CLI-B", "ACTIVE") if client_id == CLIENT else None

    def get_service(self, company_id: UUID, service_id: UUID) -> ServiceRef | None:
        if service_id != SERVICE:
            return None
        return ServiceRef(SERVICE, "Reel", "REEL", "ACTIVE", "PER_VIDEO")

    def get_person(self, company_id: UUID, user_id: UUID) -> PersonRow | None:
        return self.people.get(user_id)

    def get_assignee(self, company_id: UUID, user_id: UUID) -> PersonRow | None:
        if user_id == ADMIN:
            return PersonRow(ADMIN, "Asha Admin", "ADMIN", "", "admin@example.com")
        return self.people.get(user_id)

    def current_rate(
        self, company_id: UUID, scope: str, subject_id: UUID, service_id: UUID
    ) -> Decimal | None:
        return self.rates.get((scope, subject_id))

    def company_currency(self, company_id: UUID) -> str:
        return "INR"

    def budget_totals(
        self, company_id: UUID, client_id: UUID, exclude_task_id: UUID | None = None
    ) -> BudgetTotals:
        return BudgetTotals(Decimal("12000"), Decimal("11600"), Decimal("0"))

    def create_task(
        self, company_id: UUID, actor_id: UUID, values: dict[str, Any], price_changes: list[Any]
    ) -> UUID:
        self.created = values
        self.created_price_changes = price_changes
        self.task = task_row(
            status=values["status"],
            client_price_default=values["client_price_default"],
            client_price_final=values["client_price_final"],
            assignee_user_id=values["assignee_user_id"],
            assignee_type=values["assignee_type"],
            commission_default=values["commission_default"],
            commission_final=values["commission_final"],
            monitor_user_id=values["monitor_user_id"],
        )
        return self.task.id

    def get_task(self, company_id: UUID, task_id: UUID) -> TaskRow | None:
        return self.task if task_id == self.task.id else None

    def mutate_task(self, company_id: UUID, task_id: UUID, actor_id: UUID, plan: Any) -> None:
        self.applied = plan(self.task)
        self.task = replace(self.task, **self.applied.updates)

    def list_worker_tasks(
        self,
        company_id: UUID,
        user_id: UUID,
        filters: WorkerTaskFilters,
        client_ids: list[UUID] | None = None,
    ) -> tuple[list[TaskRow], int]:
        return [self.task], 1

    def list_history(self, task_id: UUID) -> list[Any]:
        return []

    def list_price_changes(self, task_id: UUID) -> list[Any]:
        return []

    def list_comments(self, task_id: UUID) -> list[Any]:
        return []

    def list_files(self, task_id: UUID) -> list[Any]:
        return []


class FakeAccess:
    """Per-client access (owner request 2026-11-26): user id -> {client id: level}."""

    def __init__(self) -> None:
        self.levels: dict[UUID, dict[UUID, str]] = {}

    def levels_for_user(self, company_id: UUID, user_id: UUID) -> dict[UUID, str]:
        return self.levels.get(user_id, {})


class FakeFinanceRepository:
    def company_timezone(self, company_id: UUID) -> str:
        return "Asia/Kolkata"


def allow_all(*_: Any) -> bool:
    return True


@patch("app.services.task_service.validate_user_action_access", allow_all)
class TaskServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FakeTaskRepository()
        self.access = FakeAccess()
        self.service = TaskService(
            self.repo, FakeFinanceRepository(), access=self.access  # type: ignore[arg-type]
        )

    def create(self, **fields: Any) -> TaskCreateRequest:
        fields.setdefault("due_date", date(2026, 12, 1))
        return TaskCreateRequest(client_id=CLIENT, service_id=SERVICE, title="Reel", **fields)

    # -- who may do what ----------------------------------------------------------------

    def test_only_admin_can_create_and_assign(self) -> None:
        for role, user in (
            ("COMPANY_MANAGER", MANAGER),
            ("COMPANY_EMPLOYEE", EMPLOYEE),
            ("COMPANY_CLIENT", uuid4()),
        ):
            with self.assertRaises(AuthenticationError) as error:
                self.service.create_task(context(role, user), self.create())
            self.assertEqual(error.exception.status_code, 403)
            with self.assertRaises(AuthenticationError):
                self.service.assign_task(
                    context(role, user),
                    self.repo.task.id,
                    TaskAssignRequest(assignee_user_id=MANAGER),
                )

    def test_read_access_sees_the_clients_tasks_but_changes_nothing(self) -> None:
        reader = uuid4()
        self.access.levels[reader] = {CLIENT: "READ"}
        task = self.service.get_worker_task(context("COMPANY_EMPLOYEE", reader), self.repo.task.id)
        self.assertEqual(task.my_role, "CLIENT_READ")
        self.assertEqual(task.allowed_statuses, [])
        self.assertFalse(task.can_comment)
        self.assertFalse(task.can_upload_deliverables)
        self.assertIsNone(task.my_commission)  # never money through client access
        self.assertNotIn("client_price", task.model_dump())
        with self.assertRaises(AuthenticationError) as refused:
            self.service._comment_access(context("COMPANY_EMPLOYEE", reader), self.repo.task.id)
        self.assertEqual(refused.exception.status_code, 403)

    def test_write_access_moves_status_like_a_monitor_but_cannot_approve(self) -> None:
        writer = uuid4()
        self.access.levels[writer] = {CLIENT: "CREATE"}  # Create includes Write
        self.repo.task = replace(self.repo.task, status="SUBMITTED")
        task = self.service.get_worker_task(context("COMPANY_EMPLOYEE", writer), self.repo.task.id)
        self.assertEqual(task.my_role, "CLIENT_WRITE")
        self.assertTrue(task.can_comment)
        self.assertEqual(task.assignee_name, "Manager X")
        self.assertNotIn("APPROVED", task.allowed_statuses)
        self.service.change_status_worker(
            context("COMPANY_EMPLOYEE", writer),
            self.repo.task.id,
            TaskStatusChangeRequest(status="REVIEW"),
        )
        self.assertEqual(self.repo.task.status, "REVIEW")

    def test_access_to_another_client_shows_nothing(self) -> None:
        stranger = uuid4()
        self.access.levels[stranger] = {uuid4(): "CREATE"}
        with self.assertRaises(AuthenticationError) as error:
            self.service.get_worker_task(context("COMPANY_MANAGER", stranger), self.repo.task.id)
        self.assertEqual(error.exception.status_code, 404)

    def test_worker_cannot_see_a_task_that_is_not_theirs(self) -> None:
        outsider = uuid4()
        with self.assertRaises(AuthenticationError) as error:
            self.service.get_worker_task(context("COMPANY_EMPLOYEE", outsider), self.repo.task.id)
        self.assertEqual(error.exception.status_code, 404)  # not 403: ids cannot be probed

    def test_workers_cannot_approve(self) -> None:
        self.repo.task = replace(self.repo.task, status="REVIEW")
        for user in (MANAGER, OTHER_MANAGER):  # assignee and monitor
            with self.assertRaises(AuthenticationError) as error:
                self.service.change_status_worker(
                    context("COMPANY_MANAGER", user),
                    self.repo.task.id,
                    TaskStatusChangeRequest(status="APPROVED"),
                )
            self.assertEqual(error.exception.code, "INVALID_STATUS_CHANGE")

    def test_monitor_can_move_submitted_work_to_review(self) -> None:
        self.repo.task = replace(self.repo.task, status="SUBMITTED")
        self.service.change_status_worker(
            context("COMPANY_MANAGER", OTHER_MANAGER),
            self.repo.task.id,
            TaskStatusChangeRequest(status="REVIEW"),
        )
        self.assertEqual(self.repo.task.status, "REVIEW")

    # -- pricing --------------------------------------------------------------------------

    def test_create_uses_client_rate_and_manager_commission(self) -> None:
        result = self.service.create_task(
            context("COMPANY_ADMIN", ADMIN), self.create(assignee_user_id=MANAGER)
        )
        assert self.repo.created is not None
        self.assertEqual(self.repo.created["client_price_final"], Decimal("400.00"))
        self.assertEqual(self.repo.created["commission_final"], Decimal("300.00"))
        self.assertEqual(self.repo.created["status"], "ASSIGNED")
        self.assertEqual(self.repo.created_price_changes, [])  # defaults used: nothing overridden
        self.assertEqual(result.task.margin, Decimal("100.00"))

    def test_manual_long_video_price_is_recorded_with_reason(self) -> None:
        self.service.create_task(
            context("COMPANY_ADMIN", ADMIN),
            self.create(
                assignee_user_id=MANAGER,
                client_price=Decimal("900"),
                client_price_reason="Long video",
                commission=Decimal("500"),
                commission_reason="Long video",
            ),
        )
        fields = {change[0]: change for change in self.repo.created_price_changes}
        self.assertEqual(
            fields["CLIENT_PRICE"][1:], (Decimal("400.00"), Decimal("900.00"), "Long video")
        )
        self.assertEqual(
            fields["COMMISSION"][1:], (Decimal("300.00"), Decimal("500.00"), "Long video")
        )

    def test_price_required_when_no_rate_is_configured(self) -> None:
        del self.repo.rates[("CLIENT", CLIENT)]
        with self.assertRaises(AuthenticationError) as error:
            self.service.create_task(context("COMPANY_ADMIN", ADMIN), self.create())
        self.assertEqual(error.exception.code, "CLIENT_PRICE_REQUIRED")

    def test_salaried_employee_gets_no_commission(self) -> None:
        self.service.create_task(
            context("COMPANY_ADMIN", ADMIN), self.create(assignee_user_id=EMPLOYEE)
        )
        assert self.repo.created is not None
        self.assertIsNone(self.repo.created["commission_final"])
        with self.assertRaises(AuthenticationError) as error:
            self.service.create_task(
                context("COMPANY_ADMIN", ADMIN),
                self.create(assignee_user_id=EMPLOYEE, commission=Decimal("100")),
            )
        self.assertEqual(error.exception.code, "COMMISSION_NOT_ALLOWED")

    def test_a_task_from_the_tasks_page_goes_into_the_client_calendar(self) -> None:
        # Owner report 2026-11-28: a task made on the Tasks page did not show in the calendar.
        with patch.object(self.service.events, "add_to_calendar") as add:
            self.service.create_task(context("COMPANY_ADMIN", ADMIN), self.create())
        assert self.repo.created is not None
        add.assert_called_once()
        args = add.call_args.args
        self.assertEqual(
            (args[3], args[4], args[5], args[6]), (CLIENT, SERVICE, "Reel", date(2026, 12, 1))
        )

    def test_admin_can_take_a_task_with_no_commission(self) -> None:
        # Owner request 2026-11-28: the Admin does some tasks too.
        self.service.create_task(
            context("COMPANY_ADMIN", ADMIN), self.create(assignee_user_id=ADMIN)
        )
        assert self.repo.created is not None
        self.assertEqual(self.repo.created["assignee_type"], "ADMIN")
        self.assertEqual(self.repo.created["status"], "ASSIGNED")
        self.assertIsNone(self.repo.created["commission_final"])
        with self.assertRaises(AuthenticationError) as error:
            self.service.create_task(
                context("COMPANY_ADMIN", ADMIN),
                self.create(assignee_user_id=ADMIN, commission=Decimal("100")),
            )
        self.assertEqual(error.exception.code, "COMMISSION_NOT_ALLOWED")

    def test_monitor_must_be_a_manager(self) -> None:
        with self.assertRaises(AuthenticationError) as error:
            self.service.create_task(
                context("COMPANY_ADMIN", ADMIN),
                self.create(assignee_user_id=MANAGER, monitor_user_id=EMPLOYEE),
            )
        self.assertEqual(error.exception.code, "MONITOR_MUST_BE_MANAGER")

    def test_budget_warning_when_task_exceeds_budget(self) -> None:
        # Budget 12,000 with 11,600 used: a 900 task goes 500 over.
        result = self.service.create_task(
            context("COMPANY_ADMIN", ADMIN),
            self.create(client_price=Decimal("900"), client_price_reason="Long video"),
        )
        self.assertTrue(result.budget.exceeds_with_new_task)
        self.assertEqual(result.budget.projected_overage, Decimal("500.00"))
        self.assertIn("over budget", result.budget.message)

    # -- privacy --------------------------------------------------------------------------

    def test_worker_and_client_schemas_have_no_internal_money_fields(self) -> None:
        hidden = {
            "client_price",
            "client_price_default",
            "client_price_final",
            "margin",
            "commission",
            "commission_default",
            "revenue",
        }
        for schema in (WorkerTaskResponse, WorkspaceDashboardResponse):
            self.assertFalse(hidden & set(schema.model_fields), schema.__name__)
        client_fields = set(ClientWorkspaceSummaryResponse.model_fields)
        self.assertFalse(
            {"tasks", "items", "commission", "margin", "assignee_name"} & client_fields
        )
        self.assertIn("margin", AdminTaskResponse.model_fields)  # admin still sees it

    def test_commission_visible_only_to_the_assigned_manager(self) -> None:
        own = self.service.list_worker_tasks(
            context("COMPANY_MANAGER", MANAGER), WorkerTaskFilters()
        )
        self.assertEqual(own.items[0].my_commission, Decimal("300.00"))
        monitored = self.service.list_worker_tasks(
            context("COMPANY_MANAGER", OTHER_MANAGER), WorkerTaskFilters()
        )
        self.assertIsNone(monitored.items[0].my_commission)
        self.assertEqual(monitored.items[0].my_role, "MONITOR")


if __name__ == "__main__":
    unittest.main()


class TodayPanelTest(unittest.TestCase):
    """The dashboard's Today panel (owner request 2026-11-19)."""

    @patch("app.services.task_service.validate_user_action_access", return_value=True)
    def test_groups_and_who_sees_review(self, _: Any) -> None:
        from datetime import timedelta as days

        repo = FakeTaskRepository()
        service = TaskService(repo, FakeFinanceRepository())  # type: ignore[arg-type]
        today = service._today(COMPANY)
        rows = [
            task_row(number=1, priority="URGENT", status="IN_PROGRESS", due_date=today - days(2)),
            task_row(number=2, priority="HIGH", status="ASSIGNED", due_date=today),
            task_row(number=3, priority="LOW", status="PENDING", due_date=today + days(3)),
            task_row(number=4, priority="MEDIUM", status="SUBMITTED", due_date=today - days(1)),
            task_row(
                number=5,
                status="REVIEW",
                due_date=today,
                monitor_user_id=MANAGER,
                assignee_user_id=EMPLOYEE,
            ),
            task_row(number=6, status="ASSIGNED", due_date=None),
        ]
        repo.focus = lambda company_id, user_id, until: rows  # type: ignore[attr-defined]
        admin = service.focus_admin(context("COMPANY_ADMIN", ADMIN))
        self.assertEqual([t.code for t in admin.overdue], ["TSK-0001"])
        self.assertEqual(admin.overdue[0].days_left, -2)
        self.assertEqual([t.code for t in admin.due_today], ["TSK-0002"])
        self.assertEqual([t.code for t in admin.this_week], ["TSK-0003"])
        self.assertEqual([t.code for t in admin.to_review], ["TSK-0004", "TSK-0005"])
        manager = service.focus_worker(context("COMPANY_MANAGER", MANAGER))
        self.assertEqual([t.code for t in manager.to_review], ["TSK-0005"])  # they monitor it
        self.assertEqual(manager.to_review[0].my_role, "MONITOR")
        employee = service.focus_worker(context("COMPANY_EMPLOYEE", EMPLOYEE))
        self.assertEqual(employee.to_review, [])  # handed in: waiting on the reviewer


class ToAssignTest(unittest.TestCase):
    """Client calendar items arrive as Pending with nobody assigned (owner request 2026-11-19)."""

    @patch("app.services.task_service.validate_user_action_access", return_value=True)
    def test_unassigned_pending_goes_to_the_admin_to_assign_list(self, _: Any) -> None:
        repo = FakeTaskRepository()
        service = TaskService(repo, FakeFinanceRepository())  # type: ignore[arg-type]
        today = service._today(COMPANY)
        rows = [
            task_row(number=7, status="PENDING", assignee_user_id=None, due_date=today),
            task_row(number=8, status="PENDING", assignee_user_id=None, due_date=None),
        ]
        repo.focus = lambda company_id, user_id, until: rows  # type: ignore[attr-defined]
        admin = service.focus_admin(context("COMPANY_ADMIN", ADMIN))
        self.assertEqual([t.code for t in admin.to_assign], ["TSK-0007", "TSK-0008"])
        self.assertEqual(admin.due_today, [])  # shown once, under To assign
        worker = service.focus_worker(context("COMPANY_MANAGER", MANAGER))
        self.assertEqual(worker.to_assign, [])


class PriceAndDateRulesTest(unittest.TestCase):
    """Owner rules 2026-11-19: no due date, no task; no price, no status change."""

    @patch("app.services.task_service.validate_user_action_access", return_value=True)
    def test_a_task_needs_a_due_date(self, _: Any) -> None:
        service = TaskService(FakeTaskRepository(), FakeFinanceRepository())  # type: ignore[arg-type]
        request = TaskCreateRequest(client_id=CLIENT, service_id=SERVICE, title="Reel")
        with self.assertRaises(AuthenticationError) as refused:
            service.create_task(context("COMPANY_ADMIN", ADMIN), request)
        self.assertEqual(refused.exception.code, "DUE_DATE_REQUIRED")

    def test_status_waits_for_a_price(self) -> None:
        from app.services.task_service import NO_RATE_REASON, _require_price

        no_price = task_row(client_price_final=Decimal("0"), client_price_reason=NO_RATE_REASON)
        with self.assertRaises(AuthenticationError) as refused:
            _require_price(no_price)
        self.assertEqual(refused.exception.code, "CLIENT_PRICE_REQUIRED")
        _require_price(task_row(client_price_final=Decimal("700")))  # a client rate
        _require_price(task_row(client_price_final=Decimal("0"), client_price_reason="Free reel"))


class CalendarTicketTest(unittest.TestCase):
    """A client's calendar item always becomes a task (owner report 2026-11-19)."""

    def test_task_is_made_even_without_a_client_rate(self) -> None:
        repo = FakeTaskRepository()
        repo.rates.pop(("CLIENT", CLIENT))
        repo.calendar_service_choices = lambda company_id, client_id: [SERVICE]  # type: ignore[attr-defined]
        service = TaskService(repo, FakeFinanceRepository())  # type: ignore[arg-type]
        task_id = service.create_calendar_ticket(
            COMPANY, CLIENT, ADMIN, "Reel", "", date(2026, 11, 30)
        )
        self.assertIsNotNone(task_id)
        self.assertEqual(repo.created["status"], "PENDING")
        self.assertEqual(repo.created["client_price_final"], Decimal("0.00"))
        self.assertIn("No client rate", repo.created["client_price_reason"])

    def test_the_client_rate_is_used_when_there_is_one(self) -> None:
        repo = FakeTaskRepository()
        repo.calendar_service_choices = lambda company_id, client_id: [SERVICE]  # type: ignore[attr-defined]
        repo.rates[("CLIENT", CLIENT)] = Decimal("700")
        service = TaskService(repo, FakeFinanceRepository())  # type: ignore[arg-type]
        service.create_calendar_ticket(COMPANY, CLIENT, ADMIN, "Reel", "", date(2026, 11, 30))
        self.assertEqual(repo.created["client_price_final"], Decimal("700.00"))
        self.assertEqual(repo.created["client_price_reason"], "")

    def test_a_team_members_video_is_assigned_to_them_with_automatic_prices(self) -> None:
        repo = FakeTaskRepository()
        repo.calendar_service_choices = lambda company_id, client_id: [SERVICE]  # type: ignore[attr-defined]
        service = TaskService(repo, FakeFinanceRepository())  # type: ignore[arg-type]
        service.create_calendar_ticket(
            COMPANY, CLIENT, MANAGER, "Reel", "", date(2026, 11, 30), assignee_id=MANAGER
        )
        assert repo.created is not None
        self.assertEqual(repo.created["status"], "ASSIGNED")
        self.assertEqual(repo.created["assignee_user_id"], MANAGER)
        self.assertEqual(repo.created["client_price_final"], Decimal("400.00"))  # client rate
        self.assertEqual(repo.created["commission_final"], Decimal("300.00"))  # fixed rate

        service.create_calendar_ticket(
            COMPANY, CLIENT, EMPLOYEE, "Reel", "", date(2026, 11, 30), assignee_id=EMPLOYEE
        )
        self.assertEqual(repo.created["assignee_type"], "EMPLOYEE")
        self.assertIsNone(repo.created["commission_final"])  # salaried

        repo.rates.pop(("MANAGER", MANAGER))  # no fixed rate yet: the admin sets it later
        service.create_calendar_ticket(
            COMPANY, CLIENT, MANAGER, "Reel", "", date(2026, 11, 30), assignee_id=MANAGER
        )
        self.assertEqual(repo.created["status"], "ASSIGNED")
        self.assertIsNone(repo.created["commission_final"])

    def test_a_waiting_task_follows_a_new_service(self) -> None:
        carousel = uuid4()
        repo = FakeTaskRepository()
        repo.get_service = lambda company_id, service_id: ServiceRef(  # type: ignore[method-assign]
            carousel, "Carousel", "CAROUSEL", "ACTIVE", "PER_PIECE"
        )
        repo.rates[("CLIENT", CLIENT)] = Decimal("250")
        repo.task = task_row(status="PENDING", assignee_user_id=None, commission_final=None)
        service = TaskService(repo, FakeFinanceRepository())  # type: ignore[arg-type]
        service.change_calendar_ticket_service(COMPANY, repo.task.id, ADMIN, carousel)
        self.assertEqual(repo.task.service_id, carousel)
        self.assertEqual(repo.task.client_price_final, Decimal("250.00"))
        assert repo.applied is not None
        self.assertEqual(
            repo.applied.price_changes[0][:3],
            ("CLIENT_PRICE", Decimal("400.00"), Decimal("250.00")),
        )

        repo.task = task_row(status="ASSIGNED")  # commission already set from the old service
        service.change_calendar_ticket_service(COMPANY, repo.task.id, ADMIN, carousel)
        self.assertEqual(repo.task.service_id, SERVICE)
