"""Task workflow: creation with price snapshot, assignment, status changes, comments and files.

Rules (docs/ProductionManagementPlan.md, sections 3.2 and 4):
- Only the Company Admin creates, assigns, re-prices and approves tasks.
- An assignee moves their own task up to Submitted; a monitoring manager only changes status,
  up to Review. Approve/Complete are Admin-only.
- Workers only ever see tasks they are assigned to or monitor, without client prices or margin.
- Clients have no task access at all.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import UploadFile

from app.repositories.finance_repository import FinanceRepository
from app.repositories.task_repository import (
    PersonRow,
    TaskMutation,
    TaskNotFound,
    TaskRepository,
    TaskRow,
)
from app.schemas.authentication import AuthContext
from app.schemas.production import (
    AdminTaskDetailResponse,
    AdminTaskListResponse,
    AdminTaskResponse,
    AssigneeOptionResponse,
    BudgetCheckResponse,
    NamedRef,
    PersonRef,
    PriceChangeResponse,
    PricingPreviewResponse,
    StatusHistoryResponse,
    TaskAssignRequest,
    TaskCommentRequest,
    TaskCommentResponse,
    TaskCreateRequest,
    TaskFileKind,
    TaskFileResponse,
    TaskListFilters,
    TaskMonitorRequest,
    TaskPriceChangeRequest,
    TaskStatusChangeRequest,
    TaskUpdateRequest,
    TaskWriteResponse,
    WorkerTaskDetailResponse,
    WorkerTaskFilters,
    WorkerTaskListResponse,
    WorkerTaskResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access
from app.services.production_rules import (
    BILLABLE_STATUSES,
    CLOSED_STATUSES,
    TaskActorRole,
    allowed_transitions,
    budget_position,
    calendar_priority,
    can_transition,
    is_billable,
    is_overdue,
    money,
    status_timestamp_updates,
    task_margin,
)
from app.services.task_events import NoTaskEvents, TaskEvents
from app.services.task_file_storage import TaskFileStorage

WORKER_ROLES = {"COMPANY_MANAGER": "MANAGER", "COMPANY_EMPLOYEE": "EMPLOYEE"}
# Statuses in which the assignee is still working and may add or remove deliverables.
_WORKING_STATUSES = frozenset({"ASSIGNED", "IN_PROGRESS", "SUBMITTED", "REVIEW"})
STATUS_LABELS = {
    "PENDING": "Pending",
    "ASSIGNED": "Assigned",
    "IN_PROGRESS": "In Progress",
    "SUBMITTED": "Submitted",
    "REVIEW": "Review",
    "APPROVED": "Approved",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
}


def _not_found() -> AuthenticationError:
    return AuthenticationError(404, "TASK_NOT_FOUND", "Task was not found.")


class TaskService:
    def __init__(
        self,
        repository: TaskRepository | None = None,
        finance_repository: FinanceRepository | None = None,
        storage: TaskFileStorage | None = None,
        events: TaskEvents | None = None,
    ):
        self.repository = repository or TaskRepository()
        self.finance = finance_repository or FinanceRepository()
        self.storage = storage or TaskFileStorage()
        # Notifications are sent only by the app's own instance (see the bottom of this file).
        self.events = events or NoTaskEvents()

    # -- access ----------------------------------------------------------------------------

    @staticmethod
    def _admin(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Only the Company Admin can manage tasks."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "TASKS", action):
            raise AuthenticationError(
                403, f"TASKS_{action}_REQUIRED", f"Tasks {action.lower()} permission is required."
            )
        return context.company_id

    @staticmethod
    def _worker(context: AuthContext) -> tuple[UUID, str]:
        role = WORKER_ROLES.get(context.role)
        if role is None or context.company_id is None:
            raise AuthenticationError(
                403, "TEAM_MEMBER_REQUIRED", "Only managers and employees have a task workspace."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "TASKS", "VIEW"):
            raise AuthenticationError(
                403, "TASKS_VIEW_REQUIRED", "Tasks view permission is required."
            )
        return context.company_id, role

    def _today(self, company_id: UUID) -> date:
        try:
            zone = ZoneInfo(self.finance.company_timezone(company_id))
        except Exception:
            zone = ZoneInfo("UTC")
        return datetime.now(zone).date()

    def _load(self, company_id: UUID, task_id: UUID) -> TaskRow:
        row = self.repository.get_task(company_id, task_id)
        if row is None:
            raise _not_found()
        return row

    @staticmethod
    def _worker_role(row: TaskRow, user_id: UUID) -> TaskActorRole | None:
        if row.assignee_user_id == user_id:
            return "ASSIGNEE"
        if row.monitor_user_id == user_id:
            return "MONITOR"
        return None

    def _load_for_worker(
        self, company_id: UUID, user_id: UUID, task_id: UUID
    ) -> tuple[TaskRow, TaskActorRole]:
        row = self.repository.get_task(company_id, task_id)
        role = self._worker_role(row, user_id) if row else None
        if row is None or role is None:
            # Same answer for "missing" and "not yours", so task ids cannot be probed.
            raise _not_found()
        return row, role

    def _require_person(self, company_id: UUID, user_id: UUID, code: str, label: str) -> PersonRow:
        person = self.repository.get_person(company_id, user_id)
        if person is None:
            raise AuthenticationError(
                404, code, f"{label} was not found or is not an active manager or employee."
            )
        return person

    def _require_monitor(
        self, company_id: UUID, monitor_id: UUID, assignee_id: UUID | None
    ) -> PersonRow:
        monitor = self._require_person(company_id, monitor_id, "MONITOR_NOT_FOUND", "Monitor")
        if monitor.role != "MANAGER":
            raise AuthenticationError(
                422, "MONITOR_MUST_BE_MANAGER", "Only a manager can be set as a task monitor."
            )
        if assignee_id is not None and monitor_id == assignee_id:
            raise AuthenticationError(
                422,
                "MONITOR_IS_ASSIGNEE",
                "The monitor must be a different person from the assignee.",
            )
        return monitor

    # -- response builders -----------------------------------------------------------------

    def _admin_task(self, row: TaskRow, today: date) -> AdminTaskResponse:
        has_assignee = row.assignee_user_id is not None
        return AdminTaskResponse(
            id=row.id,
            code=row.code,
            title=row.title,
            description=row.description,
            priority=row.priority,
            status=row.status,
            client=NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
            service=NamedRef(id=row.service_id, name=row.service_name, code=row.service_code),
            assignee=(
                PersonRef(
                    id=row.assignee_user_id,
                    name=row.assignee_name or "",
                    role=row.assignee_type,
                )
                if row.assignee_user_id is not None
                else None
            ),
            monitor=(
                NamedRef(id=row.monitor_user_id, name=row.monitor_name or "")
                if row.monitor_user_id is not None
                else None
            ),
            due_date=row.due_date,
            is_overdue=is_overdue(row.status, row.due_date, today),
            billable=is_billable(row.status),
            currency=row.currency,
            client_pricing_model=row.client_pricing_model,
            client_price_default=row.client_price_default,
            client_price=money(row.client_price_final),
            client_price_reason=row.client_price_reason,
            commission_default=row.commission_default,
            commission=row.commission_final,
            commission_reason=row.commission_reason,
            margin=task_margin(row.client_price_final, row.commission_final),
            allowed_statuses=allowed_transitions("ADMIN", row.status, has_assignee),
            files_count=row.files_count,
            comments_count=row.comments_count,
            created_by_name=row.created_by_name,
            created_at=row.created_at,
            updated_at=row.updated_at,
            assigned_at=row.assigned_at,
            started_at=row.started_at,
            submitted_at=row.submitted_at,
            approved_at=row.approved_at,
            completed_at=row.completed_at,
            cancelled_at=row.cancelled_at,
        )

    def _shared_detail(
        self, task_id: UUID
    ) -> tuple[list[StatusHistoryResponse], list[TaskCommentResponse], list[TaskFileResponse]]:
        history = [
            StatusHistoryResponse(
                id=item.id,
                from_status=item.from_status,
                to_status=item.to_status,
                note=item.note,
                actor_name=item.actor_name,
                created_at=item.created_at,
            )
            for item in self.repository.list_history(task_id)
        ]
        comments = [
            TaskCommentResponse(**item.__dict__) for item in self.repository.list_comments(task_id)
        ]
        files = [
            TaskFileResponse(
                id=item.id,
                kind=item.kind,
                file_name=item.file_name,
                mime_type=item.mime_type,
                size_bytes=item.size_bytes,
                uploaded_by_name=item.uploaded_by_name,
                created_at=item.created_at,
            )
            for item in self.repository.list_files(task_id)
        ]
        return history, comments, files

    def _admin_detail(self, company_id: UUID, task_id: UUID) -> AdminTaskDetailResponse:
        row = self._load(company_id, task_id)
        history, comments, files = self._shared_detail(task_id)
        price_changes = [
            PriceChangeResponse(
                id=item.id,
                field=item.field,
                old_amount=item.old_amount,
                new_amount=item.new_amount,
                reason=item.reason,
                actor_name=item.actor_name,
                created_at=item.created_at,
            )
            for item in self.repository.list_price_changes(task_id)
        ]
        return AdminTaskDetailResponse(
            **self._admin_task(row, self._today(company_id)).model_dump(),
            status_history=history,
            price_changes=price_changes,
            comments=comments,
            files=files,
        )

    def _worker_task(self, row: TaskRow, user_id: UUID, today: date) -> WorkerTaskResponse:
        role = self._worker_role(row, user_id)
        if role is None:
            raise _not_found()
        own_manager_task = role == "ASSIGNEE" and row.assignee_type == "MANAGER"
        return WorkerTaskResponse(
            id=row.id,
            code=row.code,
            title=row.title,
            description=row.description,
            priority=row.priority,
            status=row.status,
            client_name=row.client_name,
            service_name=row.service_name,
            my_role=role,
            assignee_name=row.assignee_name if role == "MONITOR" else None,
            due_date=row.due_date,
            is_overdue=is_overdue(row.status, row.due_date, today),
            my_commission=row.commission_final if own_manager_task else None,
            currency=row.currency,
            allowed_statuses=allowed_transitions(role, row.status, True),
            can_upload_deliverables=role == "ASSIGNEE" and row.status in _WORKING_STATUSES,
            files_count=row.files_count,
            comments_count=row.comments_count,
            created_at=row.created_at,
            assigned_at=row.assigned_at,
            submitted_at=row.submitted_at,
            approved_at=row.approved_at,
            completed_at=row.completed_at,
        )

    def _worker_detail(
        self, company_id: UUID, user_id: UUID, task_id: UUID
    ) -> WorkerTaskDetailResponse:
        row, _ = self._load_for_worker(company_id, user_id, task_id)
        history, comments, files = self._shared_detail(task_id)
        return WorkerTaskDetailResponse(
            **self._worker_task(row, user_id, self._today(company_id)).model_dump(),
            status_history=history,
            comments=comments,
            files=files,
        )

    def budget_check(
        self,
        company_id: UUID,
        client_id: UUID,
        client_name: str,
        currency: str,
        task_amount: Decimal | None,
        exclude_task_id: UUID | None = None,
    ) -> BudgetCheckResponse:
        totals = self.repository.budget_totals(company_id, client_id, exclude_task_id)
        position = budget_position(totals.total, totals.used, totals.committed, task_amount)
        if not position.has_budget:
            message = f"No budget is set for {client_name}."
        elif position.exceeds_with_new_task:
            message = (
                f"This task takes {client_name} over budget by "
                f"{currency} {position.projected_overage:,.2f}."
            )
        elif task_amount is not None:
            left = position.total - position.projected_used
            message = f"{currency} {left:,.2f} of {client_name}'s budget is left after this task."
        else:
            message = f"{currency} {position.remaining:,.2f} of {client_name}'s budget is left."
        return BudgetCheckResponse(
            has_budget=position.has_budget,
            currency=currency,
            total=position.total,
            used=position.used,
            committed=position.committed,
            remaining=position.remaining,
            overage=position.overage,
            projected_used=position.projected_used,
            projected_overage=position.projected_overage,
            exceeds_with_new_task=position.exceeds_with_new_task,
            message=message,
        )

    def _write_response(self, company_id: UUID, task_id: UUID) -> TaskWriteResponse:
        detail = self._admin_detail(company_id, task_id)
        amount = None if detail.status == "CANCELLED" else detail.client_price
        budget = self.budget_check(
            company_id, detail.client.id, detail.client.name, detail.currency, amount, task_id
        )
        return TaskWriteResponse(task=detail, budget=budget)

    # -- admin: reads ----------------------------------------------------------------------

    def list_tasks(self, context: AuthContext, filters: TaskListFilters) -> AdminTaskListResponse:
        company_id = self._admin(context, "VIEW")
        today = self._today(company_id)
        rows, total = self.repository.list_tasks(company_id, filters, today)
        return AdminTaskListResponse(
            items=[self._admin_task(row, today) for row in rows],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=max(1, (total + filters.page_size - 1) // filters.page_size),
        )

    def get_task(self, context: AuthContext, task_id: UUID) -> AdminTaskDetailResponse:
        return self._admin_detail(self._admin(context, "VIEW"), task_id)

    def assignee_options(self, context: AuthContext) -> list[AssigneeOptionResponse]:
        company_id = self._admin(context, "VIEW")
        return [
            AssigneeOptionResponse(
                id=person.id,
                name=person.name,
                role=person.role,
                code=person.code,
                email=person.email,
            )
            for person in self.repository.list_people(company_id)
        ]

    def pricing_preview(
        self,
        context: AuthContext,
        client_id: UUID,
        service_id: UUID,
        assignee_user_id: UUID | None,
        client_price: Decimal | None,
    ) -> PricingPreviewResponse:
        """Default rates and budget impact, so the Admin sees them before saving a task."""
        company_id = self._admin(context, "VIEW")
        client = self.repository.get_client(company_id, client_id)
        if client is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        service = self.repository.get_service(company_id, service_id)
        if service is None:
            raise AuthenticationError(404, "SERVICE_NOT_FOUND", "Service was not found.")
        default_price = self.repository.current_rate(company_id, "CLIENT", client_id, service_id)
        person = None
        commission_default = None
        if assignee_user_id is not None:
            person = self._require_person(
                company_id, assignee_user_id, "ASSIGNEE_NOT_FOUND", "Assignee"
            )
            if person.role == "MANAGER":
                commission_default = self.repository.current_rate(
                    company_id, "MANAGER", person.id, service_id
                )
        currency = self.repository.company_currency(company_id)
        amount = client_price if client_price is not None else default_price
        return PricingPreviewResponse(
            client=NamedRef(id=client.id, name=client.name, code=client.code),
            service=NamedRef(id=service.id, name=service.name, code=service.code),
            client_pricing_model=service.client_pricing_model,
            client_price_default=default_price,
            assignee=(
                PersonRef(id=person.id, name=person.name, role=person.role) if person else None
            ),
            commission_default=commission_default,
            currency=currency,
            budget=self.budget_check(company_id, client.id, client.name, currency, amount),
        )

    # -- admin: writes ---------------------------------------------------------------------

    def _commission_for(
        self,
        company_id: UUID,
        person: PersonRow,
        service_id: UUID,
        requested: Decimal | None,
    ) -> tuple[Decimal | None, Decimal | None]:
        """(default, final) commission for an assignee. Employees are salaried: none."""
        if person.role == "EMPLOYEE":
            if requested is not None:
                raise AuthenticationError(
                    422,
                    "COMMISSION_NOT_ALLOWED",
                    "Employees are paid a monthly salary, so tasks assigned to them have no commission.",
                )
            return None, None
        default = self.repository.current_rate(company_id, "MANAGER", person.id, service_id)
        final = requested if requested is not None else default
        if final is None:
            raise AuthenticationError(
                422,
                "COMMISSION_REQUIRED",
                f"No commission rate is set for {person.name} on this service. "
                "Enter the commission for this task.",
            )
        return default, money(final)

    def create_task(self, context: AuthContext, request: TaskCreateRequest) -> TaskWriteResponse:
        company_id = self._admin(context, "CREATE")
        client = self.repository.get_client(company_id, request.client_id)
        if client is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        if client.status != "ACTIVE":
            raise AuthenticationError(
                409, "CLIENT_INACTIVE", "Tasks cannot be created for an inactive client."
            )
        service = self.repository.get_service(company_id, request.service_id)
        if service is None:
            raise AuthenticationError(404, "SERVICE_NOT_FOUND", "Service was not found.")
        if service.status != "ACTIVE":
            raise AuthenticationError(
                409, "SERVICE_INACTIVE", "Tasks cannot use an inactive service."
            )

        default_price = self.repository.current_rate(company_id, "CLIENT", client.id, service.id)
        final_price = request.client_price if request.client_price is not None else default_price
        if final_price is None:
            raise AuthenticationError(
                422,
                "CLIENT_PRICE_REQUIRED",
                f"No rate is set for {client.name} on {service.name}. Enter the price for this task.",
            )
        final_price = money(final_price)
        price_changes: list[tuple[str, Decimal | None, Decimal | None, str]] = []
        if default_price is None or money(default_price) != final_price:
            price_changes.append(
                ("CLIENT_PRICE", default_price, final_price, request.client_price_reason)
            )

        person = None
        commission_default = commission_final = None
        if request.assignee_user_id is not None:
            person = self._require_person(
                company_id, request.assignee_user_id, "ASSIGNEE_NOT_FOUND", "Assignee"
            )
            commission_default, commission_final = self._commission_for(
                company_id, person, service.id, request.commission
            )
            if commission_final is not None and (
                commission_default is None or money(commission_default) != commission_final
            ):
                price_changes.append(
                    ("COMMISSION", commission_default, commission_final, request.commission_reason)
                )
        elif request.commission is not None:
            raise AuthenticationError(
                422, "ASSIGNEE_REQUIRED", "Choose a manager before entering a commission."
            )
        if request.monitor_user_id is not None:
            self._require_monitor(company_id, request.monitor_user_id, request.assignee_user_id)

        status = "ASSIGNED" if person else "PENDING"
        task_id = self.repository.create_task(
            company_id,
            context.user_id,
            {
                "client_id": client.id,
                "service_id": service.id,
                "title": request.title,
                "description": request.description,
                "priority": request.priority,
                "status": status,
                "assignee_user_id": person.id if person else None,
                "assignee_type": person.role if person else None,
                "monitor_user_id": request.monitor_user_id,
                "due_date": request.due_date,
                "client_pricing_model": service.client_pricing_model,
                "client_price_default": default_price,
                "client_price_final": final_price,
                "client_price_reason": request.client_price_reason,
                "commission_default": commission_default,
                "commission_final": commission_final,
                "commission_reason": request.commission_reason if person else "",
                "assigned_at": datetime.now(timezone.utc) if person else None,
            },
            price_changes,
        )
        self.events.assigned(company_id, task_id, context.user_id, None, None)
        return self._write_response(company_id, task_id)

    def update_task(
        self, context: AuthContext, task_id: UUID, request: TaskUpdateRequest
    ) -> AdminTaskDetailResponse:
        company_id = self._admin(context, "EDIT")
        updates = request.model_dump(include=request.model_fields_set)

        def plan(_: TaskRow) -> TaskMutation:
            return TaskMutation(updates=updates)

        self._mutate(company_id, task_id, context.user_id, plan)
        return self._admin_detail(company_id, task_id)

    def assign_task(
        self, context: AuthContext, task_id: UUID, request: TaskAssignRequest
    ) -> TaskWriteResponse:
        company_id = self._admin(context, "ASSIGN")
        person = self._require_person(
            company_id, request.assignee_user_id, "ASSIGNEE_NOT_FOUND", "Assignee"
        )
        if request.monitor_user_id is not None:
            self._require_monitor(company_id, request.monitor_user_id, person.id)
        current = self._load(company_id, task_id)
        commission_default, commission_final = self._commission_for(
            company_id, person, current.service_id, request.commission
        )

        def plan(row: TaskRow) -> TaskMutation:
            if row.status in CLOSED_STATUSES:
                raise AuthenticationError(
                    409,
                    "TASK_CLOSED",
                    "Approved, completed or cancelled tasks cannot be reassigned.",
                )
            mutation = TaskMutation(
                updates={
                    "assignee_user_id": person.id,
                    "assignee_type": person.role,
                    "monitor_user_id": request.monitor_user_id,
                    "commission_default": commission_default,
                    "commission_final": commission_final,
                    "commission_reason": (
                        request.commission_reason if commission_final is not None else ""
                    ),
                }
            )
            now = datetime.now(timezone.utc)
            if row.status == "PENDING":
                mutation.updates["status"] = "ASSIGNED"
                mutation.updates.update(
                    status_timestamp_updates(
                        "ASSIGNED",
                        now,
                        assigned_at=row.assigned_at,
                        started_at=row.started_at,
                        approved_at=row.approved_at,
                    )
                )
                mutation.status_change = ("PENDING", "ASSIGNED", f"Assigned to {person.name}")
            elif row.assignee_user_id != person.id:
                mutation.status_change = (
                    row.status,
                    row.status,
                    f"Reassigned from {row.assignee_name or 'nobody'} to {person.name}",
                )
            old = row.commission_final
            changed = (old is None) != (commission_final is None) or (
                old is not None and commission_final is not None and money(old) != commission_final
            )
            first_assignment = row.assignee_user_id is None
            if first_assignment and commission_final is not None:
                if commission_default is None or money(commission_default) != commission_final:
                    mutation.price_changes.append(
                        (
                            "COMMISSION",
                            commission_default,
                            commission_final,
                            request.commission_reason,
                        )
                    )
            elif not first_assignment and changed:
                reason = request.commission_reason or f"Reassigned to {person.name}"
                mutation.price_changes.append(("COMMISSION", old, commission_final, reason))
            return mutation

        self._mutate(company_id, task_id, context.user_id, plan)
        self.events.assigned(
            company_id, task_id, context.user_id, current.assignee_user_id, current.monitor_user_id
        )
        return self._write_response(company_id, task_id)

    def set_monitor(
        self, context: AuthContext, task_id: UUID, request: TaskMonitorRequest
    ) -> AdminTaskDetailResponse:
        company_id = self._admin(context, "ASSIGN")
        current = self._load(company_id, task_id)
        if request.monitor_user_id is not None:
            self._require_monitor(company_id, request.monitor_user_id, current.assignee_user_id)

        def plan(row: TaskRow) -> TaskMutation:
            if (
                request.monitor_user_id is not None
                and request.monitor_user_id == row.assignee_user_id
            ):
                raise AuthenticationError(
                    422,
                    "MONITOR_IS_ASSIGNEE",
                    "The monitor must be a different person from the assignee.",
                )
            return TaskMutation(updates={"monitor_user_id": request.monitor_user_id})

        self._mutate(company_id, task_id, context.user_id, plan)
        self.events.assigned(
            company_id, task_id, context.user_id, current.assignee_user_id, current.monitor_user_id
        )
        return self._admin_detail(company_id, task_id)

    def change_prices(
        self, context: AuthContext, task_id: UUID, request: TaskPriceChangeRequest
    ) -> TaskWriteResponse:
        company_id = self._admin(context, "EDIT")

        def plan(row: TaskRow) -> TaskMutation:
            mutation = TaskMutation()
            if request.client_price is not None:
                new_price = money(request.client_price)
                if new_price != money(row.client_price_final):
                    mutation.updates["client_price_final"] = new_price
                    mutation.updates["client_price_reason"] = request.client_price_reason
                    mutation.price_changes.append(
                        (
                            "CLIENT_PRICE",
                            row.client_price_final,
                            new_price,
                            request.client_price_reason,
                        )
                    )
            if request.commission is not None:
                if row.assignee_type != "MANAGER":
                    raise AuthenticationError(
                        422,
                        "COMMISSION_NOT_ALLOWED",
                        "Only tasks assigned to a manager have a commission.",
                    )
                new_commission = money(request.commission)
                if row.commission_final is None or new_commission != money(row.commission_final):
                    mutation.updates["commission_final"] = new_commission
                    mutation.updates["commission_reason"] = request.commission_reason
                    mutation.price_changes.append(
                        (
                            "COMMISSION",
                            row.commission_final,
                            new_commission,
                            request.commission_reason,
                        )
                    )
            return mutation

        self._mutate(company_id, task_id, context.user_id, plan)
        return self._write_response(company_id, task_id)

    def change_status_admin(
        self, context: AuthContext, task_id: UUID, request: TaskStatusChangeRequest
    ) -> TaskWriteResponse:
        action = "APPROVE" if request.status in BILLABLE_STATUSES else "EDIT"
        company_id = self._admin(context, action)
        previous: dict[str, str] = {}

        def plan(row: TaskRow) -> TaskMutation:
            previous["status"] = row.status
            return self._status_plan(row, "ADMIN", request)

        self._mutate(company_id, task_id, context.user_id, plan)
        self.events.status_changed(
            company_id, task_id, context.user_id, previous.get("status"), by_admin=True
        )
        return self._write_response(company_id, task_id)

    def _status_plan(
        self, row: TaskRow, role: TaskActorRole, request: TaskStatusChangeRequest
    ) -> TaskMutation:
        target = request.status
        if target == row.status:
            raise AuthenticationError(409, "STATUS_UNCHANGED", "The task already has this status.")
        has_assignee = row.assignee_user_id is not None
        if not can_transition(role, row.status, target, has_assignee):
            if role == "ADMIN" and not has_assignee:
                detail = "Assign someone to this task before moving it forward."
            elif role == "ADMIN":
                detail = "A task with an assignee cannot go back to Pending."
            elif target in BILLABLE_STATUSES or target == "CANCELLED":
                detail = "Only the Admin can approve, complete or cancel tasks."
            else:
                detail = (
                    f"You cannot move this task from {STATUS_LABELS[row.status]} "
                    f"to {STATUS_LABELS[target]}."
                )
            raise AuthenticationError(409, "INVALID_STATUS_CHANGE", detail)
        updates: dict[str, object] = {"status": target}
        updates.update(
            status_timestamp_updates(
                target,
                datetime.now(timezone.utc),
                assigned_at=row.assigned_at,
                started_at=row.started_at,
                approved_at=row.approved_at,
            )
        )
        return TaskMutation(updates=updates, status_change=(row.status, target, request.note))

    def _mutate(self, company_id: UUID, task_id: UUID, actor_id: UUID, plan: object) -> None:
        try:
            self.repository.mutate_task(company_id, task_id, actor_id, plan)  # type: ignore[arg-type]
        except TaskNotFound as error:
            raise _not_found() from error

    # -- content calendar tickets (Phase 13, owner request 2026-11-14) ----------------------

    def create_calendar_ticket(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        title: str,
        description: str,
        due_date: date,
    ) -> UUID | None:
        """Turn a calendar entry into a Pending, unassigned task. The service is the one the
        client uses most that has a client rate; priority comes from how soon the date is.
        Returns None when no service has a rate for this client (the admin creates it by hand)."""
        client = self.repository.get_client(company_id, client_id)
        if client is None or client.status != "ACTIVE":
            return None
        for service_id in self.repository.calendar_service_choices(company_id, client_id):
            service = self.repository.get_service(company_id, service_id)
            rate = self.repository.current_rate(company_id, "CLIENT", client_id, service_id)
            if service is None or rate is None:
                continue
            task_id = self.repository.create_task(
                company_id,
                actor_id,
                {
                    "client_id": client_id,
                    "service_id": service_id,
                    "title": title[:200],
                    "description": description[:5000],
                    "priority": calendar_priority(due_date, self._today(company_id)),
                    "status": "PENDING",
                    "assignee_user_id": None,
                    "assignee_type": None,
                    "monitor_user_id": None,
                    "due_date": due_date,
                    "client_pricing_model": service.client_pricing_model,
                    "client_price_default": rate,
                    "client_price_final": money(rate),
                    "client_price_reason": "",
                    "commission_default": None,
                    "commission_final": None,
                    "commission_reason": "",
                    "assigned_at": None,
                },
                [],
            )
            return task_id
        return None

    def sync_calendar_ticket(
        self, company_id: UUID, task_id: UUID, actor_id: UUID, title: str, due_date: date
    ) -> None:
        """Keep the ticket's title, date and priority in step with the entry until work starts."""
        today = self._today(company_id)

        def plan(row: TaskRow) -> TaskMutation:
            if row.status not in ("PENDING", "ASSIGNED"):
                return TaskMutation()
            return TaskMutation(
                updates={
                    "title": title[:200],
                    "due_date": due_date,
                    "priority": calendar_priority(due_date, today),
                }
            )

        self._mutate(company_id, task_id, actor_id, plan)

    def cancel_calendar_ticket(self, company_id: UUID, task_id: UUID, actor_id: UUID) -> None:
        """Cancel the ticket of a removed entry. Only while nobody has it yet."""

        def plan(row: TaskRow) -> TaskMutation:
            if row.status == "CANCELLED":
                return TaskMutation()
            if row.status != "PENDING":
                raise AuthenticationError(
                    409,
                    "ENTRY_IN_PRODUCTION",
                    "Your agency has started this video, so it cannot be removed.",
                )
            updates: dict[str, object] = {"status": "CANCELLED"}
            updates.update(
                status_timestamp_updates(
                    "CANCELLED",
                    datetime.now(timezone.utc),
                    assigned_at=row.assigned_at,
                    started_at=row.started_at,
                    approved_at=row.approved_at,
                )
            )
            return TaskMutation(
                updates=updates,
                status_change=(row.status, "CANCELLED", "Removed from the client's calendar."),
            )

        self._mutate(company_id, task_id, actor_id, plan)

    # -- worker workspace ------------------------------------------------------------------

    def list_worker_tasks(
        self, context: AuthContext, filters: WorkerTaskFilters
    ) -> WorkerTaskListResponse:
        company_id, _ = self._worker(context)
        today = self._today(company_id)
        rows, total = self.repository.list_worker_tasks(company_id, context.user_id, filters)
        return WorkerTaskListResponse(
            items=[self._worker_task(row, context.user_id, today) for row in rows],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=max(1, (total + filters.page_size - 1) // filters.page_size),
        )

    def get_worker_task(self, context: AuthContext, task_id: UUID) -> WorkerTaskDetailResponse:
        company_id, _ = self._worker(context)
        return self._worker_detail(company_id, context.user_id, task_id)

    def change_status_worker(
        self, context: AuthContext, task_id: UUID, request: TaskStatusChangeRequest
    ) -> WorkerTaskDetailResponse:
        company_id, _ = self._worker(context)
        if not validate_user_action_access(str(context.user_id), context.role, "TASKS", "EDIT"):
            raise AuthenticationError(
                403, "TASKS_EDIT_REQUIRED", "Tasks edit permission is required."
            )

        previous: dict[str, str] = {}

        def plan(row: TaskRow) -> TaskMutation:
            role = self._worker_role(row, context.user_id)
            if role is None:
                raise _not_found()
            previous["status"] = row.status
            return self._status_plan(row, role, request)

        self._mutate(company_id, task_id, context.user_id, plan)
        self.events.status_changed(
            company_id, task_id, context.user_id, previous.get("status"), by_admin=False
        )
        return self._worker_detail(company_id, context.user_id, task_id)

    # -- comments and files (admin and workers) ----------------------------------------------

    def add_comment(
        self, context: AuthContext, task_id: UUID, request: TaskCommentRequest
    ) -> list[TaskCommentResponse]:
        company_id = self._comment_access(context, task_id)
        self.repository.add_comment(company_id, task_id, context.user_id, request.content)
        self.events.commented(company_id, task_id, context.user_id, request.content)
        return [
            TaskCommentResponse(**item.__dict__) for item in self.repository.list_comments(task_id)
        ]

    def _comment_access(self, context: AuthContext, task_id: UUID) -> UUID:
        if context.role == "COMPANY_ADMIN":
            company_id = self._admin(context, "VIEW")
            self._load(company_id, task_id)
            return company_id
        company_id, _ = self._worker(context)
        self._load_for_worker(company_id, context.user_id, task_id)
        return company_id

    def upload_file(
        self, context: AuthContext, task_id: UUID, kind: TaskFileKind, upload: UploadFile
    ) -> list[TaskFileResponse]:
        if context.role == "COMPANY_ADMIN":
            company_id = self._admin(context, "EDIT")
            self._load(company_id, task_id)
        else:
            company_id, _ = self._worker(context)
            row, role = self._load_for_worker(company_id, context.user_id, task_id)
            if role != "ASSIGNEE" or kind != "DELIVERABLE":
                raise AuthenticationError(
                    403,
                    "UPLOAD_NOT_ALLOWED",
                    "Only the assigned person can upload, and only finished work (deliverables).",
                )
            if row.status not in _WORKING_STATUSES:
                raise AuthenticationError(
                    409, "TASK_CLOSED", "Files cannot be added after a task is approved or closed."
                )
        stored = self.storage.save(company_id, task_id, upload)
        try:
            self.repository.add_file(
                company_id,
                task_id,
                context.user_id,
                kind,
                stored.file_name,
                stored.storage_path,
                stored.mime_type,
                stored.size_bytes,
            )
        except Exception:
            self.storage.delete(stored.storage_path)
            raise
        self.events.file_added(company_id, task_id, context.user_id, stored.file_name, kind)
        _, _, files = self._shared_detail(task_id)
        return files

    def file_for_download(
        self, context: AuthContext, task_id: UUID, file_id: UUID
    ) -> tuple[Path, str, str]:
        if context.role == "COMPANY_ADMIN":
            company_id = self._admin(context, "VIEW")
        else:
            company_id, _ = self._worker(context)
            self._load_for_worker(company_id, context.user_id, task_id)
        record = self.repository.get_file(company_id, task_id, file_id)
        if record is None:
            raise AuthenticationError(404, "FILE_NOT_FOUND", "File was not found.")
        return self.storage.path_for(record.storage_path), record.file_name, record.mime_type

    def delete_file(
        self, context: AuthContext, task_id: UUID, file_id: UUID
    ) -> list[TaskFileResponse]:
        if context.role == "COMPANY_ADMIN":
            company_id = self._admin(context, "EDIT")
            record = self.repository.get_file(company_id, task_id, file_id)
        else:
            company_id, _ = self._worker(context)
            row, role = self._load_for_worker(company_id, context.user_id, task_id)
            record = self.repository.get_file(company_id, task_id, file_id)
            if record is not None and (
                role != "ASSIGNEE"
                or record.uploaded_by_id != context.user_id
                or row.status not in _WORKING_STATUSES
            ):
                raise AuthenticationError(
                    403,
                    "DELETE_NOT_ALLOWED",
                    "You can only remove your own uploads while the task is still in progress.",
                )
        if record is None:
            raise AuthenticationError(404, "FILE_NOT_FOUND", "File was not found.")
        self.repository.delete_file(company_id, file_id)
        self.storage.delete(record.storage_path)
        _, _, files = self._shared_detail(task_id)
        return files

    def is_ready(self) -> bool:
        return self.repository.is_ready()


task_service = TaskService(events=TaskEvents())
