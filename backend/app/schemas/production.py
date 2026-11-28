"""Schemas for tasks, budgets, payments, salaries, payouts and reports.

Privacy is part of the shape: worker and client responses have no fields for client prices,
margin, revenue or other people's pay, so those values cannot leak to those roles.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.service_pricing import PricingModel
from app.services.production_rules import ReportPeriod, TaskStatus

TaskPriority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
# ADMIN: the Admin can take a task too (owner request 2026-11-28); no commission or salary.
AssigneeType = Literal["MANAGER", "EMPLOYEE", "ADMIN"]
TaskFileKind = Literal["REFERENCE", "DELIVERABLE"]
BudgetEntryType = Literal["INITIAL", "TOP_UP", "ADJUSTMENT"]
PaymentMethod = Literal["CASH", "BANK_TRANSFER", "UPI", "CHEQUE", "CARD", "OTHER"]
WorkerTaskRole = Literal["ASSIGNEE", "MONITOR", "CLIENT_WRITE", "CLIENT_READ"]
# Which tasks a worker lists: their own, the ones they monitor, or those of clients they have
# access to (owner request 2026-11-26).
WorkerTaskScope = Literal["ASSIGNEE", "MONITOR", "CLIENT"]
ClientAccessLevel = Literal["READ", "WRITE", "CREATE"]

Money = Decimal


def _optional_money() -> Decimal | None:
    return Field(default=None, ge=0, max_digits=12, decimal_places=2)


def _strip(value: str | None) -> str | None:
    return value.strip() if value is not None else None


def _strip_required(value: str) -> str:
    return value.strip()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Shared summaries
# ---------------------------------------------------------------------------


class NamedRef(BaseModel):
    id: UUID
    name: str
    code: str = ""


class PersonRef(BaseModel):
    id: UUID
    name: str
    role: AssigneeType


class StatusHistoryResponse(BaseModel):
    id: UUID
    from_status: TaskStatus | None
    to_status: TaskStatus
    note: str
    actor_name: str
    created_at: datetime


class TaskCommentResponse(BaseModel):
    id: UUID
    author_id: UUID
    author_name: str
    content: str
    created_at: datetime


class TaskFileResponse(BaseModel):
    id: UUID
    kind: TaskFileKind
    file_name: str
    mime_type: str
    size_bytes: int
    uploaded_by_name: str
    created_at: datetime


class BudgetCheckResponse(BaseModel):
    """Admin-only budget position for one client, optionally including a task being priced."""

    has_budget: bool
    currency: str
    total: Money
    used: Money
    committed: Money
    remaining: Money
    overage: Money
    projected_used: Money
    projected_overage: Money
    exceeds_with_new_task: bool
    message: str


# ---------------------------------------------------------------------------
# Admin task management
# ---------------------------------------------------------------------------


class TaskCreateRequest(_Strict):
    client_id: UUID
    service_id: UUID
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: TaskPriority = "MEDIUM"
    due_date: date | None = None
    client_price: Decimal | None = _optional_money()
    client_price_reason: str = Field(default="", max_length=500)
    assignee_user_id: UUID | None = None
    monitor_user_id: UUID | None = None
    commission: Decimal | None = _optional_money()
    commission_reason: str = Field(default="", max_length=500)

    _strip_text = field_validator(
        "title", "description", "client_price_reason", "commission_reason"
    )(_strip_required)

    @model_validator(mode="after")
    def check_people(self) -> Self:
        if len(self.title) < 2:
            raise ValueError("Task title cannot be blank.")
        if self.monitor_user_id is not None and self.monitor_user_id == self.assignee_user_id:
            raise ValueError("The monitor must be a different person from the assignee.")
        return self


class TaskUpdateRequest(_Strict):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: TaskPriority | None = None
    due_date: date | None = None

    _strip_text = field_validator("title", "description")(_strip)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one task field is required.")
        if self.title is not None and len(self.title) < 2:
            raise ValueError("Task title cannot be blank.")
        return self


class TaskAssignRequest(_Strict):
    assignee_user_id: UUID
    monitor_user_id: UUID | None = None
    commission: Decimal | None = _optional_money()
    commission_reason: str = Field(default="", max_length=500)

    _strip_text = field_validator("commission_reason")(_strip_required)

    @model_validator(mode="after")
    def check_people(self) -> Self:
        if self.monitor_user_id is not None and self.monitor_user_id == self.assignee_user_id:
            raise ValueError("The monitor must be a different person from the assignee.")
        return self


class TaskMonitorRequest(_Strict):
    monitor_user_id: UUID | None = None


class TaskPriceChangeRequest(_Strict):
    client_price: Decimal | None = _optional_money()
    client_price_reason: str = Field(default="", max_length=500)
    commission: Decimal | None = _optional_money()
    commission_reason: str = Field(default="", max_length=500)

    _strip_text = field_validator("client_price_reason", "commission_reason")(_strip_required)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.client_price is None and self.commission is None:
            raise ValueError("Provide a new client price, a new commission, or both.")
        return self


class TaskStatusChangeRequest(_Strict):
    status: TaskStatus
    note: str = Field(default="", max_length=1000)

    _strip_text = field_validator("note")(_strip_required)


class TaskCommentRequest(_Strict):
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank.")
        return value


class TaskListFilters(BaseModel):
    search: str = Field(default="", max_length=100)
    status: TaskStatus | None = None
    client_id: UUID | None = None
    service_id: UUID | None = None
    assignee_user_id: UUID | None = None
    overdue_only: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)


class PriceChangeResponse(BaseModel):
    id: UUID
    field: Literal["CLIENT_PRICE", "COMMISSION"]
    old_amount: Money | None
    new_amount: Money | None
    reason: str
    actor_name: str
    created_at: datetime


class AdminTaskResponse(BaseModel):
    id: UUID
    code: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    client: NamedRef
    service: NamedRef
    assignee: PersonRef | None
    monitor: NamedRef | None
    due_date: date | None
    is_overdue: bool
    billable: bool
    currency: str
    client_pricing_model: PricingModel
    client_price_default: Money | None
    client_price: Money
    client_price_reason: str
    commission_default: Money | None
    commission: Money | None
    commission_reason: str
    margin: Money
    allowed_statuses: list[TaskStatus]
    files_count: int = 0
    comments_count: int = 0
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    assigned_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    approved_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


class AdminTaskDetailResponse(AdminTaskResponse):
    status_history: list[StatusHistoryResponse]
    price_changes: list[PriceChangeResponse]
    comments: list[TaskCommentResponse]
    files: list[TaskFileResponse]


class AdminTaskListResponse(BaseModel):
    items: list[AdminTaskResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class TaskWriteResponse(BaseModel):
    """Result of a write that can affect the client's budget."""

    task: AdminTaskDetailResponse
    budget: BudgetCheckResponse


class PricingPreviewResponse(BaseModel):
    client: NamedRef
    service: NamedRef
    client_pricing_model: PricingModel
    client_price_default: Money | None
    assignee: PersonRef | None
    commission_default: Money | None
    currency: str
    budget: BudgetCheckResponse


class AssigneeOptionResponse(BaseModel):
    id: UUID
    name: str
    role: AssigneeType
    code: str
    email: str


# ---------------------------------------------------------------------------
# Manager / Employee workspace (no client prices, no margin, no other people's pay)
# ---------------------------------------------------------------------------


class WorkerTaskResponse(BaseModel):
    id: UUID
    code: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    client_name: str
    service_name: str
    my_role: WorkerTaskRole
    assignee_name: str | None
    due_date: date | None
    is_overdue: bool
    # Only present for a manager viewing a task assigned to them.
    my_commission: Money | None
    currency: str
    allowed_statuses: list[TaskStatus]
    can_upload_deliverables: bool
    can_comment: bool = True
    files_count: int = 0
    comments_count: int = 0
    created_at: datetime
    assigned_at: datetime | None
    submitted_at: datetime | None
    approved_at: datetime | None
    completed_at: datetime | None


class ClientAccessPerson(BaseModel):
    id: UUID
    name: str
    role: Literal["MANAGER", "EMPLOYEE"]
    code: str = ""


class ClientAccessGrant(BaseModel):
    user_id: UUID
    client_id: UUID
    level: ClientAccessLevel


class ClientAccessOverview(BaseModel):
    """Admin: every manager/employee, every active client, and who has which access."""

    people: list[ClientAccessPerson]
    clients: list[NamedRef]
    grants: list[ClientAccessGrant]


class ClientAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    client_id: UUID
    level: ClientAccessLevel | None = None  # None removes the access


class MyClientAccess(BaseModel):
    client: NamedRef
    level: ClientAccessLevel


class MyClientAccessResponse(BaseModel):
    items: list[MyClientAccess]


class WorkerTaskDetailResponse(WorkerTaskResponse):
    status_history: list[StatusHistoryResponse]
    comments: list[TaskCommentResponse]
    files: list[TaskFileResponse]


class WorkerTaskListResponse(BaseModel):
    items: list[WorkerTaskResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class WorkerTaskFilters(BaseModel):
    role: WorkerTaskScope | None = None
    client_id: UUID | None = None
    status: TaskStatus | None = None
    search: str = Field(default="", max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)


class TaskCounts(BaseModel):
    assigned: int
    in_progress: int
    submitted: int
    in_review: int
    approved: int
    completed: int
    overdue: int
    monitoring: int


class CommissionTaskLine(BaseModel):
    task_id: UUID
    code: str
    title: str
    service_name: str
    status: TaskStatus
    commission: Money
    approved_at: datetime | None


class SheetLine(BaseModel):
    """One row of a payment sheet; `amount` is signed (money in +, work -)."""

    day: date
    kind: Literal["CARRIED", "PAYMENT", "ADJUSTMENT", "WORK"]
    label: str
    amount: Money
    balance: Money


class WalletPeriod(BaseModel):
    """A manager payment sheet: one top-up, with the previous sheet's balance carried in."""

    index: int
    start: date
    end: date | None
    topped_up: Money
    earned: Money
    balance: Money
    items: int
    carried_in: Money = Decimal("0.00")
    ran_out_on: date | None = None
    lines: list[SheetLine] = []


class WalletLine(BaseModel):
    day: date
    kind: Literal["TOP_UP", "COMMISSION"]
    title: str
    amount: Money
    balance: Money


class ManagerWallet(BaseModel):
    """Advance model (owner decision 2026-11-14): top-ups minus commission earned."""

    topped_up: Money
    earned: Money
    balance: Money
    periods: list[WalletPeriod]
    lines: list[WalletLine]


class ManagerEarningsResponse(BaseModel):
    currency: str
    earned: Money
    upcoming: Money
    paid: Money
    pending: Money
    current_month_earned: Money
    tasks: list[CommissionTaskLine]
    payouts: list["ManagerPayoutResponse"]
    wallet: ManagerWallet | None = None


class SalaryMonthLine(BaseModel):
    month: date
    due: Money
    paid: Money
    pending: Money


class EmployeeSalaryResponse(BaseModel):
    currency: str
    current_monthly_salary: Money | None
    total_due: Money
    total_paid: Money
    pending: Money
    months: list[SalaryMonthLine]
    payments: list["SalaryPaymentResponse"]


class WorkspaceDashboardResponse(BaseModel):
    role: AssigneeType
    counts: TaskCounts
    currency: str
    # Manager: commission figures. Employee: salary figures. Never anyone else's.
    current_month_earnings: Money
    pending_payment: Money
    upcoming_tasks: list[WorkerTaskResponse]


# ---------------------------------------------------------------------------
# Client portal (counts and own money only, never a task list)
# ---------------------------------------------------------------------------


class ClientServiceCount(BaseModel):
    service_id: UUID
    service_name: str
    completed: int
    in_progress: int
    charged: Money


class ClientBudgetSummary(BaseModel):
    has_budget: bool
    total: Money
    used: Money
    remaining: Money
    overage: Money


class ClientPaymentLine(BaseModel):
    amount: Money
    received_on: date
    method: PaymentMethod
    reference: str


class ClientDeliveryLine(BaseModel):
    title: str
    service_name: str
    delivered_on: date
    amount: Money


class ClientMonthPoint(BaseModel):
    month: date
    items: int
    amount: Money


class ClientWorkspaceSummaryResponse(BaseModel):
    client_name: str
    currency: str
    completed_items: int
    in_progress_items: int
    services: list[ClientServiceCount]
    budget: ClientBudgetSummary
    total_charged: Money
    total_paid: Money
    pending_amount: Money
    current_month_charged: Money
    payments: list[ClientPaymentLine]
    recent_deliveries: list[ClientDeliveryLine] = []
    monthly: list[ClientMonthPoint] = []


# ---------------------------------------------------------------------------
# Admin finance: budgets, payments, salaries, payouts
# ---------------------------------------------------------------------------


class BudgetEntryRequest(_Strict):
    type: BudgetEntryType
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    note: str = Field(default="", max_length=500)

    _strip_text = field_validator("note")(_strip_required)

    @model_validator(mode="after")
    def check_amount(self) -> Self:
        if self.type != "ADJUSTMENT" and self.amount <= 0:
            raise ValueError("Initial budgets and top-ups must be greater than zero.")
        if self.amount == 0:
            raise ValueError("Amount cannot be zero.")
        return self


class BudgetEntryResponse(BaseModel):
    id: UUID
    type: BudgetEntryType
    amount: Money
    currency: str
    note: str
    created_by_name: str
    created_at: datetime


class ClientBudgetResponse(BaseModel):
    client: NamedRef
    budget: BudgetCheckResponse
    entries: list[BudgetEntryResponse]


class PaymentRequestBase(_Strict):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: PaymentMethod = "BANK_TRANSFER"
    reference: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=500)

    _strip_text = field_validator("reference", "note")(_strip_required)


class PaymentUpdateBase(_Strict):
    """Edit a recorded payment: send only the fields that change."""

    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    method: PaymentMethod | None = None
    reference: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)

    _strip_text = field_validator("reference", "note")(_strip)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to change.")
        for name in self.model_fields_set:
            if name not in {"reference", "note"} and getattr(self, name) is None:
                raise ValueError(f"{name.replace('_', ' ').capitalize()} cannot be empty.")
        return self


class ClientPaymentUpdate(PaymentUpdateBase):
    client_id: UUID | None = None
    received_on: date | None = None


class SalaryPaymentUpdate(PaymentUpdateBase):
    period_month: date | None = None
    paid_on: date | None = None

    @field_validator("period_month")
    @classmethod
    def first_of_month(cls, value: date | None) -> date | None:
        return value.replace(day=1) if value else None


class ManagerPayoutUpdate(PaymentUpdateBase):
    paid_on: date | None = None


class SalaryRecordUpdate(_Strict):
    monthly_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=500)

    _strip_text = field_validator("note")(_strip)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.monthly_amount is None and self.note is None:
            raise ValueError("Provide a new amount or note.")
        return self


class ClientPaymentRequest(PaymentRequestBase):
    client_id: UUID
    received_on: date


class ClientPaymentResponse(BaseModel):
    id: UUID
    client: NamedRef
    amount: Money
    currency: str
    received_on: date
    method: PaymentMethod
    reference: str
    note: str
    created_by_name: str
    created_at: datetime


class SalaryRequest(_Strict):
    monthly_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    effective_from: date
    note: str = Field(default="", max_length=500)

    _strip_text = field_validator("note")(_strip_required)


class SalaryRecordResponse(BaseModel):
    id: UUID
    monthly_amount: Money
    currency: str
    effective_from: date
    effective_to: date | None
    note: str
    created_by_name: str
    created_at: datetime


class SalaryPaymentRequest(PaymentRequestBase):
    user_id: UUID
    period_month: date
    paid_on: date

    @field_validator("period_month")
    @classmethod
    def first_of_month(cls, value: date) -> date:
        return value.replace(day=1)


class SalaryPaymentResponse(BaseModel):
    id: UUID
    user_id: UUID
    employee_name: str
    period_month: date
    amount: Money
    currency: str
    paid_on: date
    method: PaymentMethod
    reference: str
    note: str
    created_by_name: str
    created_at: datetime


class ManagerPayoutRequest(PaymentRequestBase):
    manager_user_id: UUID
    paid_on: date


class ManagerPayoutResponse(BaseModel):
    id: UUID
    manager_user_id: UUID
    manager_name: str
    amount: Money
    currency: str
    paid_on: date
    method: PaymentMethod
    reference: str
    note: str
    created_by_name: str
    created_at: datetime


class PaymentListFilters(BaseModel):
    subject_id: UUID | None = None
    start: date | None = None
    end: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ClientPaymentListResponse(BaseModel):
    items: list[ClientPaymentResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    total_amount: Money


class SalaryPaymentListResponse(BaseModel):
    items: list[SalaryPaymentResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    total_amount: Money


class ManagerPayoutListResponse(BaseModel):
    items: list[ManagerPayoutResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    total_amount: Money


class PersonFinanceResponse(BaseModel):
    """Admin view of one manager's commission or one employee's salary."""

    person: PersonRef
    manager: ManagerEarningsResponse | None
    employee: EmployeeSalaryResponse | None
    salary_history: list[SalaryRecordResponse]


# ---------------------------------------------------------------------------
# Admin dashboard and reports
# ---------------------------------------------------------------------------


class PeriodQuery(BaseModel):
    period: ReportPeriod = "this_month"
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def check_custom(self) -> Self:
        if self.period == "custom" and (self.start is None or self.end is None):
            raise ValueError("A custom period needs both a start and an end date.")
        if self.start and self.end and self.end < self.start:
            raise ValueError("The end date must be on or after the start date.")
        return self


class PeriodResponse(BaseModel):
    period: ReportPeriod
    start: date | None
    end: date | None


class EarningLine(BaseModel):
    """One delivery on the Admin's Earnings section (owner request 2026-11-28)."""

    key: str
    day: date
    title: str
    client_name: str
    service_name: str
    amount: Money
    commission: Money


class EarningsResponse(BaseModel):
    currency: str
    lines: list[EarningLine]


class FinanceSummaryResponse(BaseModel):
    period: PeriodResponse
    currency: str
    revenue: Money
    commission_cost: Money
    salary_cost: Money
    team_cost: Money
    gross_margin: Money
    approved_items: int
    pending_client_payments: Money
    pending_manager_payments: Money
    pending_salary_payments: Money
    pending_team_payments: Money
    open_tasks: int
    unassigned_tasks: int
    in_review_tasks: int
    overdue_tasks: int
    top_client: NamedRef | None
    top_client_open_tasks: int


class ClientReportRow(BaseModel):
    client: NamedRef
    total_tasks: int
    completed_tasks: int
    open_tasks: int
    billed: Money
    received: Money
    pending: Money
    budget_total: Money
    budget_remaining: Money
    services: list[ClientServiceCount]


class TeamReportRow(BaseModel):
    person: PersonRef
    total_tasks: int
    completed_tasks: int
    open_tasks: int
    earnings: Money
    paid: Money
    pending: Money
    # Employees: the monthly salary in effect today, else the next one set (2026-11-28).
    monthly_salary: Money | None = None
    salary_from: date | None = None


class ServiceReportRow(BaseModel):
    service: NamedRef
    items: int
    revenue: Money
    commission_cost: Money
    margin: Money


class ClientReportResponse(BaseModel):
    period: PeriodResponse
    currency: str
    rows: list[ClientReportRow]


class TeamReportResponse(BaseModel):
    period: PeriodResponse
    currency: str
    rows: list[TeamReportRow]


class ServiceReportResponse(BaseModel):
    period: PeriodResponse
    currency: str
    rows: list[ServiceReportRow]
    totals: ServiceReportRow | None


class DashboardMoney(BaseModel):
    revenue: Money
    previous_revenue: Money | None
    revenue_change_pct: float | None
    team_cost: Money
    commission_cost: Money
    salary_cost: Money
    gross_margin: Money
    margin_pct: float | None
    pending_client_payments: Money
    pending_team_payments: Money
    approved_items: int
    # Since 2026-11-28 revenue is money received from clients and team cost is money paid to the
    # team (salaries and manager top-ups). The work side stays here for the small print.
    received_count: int = 0
    salaries_paid: Money = Decimal("0.00")
    topups_paid: Money = Decimal("0.00")
    work_delivered: Money = Decimal("0.00")
    cost_earned: Money = Decimal("0.00")


class DashboardTrendPoint(BaseModel):
    month: date
    revenue: Money
    team_cost: Money
    margin: Money


class DashboardAttentionTask(BaseModel):
    id: UUID
    code: str
    title: str
    client_name: str
    assignee_name: str | None
    due_date: date
    status: TaskStatus
    is_overdue: bool


class DashboardTeamLoad(BaseModel):
    person: PersonRef
    open_tasks: int
    completed_tasks: int
    pending: Money


class DashboardBudgetWatch(BaseModel):
    client: NamedRef
    total: Money
    used: Money
    committed: Money
    remaining: Money
    percent_used: float
    over: bool


class DashboardClientPayment(BaseModel):
    """How much a client has paid against the work billed to them (all time)."""

    client: NamedRef
    billed: Money
    received: Money
    due: Money
    percent_paid: float
    last_payment_on: date | None
    unpaid_invoices: int
    overdue_invoices: int


class AdminDashboardResponse(BaseModel):
    """Admin home: money, trend, work, team and budgets in one call (Admin only)."""

    period: PeriodResponse
    previous_period: PeriodResponse | None
    currency: str
    money: DashboardMoney
    trend: list[DashboardTrendPoint]
    status_counts: dict[str, int]
    open_tasks: int
    overdue_tasks: int
    due_this_week: int
    attention: list[DashboardAttentionTask]
    team: list[DashboardTeamLoad]
    budgets: list[DashboardBudgetWatch]
    client_payments: list[DashboardClientPayment]


ManagerEarningsResponse.model_rebuild()
EmployeeSalaryResponse.model_rebuild()


class FocusTask(BaseModel):
    """A task on the dashboard's Today panel (owner request 2026-11-19)."""

    id: UUID
    code: str
    title: str
    client_name: str
    service_name: str
    priority: TaskPriority
    status: TaskStatus
    due_date: date | None
    days_left: int | None  # negative: days late
    assignee_name: str | None
    monitor_name: str | None
    my_role: Literal["ASSIGNEE", "MONITOR"] | None = None


class TaskFocusResponse(BaseModel):
    today: date
    overdue: list[FocusTask]
    due_today: list[FocusTask]
    this_week: list[FocusTask]
    to_review: list[FocusTask]
    to_assign: list[FocusTask] = []  # admin only: Pending and nobody assigned
