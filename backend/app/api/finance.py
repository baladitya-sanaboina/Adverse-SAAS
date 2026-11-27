"""Admin-only money endpoints: dashboard summary, reports, budgets, payments, salaries, payouts."""

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import ValidationError

from app.middleware.authentication import AuthenticatedContext
from app.schemas.invoices import PaymentSheet, SheetsOverviewResponse
from app.schemas.production import (
    AdminDashboardResponse,
    BudgetEntryRequest,
    ClientBudgetResponse,
    ClientPaymentListResponse,
    ClientPaymentRequest,
    ClientPaymentResponse,
    ClientPaymentUpdate,
    ClientReportResponse,
    EarningsResponse,
    FinanceSummaryResponse,
    ManagerPayoutListResponse,
    ManagerPayoutRequest,
    ManagerPayoutResponse,
    ManagerPayoutUpdate,
    PaymentListFilters,
    PeriodQuery,
    PersonFinanceResponse,
    SalaryPaymentListResponse,
    SalaryPaymentRequest,
    SalaryPaymentResponse,
    SalaryPaymentUpdate,
    SalaryRecordUpdate,
    SalaryRequest,
    ServiceReportResponse,
    TeamReportResponse,
)
from app.schemas.registration import ErrorResponse
from app.services.authentication_service import AuthenticationError
from app.services.finance_service import finance_service
from app.services.invoice_service import invoice_service
from app.services.production_rules import ReportPeriod

router = APIRouter(prefix="/company/finance", tags=["finance"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Only the Company Admin can see finances."},
    404: {"model": ErrorResponse, "description": "The client, person or payment was not found."},
    409: {"model": ErrorResponse, "description": "The change conflicts with existing records."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


def _period(period: ReportPeriod, start: date | None, end: date | None) -> PeriodQuery:
    # Built after FastAPI's own validation, so turn a bad range into a 422, not a 500.
    try:
        return PeriodQuery(period=period, start=start, end=end)
    except ValidationError as error:
        message = error.errors()[0]["msg"].removeprefix("Value error, ")
        raise AuthenticationError(422, "INVALID_PERIOD", message) from error


def _payments(
    subject_id: UUID | None, start: date | None, end: date | None, page: int, page_size: int
) -> PaymentListFilters:
    return PaymentListFilters(
        subject_id=subject_id, start=start, end=end, page=page, page_size=page_size
    )


# -- dashboard and reports ----------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    summary="Admin home: money with change, 6-month trend, work, team load and budget watch",
    responses=ERRORS,
)
def dashboard(
    context: AuthenticatedContext,
    period: ReportPeriod = Query("this_month"),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> AdminDashboardResponse:
    return finance_service.admin_dashboard(context, _period(period, start, end))


@router.get(
    "/earnings",
    response_model=EarningsResponse,
    summary="Admin only: every delivery of the last three years, for the Earnings section",
    responses=ERRORS,
)
def earnings(context: AuthenticatedContext) -> EarningsResponse:
    return finance_service.earnings(context)


@router.get(
    "/summary",
    response_model=FinanceSummaryResponse,
    summary="Revenue, team cost, gross margin, pending payments and task counts",
    responses=ERRORS,
)
def summary(
    context: AuthenticatedContext,
    period: ReportPeriod = Query("this_month"),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> FinanceSummaryResponse:
    return finance_service.finance_summary(context, _period(period, start, end))


@router.get(
    "/reports/clients",
    response_model=ClientReportResponse,
    summary="Report by client",
    responses=ERRORS,
)
def client_report(
    context: AuthenticatedContext,
    period: ReportPeriod = Query("this_month"),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> ClientReportResponse:
    return finance_service.client_report(context, _period(period, start, end))


@router.get(
    "/reports/team",
    response_model=TeamReportResponse,
    summary="Report by team member",
    responses=ERRORS,
)
def team_report(
    context: AuthenticatedContext,
    period: ReportPeriod = Query("this_month"),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> TeamReportResponse:
    return finance_service.team_report(context, _period(period, start, end))


@router.get(
    "/reports/services",
    response_model=ServiceReportResponse,
    summary="Report by service",
    responses=ERRORS,
)
def service_report(
    context: AuthenticatedContext,
    period: ReportPeriod = Query("this_month"),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> ServiceReportResponse:
    return finance_service.service_report(context, _period(period, start, end))


# -- client budgets -----------------------------------------------------------------------


@router.get(
    "/budgets/{client_id}",
    response_model=ClientBudgetResponse,
    summary="A client's one-time budget: total, used, committed, remaining and history",
    responses=ERRORS,
)
def get_budget(client_id: UUID, context: AuthenticatedContext) -> ClientBudgetResponse:
    return finance_service.get_client_budget(context, client_id)


@router.post(
    "/budgets/{client_id}/entries",
    response_model=ClientBudgetResponse,
    status_code=201,
    summary="Set the initial budget, add a top-up or record an adjustment",
    responses=ERRORS,
)
def add_budget_entry(
    client_id: UUID, request: BudgetEntryRequest, context: AuthenticatedContext
) -> ClientBudgetResponse:
    return finance_service.add_budget_entry(context, client_id, request)


# -- payment sheets ------------------------------------------------------------------------


@router.get(
    "/sheets",
    response_model=SheetsOverviewResponse,
    summary="Every manager's and client's payment sheets, most urgent first (Admin only)",
    responses=ERRORS,
)
def payment_sheets(context: AuthenticatedContext) -> SheetsOverviewResponse:
    return invoice_service.sheets_overview(context)


@router.get(
    "/sheets/clients/{client_id}",
    response_model=list[PaymentSheet],
    summary="One client's payment sheets (Admin only)",
    responses=ERRORS,
)
def client_payment_sheets(client_id: UUID, context: AuthenticatedContext) -> list[PaymentSheet]:
    return invoice_service.client_sheets(context, client_id)


@router.get(
    "/people/{user_id}/payslips/{month}.pdf",
    summary="An employee's payslip for one month, e.g. 2026-11 (Admin only)",
    responses=ERRORS,
    response_class=Response,
)
def employee_payslip(user_id: UUID, month: str, context: AuthenticatedContext) -> Response:
    content, filename = finance_service.admin_payslip(context, user_id, _month(month))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _month(value: str) -> date:
    try:
        return date.fromisoformat(f"{value[:7]}-01")
    except ValueError as error:
        raise AuthenticationError(422, "MONTH_INVALID", "Use a month like 2026-11.") from error


@router.get(
    "/sheets/managers/{manager_id}/{index}/statement.pdf",
    summary="A manager's payment sheet as a statement PDF (Admin only)",
    responses=ERRORS,
    response_class=Response,
)
def manager_sheet_statement(
    manager_id: UUID, index: int, context: AuthenticatedContext
) -> Response:
    content, filename = invoice_service.manager_statement_pdf(context, manager_id, index)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# -- client payments ----------------------------------------------------------------------


@router.get(
    "/client-payments",
    response_model=ClientPaymentListResponse,
    summary="Payments received from clients",
    responses=ERRORS,
)
def list_client_payments(
    context: AuthenticatedContext,
    client_id: UUID | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ClientPaymentListResponse:
    return finance_service.list_client_payments(
        context, _payments(client_id, start, end, page, page_size)
    )


@router.post(
    "/client-payments",
    response_model=ClientPaymentResponse,
    status_code=201,
    summary="Record a payment received from a client",
    responses=ERRORS,
)
def record_client_payment(
    request: ClientPaymentRequest, context: AuthenticatedContext
) -> ClientPaymentResponse:
    return finance_service.record_client_payment(context, request)


# -- salaries -----------------------------------------------------------------------------


@router.get(
    "/people/{user_id}",
    response_model=PersonFinanceResponse,
    summary="A manager's commission or an employee's salary position",
    responses=ERRORS,
)
def person_finance(user_id: UUID, context: AuthenticatedContext) -> PersonFinanceResponse:
    return finance_service.person_finance(context, user_id)


@router.put(
    "/people/{user_id}/salary",
    response_model=PersonFinanceResponse,
    summary="Set an employee's monthly salary from a date (earlier salaries kept as history)",
    responses=ERRORS,
)
def set_salary(
    user_id: UUID, request: SalaryRequest, context: AuthenticatedContext
) -> PersonFinanceResponse:
    return finance_service.set_salary(context, user_id, request)


@router.get(
    "/salary-payments",
    response_model=SalaryPaymentListResponse,
    summary="Salary payments made to employees",
    responses=ERRORS,
)
def list_salary_payments(
    context: AuthenticatedContext,
    user_id: UUID | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SalaryPaymentListResponse:
    return finance_service.list_salary_payments(
        context, _payments(user_id, start, end, page, page_size)
    )


@router.post(
    "/salary-payments",
    response_model=SalaryPaymentResponse,
    status_code=201,
    summary="Record a salary payment",
    responses=ERRORS,
)
def record_salary_payment(
    request: SalaryPaymentRequest, context: AuthenticatedContext
) -> SalaryPaymentResponse:
    return finance_service.record_salary_payment(context, request)


# -- manager payouts ----------------------------------------------------------------------


@router.get(
    "/manager-payouts",
    response_model=ManagerPayoutListResponse,
    summary="Commission paid out to managers",
    responses=ERRORS,
)
def list_payouts(
    context: AuthenticatedContext,
    manager_user_id: UUID | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ManagerPayoutListResponse:
    return finance_service.list_payouts(
        context, _payments(manager_user_id, start, end, page, page_size)
    )


@router.post(
    "/manager-payouts",
    response_model=ManagerPayoutResponse,
    status_code=201,
    summary="Record a commission payout to a manager",
    responses=ERRORS,
)
def record_payout(
    request: ManagerPayoutRequest, context: AuthenticatedContext
) -> ManagerPayoutResponse:
    return finance_service.record_payout(context, request)


# -- edits (declared before the generic DELETE /{kind}/{id} so these paths win) --------------


@router.patch(
    "/client-payments/{payment_id}",
    response_model=ClientPaymentResponse,
    summary="Edit a payment received from a client",
    responses=ERRORS,
)
def update_client_payment(
    payment_id: UUID, request: ClientPaymentUpdate, context: AuthenticatedContext
) -> ClientPaymentResponse:
    return finance_service.update_client_payment(context, payment_id, request)


@router.patch(
    "/salary-payments/{payment_id}",
    response_model=SalaryPaymentResponse,
    summary="Edit a salary payment",
    responses=ERRORS,
)
def update_salary_payment(
    payment_id: UUID, request: SalaryPaymentUpdate, context: AuthenticatedContext
) -> SalaryPaymentResponse:
    return finance_service.update_salary_payment(context, payment_id, request)


@router.patch(
    "/manager-payouts/{payment_id}",
    response_model=ManagerPayoutResponse,
    summary="Edit a commission payout",
    responses=ERRORS,
)
def update_payout(
    payment_id: UUID, request: ManagerPayoutUpdate, context: AuthenticatedContext
) -> ManagerPayoutResponse:
    return finance_service.update_payout(context, payment_id, request)


@router.patch(
    "/salary-records/{record_id}",
    response_model=PersonFinanceResponse,
    summary="Correct a salary rate's amount or note",
    responses=ERRORS,
)
def update_salary_record(
    record_id: UUID, request: SalaryRecordUpdate, context: AuthenticatedContext
) -> PersonFinanceResponse:
    return finance_service.update_salary_record(context, record_id, request)


@router.delete(
    "/salary-records/{record_id}",
    response_model=PersonFinanceResponse,
    summary="Delete a salary rate (the previous rate runs until the next one)",
    responses=ERRORS,
)
def delete_salary_record(record_id: UUID, context: AuthenticatedContext) -> PersonFinanceResponse:
    return finance_service.delete_salary_record(context, record_id)


# -- corrections --------------------------------------------------------------------------


@router.delete(
    "/{kind}/{payment_id}",
    status_code=204,
    summary="Delete a wrongly recorded payment (kind: client, salary or payout)",
    responses=ERRORS,
)
def delete_payment(
    kind: Literal["client", "salary", "payout"], payment_id: UUID, context: AuthenticatedContext
) -> Response:
    finance_service.delete_payment(context, kind, payment_id)
    return Response(status_code=204)
