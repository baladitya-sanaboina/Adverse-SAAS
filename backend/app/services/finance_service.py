"""Budgets, payments, salaries, payouts, earnings, dashboards and reports.

Money visibility (docs/ProductionManagementPlan.md, section 4):
- Admin: everything.
- Manager: only their own commission and payouts.
- Employee: only their own salary and salary payments.
- Client: only their own budget, charges and payments, as counts and totals (no task list).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.repositories.finance_repository import (
    ClientPaymentRow,
    FinanceRepository,
    PayoutRow,
    SalaryDateConflict,
    SalaryPaymentRow,
    SalaryRecordRow,
)
from app.repositories.task_repository import PersonRow, TaskRepository
from app.schemas.authentication import AuthContext
from app.schemas.production import (
    AdminDashboardResponse,
    BudgetEntryRequest,
    BudgetEntryResponse,
    ClientBudgetResponse,
    ClientBudgetSummary,
    ClientDeliveryLine,
    ClientMonthPoint,
    ClientPaymentLine,
    ClientPaymentListResponse,
    ClientPaymentRequest,
    ClientPaymentResponse,
    ClientPaymentUpdate,
    ClientReportResponse,
    ClientReportRow,
    ClientServiceCount,
    ClientWorkspaceSummaryResponse,
    CommissionTaskLine,
    DashboardAttentionTask,
    DashboardBudgetWatch,
    DashboardClientPayment,
    DashboardMoney,
    DashboardTeamLoad,
    DashboardTrendPoint,
    EmployeeSalaryResponse,
    FinanceSummaryResponse,
    ManagerEarningsResponse,
    ManagerPayoutListResponse,
    ManagerPayoutRequest,
    ManagerPayoutResponse,
    ManagerPayoutUpdate,
    ManagerWallet,
    NamedRef,
    PaymentListFilters,
    PeriodQuery,
    PeriodResponse,
    PersonFinanceResponse,
    PersonRef,
    SalaryMonthLine,
    SalaryPaymentListResponse,
    SalaryPaymentRequest,
    SalaryPaymentResponse,
    SalaryPaymentUpdate,
    SalaryRecordResponse,
    SalaryRecordUpdate,
    SalaryRequest,
    ServiceReportResponse,
    ServiceReportRow,
    TaskCounts,
    TeamReportResponse,
    TeamReportRow,
    WalletLine,
    WalletPeriod,
    WorkerTaskFilters,
    WorkspaceDashboardResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.notification_service import notification_service
from app.services.permission_service import validate_user_action_access
from app.services.production_rules import (
    BILLABLE_STATUSES,
    SalaryRate,
    budget_cycles,
    budget_position,
    last_month_starts,
    money,
    monthly_totals,
    resolve_period,
    salary_cost_in_range,
    salary_due_by_month,
    wallet_timeline,
)
from app.services.task_events import money_text
from app.services.task_service import WORKER_ROLES, TaskService

ZERO = Decimal("0.00")


def _pages(total: int, page_size: int) -> int:
    return max(1, (total + page_size - 1) // page_size)


def _rates(records: list[SalaryRecordRow]) -> list[SalaryRate]:
    return [
        SalaryRate(record.monthly_amount, record.effective_from, record.effective_to)
        for record in records
    ]


class FinanceService:
    def __init__(
        self,
        repository: FinanceRepository | None = None,
        task_repository: TaskRepository | None = None,
        task_service: TaskService | None = None,
    ):
        self.repository = repository or FinanceRepository()
        self.tasks = task_repository or TaskRepository()
        self.task_service = task_service or TaskService(self.tasks, self.repository)

    # -- access ----------------------------------------------------------------------------

    @staticmethod
    def _admin(context: AuthContext, module: str, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Only the Company Admin can see company finances."
            )
        if not validate_user_action_access(str(context.user_id), context.role, module, action):
            raise AuthenticationError(
                403,
                f"{module}_{action}_REQUIRED",
                f"{module.title()} {action.lower()} permission is required.",
            )
        return context.company_id

    @staticmethod
    def _worker(context: AuthContext) -> tuple[UUID, str]:
        role = WORKER_ROLES.get(context.role)
        if role is None or context.company_id is None:
            raise AuthenticationError(
                403, "TEAM_MEMBER_REQUIRED", "Only managers and employees have earnings."
            )
        return context.company_id, role

    def _zone(self, company_id: UUID) -> tuple[str, date]:
        name = self.repository.company_timezone(company_id)
        try:
            zone = ZoneInfo(name)
        except Exception:
            name, zone = "UTC", ZoneInfo("UTC")
        return name, datetime.now(zone).date()

    def _period(
        self, query: PeriodQuery, today: date
    ) -> tuple[date | None, date | None, PeriodResponse]:
        try:
            start, end = resolve_period(query.period, today, query.start, query.end)
        except ValueError as error:
            raise AuthenticationError(422, "INVALID_PERIOD", str(error)) from error
        return start, end, PeriodResponse(period=query.period, start=start, end=end)

    def _require_client(self, company_id: UUID, client_id: UUID) -> NamedRef:
        client = self.tasks.get_client(company_id, client_id)
        if client is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        return NamedRef(id=client.id, name=client.name, code=client.code)

    def _require_person(self, company_id: UUID, user_id: UUID, role: str | None) -> PersonRow:
        person = self.tasks.get_person_any_status(company_id, user_id)
        if person is None or (role is not None and person.role != role):
            label = {"MANAGER": "Manager", "EMPLOYEE": "Employee"}.get(role or "", "Person")
            raise AuthenticationError(404, f"{label.upper()}_NOT_FOUND", f"{label} was not found.")
        return person

    # -- response builders -----------------------------------------------------------------

    @staticmethod
    def _client_payment(row: ClientPaymentRow) -> ClientPaymentResponse:
        return ClientPaymentResponse(
            id=row.id,
            client=NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
            amount=money(row.amount),
            currency=row.currency,
            received_on=row.received_on,
            method=row.method,
            reference=row.reference,
            note=row.note,
            created_by_name=row.created_by_name,
            created_at=row.created_at,
        )

    @staticmethod
    def _salary_payment(row: SalaryPaymentRow) -> SalaryPaymentResponse:
        return SalaryPaymentResponse(**{**row.__dict__, "amount": money(row.amount)})

    @staticmethod
    def _payout(row: PayoutRow) -> ManagerPayoutResponse:
        return ManagerPayoutResponse(**{**row.__dict__, "amount": money(row.amount)})

    @staticmethod
    def _salary_record(row: SalaryRecordRow) -> SalaryRecordResponse:
        return SalaryRecordResponse(
            id=row.id,
            monthly_amount=money(row.monthly_amount),
            currency=row.currency,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            note=row.note,
            created_by_name=row.created_by_name,
            created_at=row.created_at,
        )

    # -- earnings shared by admin and the person themselves ---------------------------------

    @staticmethod
    def _wallet(tz: str, tasks: list[Any], payouts: list[PayoutRow]) -> ManagerWallet:
        """Top-ups (payouts) minus commission on approved work, with one period per top-up."""
        try:
            zone = ZoneInfo(tz)
        except Exception:  # noqa: BLE001
            zone = ZoneInfo("UTC")

        def local(moment: datetime) -> date:
            aware = moment if moment.tzinfo else moment.replace(tzinfo=ZoneInfo("UTC"))
            return aware.astimezone(zone).date()

        commissions = [
            (
                local(task.approved_at),
                f"TSK-{task.number:04d} · {task.title}",
                money(task.commission),
            )
            for task in tasks
            if task.status in BILLABLE_STATUSES
            and task.approved_at is not None
            and money(task.commission) > 0
        ]
        top_ups = [
            (payout.paid_on, payout.note or "Top-up", money(payout.amount)) for payout in payouts
        ]
        topped = sum((amount for _, _, amount in top_ups), ZERO)
        earned = sum((amount for _, _, amount in commissions), ZERO)
        cycles = budget_cycles(
            [(day, "TOP_UP", amount) for day, _, amount in top_ups],
            [(day, amount) for day, _, amount in commissions],
        )
        lines = wallet_timeline(top_ups, commissions)
        return ManagerWallet(
            topped_up=money(topped),
            earned=money(earned),
            balance=money(topped - earned),
            periods=[
                WalletPeriod(
                    index=cycle.index,
                    start=cycle.start,
                    end=cycle.end,
                    topped_up=cycle.amount,
                    earned=cycle.used,
                    balance=cycle.remaining,
                    items=cycle.items,
                )
                for cycle in cycles
            ],
            lines=[
                WalletLine(
                    day=line.day,
                    kind=line.kind,
                    title=line.title,
                    amount=line.amount,
                    balance=line.balance,
                )
                for line in reversed(lines[-200:])
            ],
        )

    def manager_earnings(self, company_id: UUID, manager_id: UUID) -> ManagerEarningsResponse:
        tz, today = self._zone(company_id)
        currency = self.repository.company_currency(company_id)
        tasks = self.repository.manager_commission_tasks(company_id, manager_id)
        earned = sum(
            (money(task.commission) for task in tasks if task.status in BILLABLE_STATUSES), ZERO
        )
        upcoming = sum(
            (money(task.commission) for task in tasks if task.status not in BILLABLE_STATUSES), ZERO
        )
        payouts = self.repository.list_payouts_for(company_id, manager_id)
        paid = sum((money(payout.amount) for payout in payouts), ZERO)
        month_start, month_end = resolve_period("this_month", today)
        return ManagerEarningsResponse(
            currency=currency,
            earned=earned,
            upcoming=upcoming,
            paid=paid,
            pending=max(earned - paid, ZERO),
            current_month_earned=money(
                self.repository.manager_commission_in_range(
                    company_id, manager_id, tz, month_start, month_end  # type: ignore[arg-type]
                )
            ),
            tasks=[
                CommissionTaskLine(
                    task_id=task.task_id,
                    code=f"TSK-{task.number:04d}",
                    title=task.title,
                    service_name=task.service_name,
                    status=task.status,
                    commission=money(task.commission),
                    approved_at=task.approved_at,
                )
                for task in tasks
            ],
            payouts=[self._payout(payout) for payout in payouts],
            wallet=self._wallet(tz, tasks, payouts),
        )

    def employee_salary(self, company_id: UUID, user_id: UUID) -> EmployeeSalaryResponse:
        _, today = self._zone(company_id)
        currency = self.repository.company_currency(company_id)
        records = self.repository.list_salary_records(company_id, user_id)
        due_months = salary_due_by_month(_rates(records), today)
        paid_by_month = self.repository.salary_paid_by_month(company_id, user_id)
        months = []
        for month, due in reversed(due_months):
            paid = money(paid_by_month.get(month, ZERO))
            months.append(
                SalaryMonthLine(month=month, due=due, paid=paid, pending=max(due - paid, ZERO))
            )
        total_due = sum((due for _, due in due_months), ZERO)
        total_paid = sum((money(value) for value in paid_by_month.values()), ZERO)
        current = next(
            (
                record
                for record in records
                if record.effective_from <= today
                and (record.effective_to is None or record.effective_to > today)
            ),
            None,
        )
        return EmployeeSalaryResponse(
            currency=currency,
            current_monthly_salary=money(current.monthly_amount) if current else None,
            total_due=total_due,
            total_paid=total_paid,
            pending=max(total_due - total_paid, ZERO),
            months=months,
            payments=[
                self._salary_payment(row)
                for row in self.repository.list_salary_payments_for(company_id, user_id)
            ],
        )

    # -- worker workspace ------------------------------------------------------------------

    def my_commission(self, context: AuthContext) -> ManagerEarningsResponse:
        company_id, role = self._worker(context)
        if role != "MANAGER":
            raise AuthenticationError(
                403, "MANAGER_REQUIRED", "Commission earnings are only for managers."
            )
        return self.manager_earnings(company_id, context.user_id)

    def my_salary(self, context: AuthContext) -> EmployeeSalaryResponse:
        company_id, role = self._worker(context)
        if role != "EMPLOYEE":
            raise AuthenticationError(
                403, "EMPLOYEE_REQUIRED", "Salary details are only for employees."
            )
        return self.employee_salary(company_id, context.user_id)

    def workspace_dashboard(self, context: AuthContext) -> WorkspaceDashboardResponse:
        company_id, role = self._worker(context)
        _, today = self._zone(company_id)
        counts = self.repository.worker_task_counts(company_id, context.user_id, today)
        if role == "MANAGER":
            earnings = self.manager_earnings(company_id, context.user_id)
            current_month, pending, currency = (
                earnings.current_month_earned,
                earnings.pending,
                earnings.currency,
            )
        else:
            salary = self.employee_salary(company_id, context.user_id)
            this_month = next(
                (line for line in salary.months if line.month == today.replace(day=1)), None
            )
            current_month = this_month.due if this_month else ZERO
            pending, currency = salary.pending, salary.currency
        upcoming = self.task_service.list_worker_tasks(
            context, WorkerTaskFilters(role="ASSIGNEE", page_size=5)
        ).items
        return WorkspaceDashboardResponse(
            role=role,
            counts=TaskCounts(**counts),
            currency=currency,
            current_month_earnings=current_month,
            pending_payment=pending,
            upcoming_tasks=[task for task in upcoming if task.status not in BILLABLE_STATUSES],
        )

    # -- client portal ---------------------------------------------------------------------

    def client_summary(self, context: AuthContext) -> ClientWorkspaceSummaryResponse:
        if context.role != "COMPANY_CLIENT" or context.company_id is None:
            raise AuthenticationError(
                403, "CLIENT_REQUIRED", "Only client accounts have a client summary."
            )
        company_id = context.company_id
        client = self.tasks.get_client_for_user(company_id, context.user_id)
        if client is None:
            raise AuthenticationError(
                404,
                "CLIENT_PROFILE_NOT_LINKED",
                "This login is not linked to a client profile yet. Please contact the agency.",
            )
        tz, today = self._zone(company_id)
        currency = self.repository.company_currency(company_id)
        services = [
            row
            for row in self.repository.client_service_counts(company_id, client.id, tz, None, None)
            if row.completed or row.in_progress
        ]
        totals = self.tasks.budget_totals(company_id, client.id)
        position = budget_position(totals.total, totals.used, totals.committed)
        payments = self.repository.list_client_payments_for_client(company_id, client.id)
        total_paid = sum((money(payment.amount) for payment in payments), ZERO)
        total_charged = money(totals.used)
        month_start, month_end = resolve_period("this_month", today)
        month_starts = last_month_starts(today, 6)
        recent = self.repository.client_deliveries(
            company_id, client.id, tz, start=month_starts[0], end=today
        )
        return ClientWorkspaceSummaryResponse(
            client_name=client.name,
            currency=currency,
            completed_items=sum(row.completed for row in services),
            in_progress_items=sum(row.in_progress for row in services),
            services=[
                ClientServiceCount(
                    service_id=row.service_id,
                    service_name=row.service_name,
                    completed=row.completed,
                    in_progress=row.in_progress,
                    charged=money(row.charged),
                )
                for row in services
            ],
            budget=ClientBudgetSummary(
                has_budget=position.has_budget,
                total=position.total,
                used=position.used,
                remaining=position.remaining,
                overage=position.overage,
            ),
            total_charged=total_charged,
            total_paid=total_paid,
            pending_amount=max(total_charged - total_paid, ZERO),
            current_month_charged=money(
                self.repository.client_month_charged(
                    company_id, client.id, tz, month_start, month_end  # type: ignore[arg-type]
                )
            ),
            payments=[
                ClientPaymentLine(
                    amount=money(payment.amount),
                    received_on=payment.received_on,
                    method=payment.method,
                    reference=payment.reference,
                )
                for payment in payments
            ],
            recent_deliveries=[
                ClientDeliveryLine(
                    title=row.title,
                    service_name=row.service_name,
                    delivered_on=row.delivered_on,
                    amount=money(row.amount),
                )
                for row in recent[:6]
            ],
            monthly=[
                ClientMonthPoint(month=start, items=items, amount=amount)
                for start, items, amount in monthly_totals(
                    [(row.delivered_on, row.amount) for row in recent], month_starts
                )
            ],
        )

    # -- admin: budgets --------------------------------------------------------------------

    def get_client_budget(self, context: AuthContext, client_id: UUID) -> ClientBudgetResponse:
        company_id = self._admin(context, "FINANCE", "VIEW")
        client = self._require_client(company_id, client_id)
        currency = self.repository.company_currency(company_id)
        return ClientBudgetResponse(
            client=client,
            budget=self.task_service.budget_check(
                company_id, client.id, client.name, currency, None
            ),
            entries=[
                BudgetEntryResponse(
                    id=entry.id,
                    type=entry.type,
                    amount=money(entry.amount),
                    currency=entry.currency,
                    note=entry.note,
                    created_by_name=entry.created_by_name,
                    created_at=entry.created_at,
                )
                for entry in self.repository.list_budget_entries(company_id, client.id)
            ],
        )

    def add_budget_entry(
        self, context: AuthContext, client_id: UUID, request: BudgetEntryRequest
    ) -> ClientBudgetResponse:
        company_id = self._admin(context, "FINANCE", "MANAGE")
        self._require_client(company_id, client_id)
        totals = self.tasks.budget_totals(company_id, client_id)
        if request.type == "ADJUSTMENT" and money(totals.total) + money(request.amount) < 0:
            raise AuthenticationError(
                422, "BUDGET_BELOW_ZERO", "An adjustment cannot take the budget below zero."
            )
        self.repository.add_budget_entry(
            company_id,
            client_id,
            context.user_id,
            request.type,
            money(request.amount),
            request.note,
        )
        if request.type in ("INITIAL", "TOP_UP") and money(request.amount) > 0:
            currency = self.repository.company_currency(company_id)
            notification_service.notify(
                company_id,
                [notification_service.client_user(company_id, client_id)],
                "budget.topup",
                "Budget added" if request.type == "INITIAL" else "Budget topped up",
                f"{money_text(money(request.amount), currency)} added to your budget.",
                "/dashboard#client-budget-panel",
                {"client_id": str(client_id)},
            )
        return self.get_client_budget(context, client_id)

    # -- admin: client payments ------------------------------------------------------------

    def list_client_payments(
        self, context: AuthContext, filters: PaymentListFilters
    ) -> ClientPaymentListResponse:
        company_id = self._admin(context, "FINANCE", "VIEW")
        rows, total, amount = self.repository.list_client_payments(company_id, filters)
        return ClientPaymentListResponse(
            items=[self._client_payment(row) for row in rows],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=_pages(total, filters.page_size),
            total_amount=money(amount),
        )

    def record_client_payment(
        self, context: AuthContext, request: ClientPaymentRequest
    ) -> ClientPaymentResponse:
        company_id = self._admin(context, "FINANCE", "CREATE")
        self._require_client(company_id, request.client_id)
        payment_id = self.repository.create_client_payment(
            company_id, context.user_id, request.model_dump()
        )
        row = self.repository.get_client_payment(company_id, payment_id)
        assert row is not None
        payment = self._client_payment(row)
        notification_service.notify(
            company_id,
            [notification_service.client_user(company_id, request.client_id)],
            "payment.received",
            "Payment received",
            f"{money_text(payment.amount, payment.currency)} received on "
            f"{payment.received_on:%d %b %Y}. Thank you.",
            "/dashboard",
            {"payment_id": str(payment_id)},
        )
        return payment

    def delete_payment(self, context: AuthContext, kind: str, payment_id: UUID) -> None:
        company_id = self._admin(context, "FINANCE", "DELETE")
        table = {
            "client": "client_payments",
            "salary": "salary_payments",
            "payout": "manager_payouts",
        }[kind]
        if not self.repository.delete_payment(table, company_id, payment_id, context.user_id):
            raise AuthenticationError(404, "PAYMENT_NOT_FOUND", "Payment was not found.")

    def update_client_payment(
        self, context: AuthContext, payment_id: UUID, request: ClientPaymentUpdate
    ) -> ClientPaymentResponse:
        company_id = self._admin(context, "FINANCE", "EDIT")
        if request.client_id is not None:
            self._require_client(company_id, request.client_id)
        self._update_payment("client_payments", company_id, payment_id, context, request)
        row = self.repository.get_client_payment(company_id, payment_id)
        assert row is not None
        return self._client_payment(row)

    def update_salary_payment(
        self, context: AuthContext, payment_id: UUID, request: SalaryPaymentUpdate
    ) -> SalaryPaymentResponse:
        company_id = self._admin(context, "FINANCE", "EDIT")
        self._update_payment("salary_payments", company_id, payment_id, context, request)
        row = self.repository.get_salary_payment(company_id, payment_id)
        assert row is not None
        return self._salary_payment(row)

    def update_payout(
        self, context: AuthContext, payout_id: UUID, request: ManagerPayoutUpdate
    ) -> ManagerPayoutResponse:
        company_id = self._admin(context, "FINANCE", "EDIT")
        self._update_payment("manager_payouts", company_id, payout_id, context, request)
        row = self.repository.get_payout(company_id, payout_id)
        assert row is not None
        return self._payout(row)

    def _update_payment(
        self,
        table: str,
        company_id: UUID,
        payment_id: UUID,
        context: AuthContext,
        request: ClientPaymentUpdate | SalaryPaymentUpdate | ManagerPayoutUpdate,
    ) -> None:
        updates = request.model_dump(exclude_unset=True)
        if "amount" in updates:
            updates["amount"] = money(updates["amount"])
        if not self.repository.update_payment(
            table, company_id, payment_id, context.user_id, updates
        ):
            raise AuthenticationError(404, "PAYMENT_NOT_FOUND", "Payment was not found.")

    # -- admin: salaries and payouts -------------------------------------------------------

    def update_salary_record(
        self, context: AuthContext, record_id: UUID, request: SalaryRecordUpdate
    ) -> PersonFinanceResponse:
        company_id = self._admin(context, "FINANCE", "EDIT")
        user_id = self.repository.update_salary_record(
            company_id,
            record_id,
            context.user_id,
            money(request.monthly_amount) if request.monthly_amount is not None else None,
            request.note,
        )
        if user_id is None:
            raise AuthenticationError(404, "SALARY_NOT_FOUND", "Salary record was not found.")
        return self.person_finance(context, user_id)

    def delete_salary_record(self, context: AuthContext, record_id: UUID) -> PersonFinanceResponse:
        company_id = self._admin(context, "FINANCE", "DELETE")
        user_id = self.repository.delete_salary_record(company_id, record_id, context.user_id)
        if user_id is None:
            raise AuthenticationError(404, "SALARY_NOT_FOUND", "Salary record was not found.")
        return self.person_finance(context, user_id)

    def set_salary(
        self, context: AuthContext, user_id: UUID, request: SalaryRequest
    ) -> PersonFinanceResponse:
        company_id = self._admin(context, "FINANCE", "MANAGE")
        self._require_person(company_id, user_id, "EMPLOYEE")
        try:
            self.repository.set_salary(
                company_id,
                context.user_id,
                user_id,
                money(request.monthly_amount),
                request.effective_from,
                request.note,
            )
        except SalaryDateConflict as error:
            raise AuthenticationError(
                409,
                "SALARY_CONFLICT",
                "This salary overlaps an existing open salary. Refresh and try again.",
            ) from error
        return self.person_finance(context, user_id)

    def person_finance(self, context: AuthContext, user_id: UUID) -> PersonFinanceResponse:
        company_id = self._admin(context, "FINANCE", "VIEW")
        person = self._require_person(company_id, user_id, None)
        is_manager = person.role == "MANAGER"
        return PersonFinanceResponse(
            person=PersonRef(id=person.id, name=person.name, role=person.role),
            manager=self.manager_earnings(company_id, user_id) if is_manager else None,
            employee=None if is_manager else self.employee_salary(company_id, user_id),
            salary_history=[
                self._salary_record(row)
                for row in self.repository.list_salary_records(company_id, user_id)
            ],
        )

    def list_salary_payments(
        self, context: AuthContext, filters: PaymentListFilters
    ) -> SalaryPaymentListResponse:
        company_id = self._admin(context, "FINANCE", "VIEW")
        rows, total, amount = self.repository.list_salary_payments(company_id, filters)
        return SalaryPaymentListResponse(
            items=[self._salary_payment(row) for row in rows],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=_pages(total, filters.page_size),
            total_amount=money(amount),
        )

    def record_salary_payment(
        self, context: AuthContext, request: SalaryPaymentRequest
    ) -> SalaryPaymentResponse:
        company_id = self._admin(context, "FINANCE", "CREATE")
        self._require_person(company_id, request.user_id, "EMPLOYEE")
        payment_id = self.repository.create_salary_payment(
            company_id, context.user_id, request.model_dump()
        )
        row = self.repository.get_salary_payment(company_id, payment_id)
        assert row is not None
        payment = self._salary_payment(row)
        notification_service.notify(
            company_id,
            [request.user_id],
            "salary.paid",
            "Salary paid",
            f"{money_text(payment.amount, payment.currency)} paid on {payment.paid_on:%d %b %Y}.",
            "/salary",
            {"payment_id": str(payment_id)},
        )
        return payment

    def list_payouts(
        self, context: AuthContext, filters: PaymentListFilters
    ) -> ManagerPayoutListResponse:
        company_id = self._admin(context, "FINANCE", "VIEW")
        rows, total, amount = self.repository.list_payouts(company_id, filters)
        return ManagerPayoutListResponse(
            items=[self._payout(row) for row in rows],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=_pages(total, filters.page_size),
            total_amount=money(amount),
        )

    def record_payout(
        self, context: AuthContext, request: ManagerPayoutRequest
    ) -> ManagerPayoutResponse:
        company_id = self._admin(context, "FINANCE", "CREATE")
        self._require_person(company_id, request.manager_user_id, "MANAGER")
        payout_id = self.repository.create_payout(company_id, context.user_id, request.model_dump())
        row = self.repository.get_payout(company_id, payout_id)
        assert row is not None
        payout = self._payout(row)
        notification_service.notify(
            company_id,
            [request.manager_user_id],
            "payout.paid",
            "Top-up received",
            f"{money_text(payout.amount, payout.currency)} paid on {payout.paid_on:%d %b %Y}.",
            "/earnings",
            {"payout_id": str(payout_id)},
        )
        return payout

    # -- admin: dashboard and reports ------------------------------------------------------

    def _pending_team_payments(self, company_id: UUID, today: date) -> tuple[Decimal, Decimal]:
        earned = self.repository.manager_earned_totals(company_id)
        paid = self.repository.manager_payout_totals(company_id)
        manager_pending = sum(
            (
                max(money(amount) - money(paid.get(user, ZERO)), ZERO)
                for user, amount in earned.items()
            ),
            ZERO,
        )
        salary_paid = self.repository.salary_paid_totals(company_id)
        records = self.repository.list_salary_records(company_id, None)
        by_user: dict[UUID, list[SalaryRecordRow]] = {}
        for record in records:
            by_user.setdefault(record.user_id, []).append(record)
        salary_pending = ZERO
        for user, user_records in by_user.items():
            due = sum(
                (amount for _, amount in salary_due_by_month(_rates(user_records), today)), ZERO
            )
            salary_pending += max(due - money(salary_paid.get(user, ZERO)), ZERO)
        return manager_pending, salary_pending

    def _salary_cost(
        self, company_id: UUID, start: date | None, end: date | None, today: date
    ) -> Decimal:
        records = self.repository.list_salary_records(company_id, None)
        by_user: dict[UUID, list[SalaryRecordRow]] = {}
        for record in records:
            by_user.setdefault(record.user_id, []).append(record)
        total = ZERO
        for user_records in by_user.values():
            rates = _rates(user_records)
            if start is None or end is None:
                total += sum((amount for _, amount in salary_due_by_month(rates, today)), ZERO)
            else:
                total += salary_cost_in_range(rates, start, end)
        return money(total)

    def finance_summary(self, context: AuthContext, query: PeriodQuery) -> FinanceSummaryResponse:
        company_id = self._admin(context, "FINANCE", "VIEW")
        tz, today = self._zone(company_id)
        start, end, period = self._period(query, today)
        currency = self.repository.company_currency(company_id)
        revenue, commission, approved = self.repository.revenue_in_range(company_id, tz, start, end)
        salary_cost = self._salary_cost(company_id, start, end, today)
        team_cost = money(commission) + salary_cost
        balances = self.repository.client_balances(company_id, tz, None, None)
        pending_clients = sum(
            (
                max(money(row.billed_all_time) - money(row.received_all_time), ZERO)
                for row in balances
            ),
            ZERO,
        )
        manager_pending, salary_pending = self._pending_team_payments(company_id, today)
        counts = self.repository.task_counts(company_id, today)
        top = self.repository.top_client_by_open_tasks(company_id)
        return FinanceSummaryResponse(
            period=period,
            currency=currency,
            revenue=money(revenue),
            commission_cost=money(commission),
            salary_cost=salary_cost,
            team_cost=team_cost,
            gross_margin=money(revenue) - team_cost,
            approved_items=approved,
            pending_client_payments=pending_clients,
            pending_manager_payments=manager_pending,
            pending_salary_payments=salary_pending,
            pending_team_payments=manager_pending + salary_pending,
            open_tasks=counts.open_tasks,
            unassigned_tasks=counts.unassigned,
            in_review_tasks=counts.in_review,
            overdue_tasks=counts.overdue,
            top_client=NamedRef(id=top[0], name=top[1], code=top[2]) if top else None,
            top_client_open_tasks=top[3] if top else 0,
        )

    def client_report(self, context: AuthContext, query: PeriodQuery) -> ClientReportResponse:
        company_id = self._admin(context, "REPORTS", "VIEW")
        tz, today = self._zone(company_id)
        start, end, period = self._period(query, today)
        rows = []
        for row in self.repository.client_balances(company_id, tz, start, end):
            services = [
                ClientServiceCount(
                    service_id=item.service_id,
                    service_name=item.service_name,
                    completed=item.completed,
                    in_progress=item.in_progress,
                    charged=money(item.charged),
                )
                for item in self.repository.client_service_counts(
                    company_id, row.client_id, tz, start, end
                )
                if item.completed or item.in_progress
            ]
            billed_all = money(row.billed_all_time)
            rows.append(
                ClientReportRow(
                    client=NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
                    total_tasks=row.total_tasks,
                    completed_tasks=row.completed_tasks,
                    open_tasks=row.open_tasks,
                    billed=money(row.billed_in_range),
                    received=money(row.received_in_range),
                    pending=max(billed_all - money(row.received_all_time), ZERO),
                    budget_total=money(row.budget_total),
                    budget_remaining=max(money(row.budget_total) - billed_all, ZERO),
                    services=services,
                )
            )
        return ClientReportResponse(
            period=period, currency=self.repository.company_currency(company_id), rows=rows
        )

    def team_report(self, context: AuthContext, query: PeriodQuery) -> TeamReportResponse:
        company_id = self._admin(context, "REPORTS", "VIEW")
        tz, today = self._zone(company_id)
        start, end, period = self._period(query, today)
        records = self.repository.list_salary_records(company_id, None)
        by_user: dict[UUID, list[SalaryRecordRow]] = {}
        for record in records:
            by_user.setdefault(record.user_id, []).append(record)
        rows = []
        for row in self.repository.people_work(company_id, tz, start, end):
            if row.role == "MANAGER":
                earnings = money(row.commission_in_range)
                paid = money(row.payouts_in_range)
                pending = max(money(row.commission_all_time) - money(row.payouts_all_time), ZERO)
            else:
                rates = _rates(by_user.get(row.user_id, []))
                due_all = sum((amount for _, amount in salary_due_by_month(rates, today)), ZERO)
                earnings = (
                    due_all
                    if start is None or end is None
                    else salary_cost_in_range(rates, start, end)
                )
                paid = money(row.salary_paid_in_range)
                pending = max(due_all - money(row.salary_paid_all_time), ZERO)
            rows.append(
                TeamReportRow(
                    person=PersonRef(id=row.user_id, name=row.name, role=row.role),
                    total_tasks=row.total_tasks,
                    completed_tasks=row.completed_tasks,
                    open_tasks=row.open_tasks,
                    earnings=earnings,
                    paid=paid,
                    pending=pending,
                )
            )
        return TeamReportResponse(
            period=period, currency=self.repository.company_currency(company_id), rows=rows
        )

    def service_report(self, context: AuthContext, query: PeriodQuery) -> ServiceReportResponse:
        company_id = self._admin(context, "REPORTS", "VIEW")
        tz, today = self._zone(company_id)
        start, end, period = self._period(query, today)
        rows = [
            ServiceReportRow(
                service=NamedRef(
                    id=item.service_id, name=item.service_name, code=item.service_code
                ),
                items=item.completed,
                revenue=money(item.charged),
                commission_cost=money(item.commission),
                margin=money(item.charged) - money(item.commission),
            )
            for item in self.repository.client_service_counts(company_id, None, tz, start, end)
        ]
        totals = ServiceReportRow(
            service=NamedRef(id=company_id, name="All services", code="TOTAL"),
            items=sum(row.items for row in rows),
            revenue=sum((row.revenue for row in rows), ZERO),
            commission_cost=sum((row.commission_cost for row in rows), ZERO),
            margin=sum((row.margin for row in rows), ZERO),
        )
        return ServiceReportResponse(
            period=period,
            currency=self.repository.company_currency(company_id),
            rows=rows,
            totals=totals if rows else None,
        )

    # -- admin: home dashboard ---------------------------------------------------------------

    def _previous_range(
        self, period: str, today: date, start: date | None, end: date | None
    ) -> tuple[date, date] | None:
        """The comparison range: previous month for "this month", else the same-length range before."""
        if start is None or end is None:
            return None
        if period == "this_month":
            previous_start, previous_end = resolve_period("previous_month", today)
            assert previous_start is not None and previous_end is not None
            return previous_start, previous_end
        length = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        return previous_end - timedelta(days=length - 1), previous_end

    def admin_dashboard(self, context: AuthContext, query: PeriodQuery) -> AdminDashboardResponse:
        company_id = self._admin(context, "FINANCE", "VIEW")
        tz, today = self._zone(company_id)
        start, end, period = self._period(query, today)
        summary = self.finance_summary(context, query)
        currency = summary.currency

        previous_revenue: Decimal | None = None
        previous_period: PeriodResponse | None = None
        previous = self._previous_range(query.period, today, start, end)
        if previous is not None:
            previous_revenue, _, _ = self.repository.revenue_in_range(
                company_id, tz, previous[0], previous[1]
            )
            previous_revenue = money(previous_revenue)
            previous_period = PeriodResponse(period="custom", start=previous[0], end=previous[1])
        revenue = summary.revenue
        change = (
            float((revenue - previous_revenue) / previous_revenue * 100)
            if previous_revenue is not None and previous_revenue > 0
            else None
        )

        trend = []
        month_start = today.replace(day=1)
        months = []
        for _ in range(6):
            months.append(month_start)
            month_start = (month_start - timedelta(days=1)).replace(day=1)
        for first in reversed(months):
            last = resolve_period("this_month", first)[1]
            assert last is not None
            month_revenue, month_commission, _ = self.repository.revenue_in_range(
                company_id, tz, first, last
            )
            month_cost = money(month_commission) + self._salary_cost(company_id, first, last, today)
            trend.append(
                DashboardTrendPoint(
                    month=first,
                    revenue=money(month_revenue),
                    team_cost=month_cost,
                    margin=money(month_revenue) - month_cost,
                )
            )

        attention_rows = self.repository.attention_tasks(company_id, today + timedelta(days=7))
        due_this_week = sum(1 for row in attention_rows if row.due_date >= today)

        team = sorted(
            (
                DashboardTeamLoad(
                    person=row.person,
                    open_tasks=row.open_tasks,
                    completed_tasks=row.completed_tasks,
                    pending=row.pending,
                )
                for row in self.team_report(context, query).rows
            ),
            key=lambda item: (-item.open_tasks, item.person.name),
        )

        budgets = []
        client_payments = []
        for row in self.repository.client_balances(company_id, tz, None, None):
            billed = money(row.billed_all_time)
            received = money(row.received_all_time)
            if billed > 0 or received > 0:
                client_payments.append(
                    DashboardClientPayment(
                        client=NamedRef(
                            id=row.client_id, name=row.client_name, code=row.client_code
                        ),
                        billed=billed,
                        received=received,
                        due=max(billed - received, ZERO),
                        percent_paid=(
                            min(float(received / billed * 100), 100.0) if billed > 0 else 100.0
                        ),
                        last_payment_on=row.last_payment_on,
                        unpaid_invoices=row.unpaid_invoices,
                        overdue_invoices=row.overdue_invoices,
                    )
                )
            total = money(row.budget_total)
            if total <= 0:
                continue
            used = money(row.billed_all_time)
            committed = money(self.tasks.budget_totals(company_id, row.client_id).committed)
            budgets.append(
                DashboardBudgetWatch(
                    client=NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
                    total=total,
                    used=used,
                    committed=committed,
                    remaining=max(total - used, ZERO),
                    percent_used=float(used / total * 100),
                    over=used > total,
                )
            )
        budgets.sort(key=lambda item: -item.percent_used)

        return AdminDashboardResponse(
            period=period,
            previous_period=previous_period,
            currency=currency,
            money=DashboardMoney(
                revenue=revenue,
                previous_revenue=previous_revenue,
                revenue_change_pct=change,
                team_cost=summary.team_cost,
                commission_cost=summary.commission_cost,
                salary_cost=summary.salary_cost,
                gross_margin=summary.gross_margin,
                margin_pct=float(summary.gross_margin / revenue * 100) if revenue > 0 else None,
                pending_client_payments=summary.pending_client_payments,
                pending_team_payments=summary.pending_team_payments,
                approved_items=summary.approved_items,
            ),
            trend=trend,
            status_counts=self.repository.status_counts(company_id),
            open_tasks=summary.open_tasks,
            overdue_tasks=summary.overdue_tasks,
            due_this_week=due_this_week,
            attention=[
                DashboardAttentionTask(
                    id=row.id,
                    code=f"TSK-{row.number:04d}",
                    title=row.title,
                    client_name=row.client_name,
                    assignee_name=row.assignee_name,
                    due_date=row.due_date,
                    status=row.status,
                    is_overdue=row.due_date < today,
                )
                for row in attention_rows
            ],
            team=team[:8],
            budgets=budgets[:6],
            # Most money owed first; clients who are paid up go last.
            client_payments=sorted(
                client_payments, key=lambda item: (-item.due, -item.overdue_invoices)
            )[:6],
        )


finance_service = FinanceService()
