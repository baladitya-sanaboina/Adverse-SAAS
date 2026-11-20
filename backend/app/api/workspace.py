"""Manager/Employee workspace and Client portal endpoints.

Every response here uses the worker or client schemas, which have no fields for client prices,
margin, revenue or other people's pay.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse, Response

from app.middleware.authentication import AuthenticatedContext
from app.schemas.production import (
    ClientWorkspaceSummaryResponse,
    EmployeeSalaryResponse,
    ManagerEarningsResponse,
    TaskCommentRequest,
    TaskCommentResponse,
    TaskFileResponse,
    TaskFocusResponse,
    TaskStatusChangeRequest,
    WorkerTaskDetailResponse,
    WorkerTaskFilters,
    WorkerTaskListResponse,
    WorkerTaskRole,
    WorkspaceDashboardResponse,
)
from app.schemas.registration import ErrorResponse
from app.services.finance_service import finance_service
from app.services.production_rules import TaskStatus
from app.services.task_service import task_service

router = APIRouter(prefix="/workspace", tags=["team-workspace"])
portal_router = APIRouter(prefix="/client-portal", tags=["client-portal"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "This workspace is not available to your role."},
    404: {"model": ErrorResponse, "description": "The task or file was not found."},
    409: {"model": ErrorResponse, "description": "The change is not allowed in the task's state."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "/dashboard",
    response_model=WorkspaceDashboardResponse,
    summary="My task counts and my own earnings",
    responses=ERRORS,
)
def dashboard(context: AuthenticatedContext) -> WorkspaceDashboardResponse:
    return finance_service.workspace_dashboard(context)


@router.get(
    "/tasks",
    response_model=WorkerTaskListResponse,
    summary="Tasks assigned to me or monitored by me",
    responses=ERRORS,
)
def list_my_tasks(
    context: AuthenticatedContext,
    role: WorkerTaskRole | None = Query(None),
    task_status: TaskStatus | None = Query(None, alias="status"),
    search: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
) -> WorkerTaskListResponse:
    return task_service.list_worker_tasks(
        context,
        WorkerTaskFilters(
            role=role, status=task_status, search=search.strip(), page=page, page_size=page_size
        ),
    )


@router.get(
    "/tasks/focus",
    response_model=TaskFocusResponse,
    summary="My overdue, today, this week and to-review tasks, most urgent first",
)
def my_task_focus(context: AuthenticatedContext) -> TaskFocusResponse:
    return task_service.focus_worker(context)


@router.get(
    "/tasks/{task_id}",
    response_model=WorkerTaskDetailResponse,
    summary="One of my tasks",
    responses=ERRORS,
)
def get_my_task(task_id: UUID, context: AuthenticatedContext) -> WorkerTaskDetailResponse:
    return task_service.get_worker_task(context, task_id)


@router.post(
    "/tasks/{task_id}/status",
    response_model=WorkerTaskDetailResponse,
    summary="Move my task forward (assignee) or change its status (monitor)",
    responses=ERRORS,
)
def change_my_task_status(
    task_id: UUID, request: TaskStatusChangeRequest, context: AuthenticatedContext
) -> WorkerTaskDetailResponse:
    return task_service.change_status_worker(context, task_id, request)


@router.post(
    "/tasks/{task_id}/comments",
    response_model=list[TaskCommentResponse],
    status_code=201,
    summary="Comment on my task",
    responses=ERRORS,
)
def comment_on_my_task(
    task_id: UUID, request: TaskCommentRequest, context: AuthenticatedContext
) -> list[TaskCommentResponse]:
    return task_service.add_comment(context, task_id, request)


@router.post(
    "/tasks/{task_id}/files",
    response_model=list[TaskFileResponse],
    status_code=201,
    summary="Upload finished work for my task",
    responses=ERRORS,
)
def upload_deliverable(
    task_id: UUID, context: AuthenticatedContext, file: UploadFile = File(...)
) -> list[TaskFileResponse]:
    return task_service.upload_file(context, task_id, "DELIVERABLE", file)


@router.get("/tasks/{task_id}/files/{file_id}", summary="Download a file", responses=ERRORS)
def download_task_file(task_id: UUID, file_id: UUID, context: AuthenticatedContext) -> FileResponse:
    path, name, mime = task_service.file_for_download(context, task_id, file_id)
    return FileResponse(path, media_type=mime, filename=name)


@router.delete(
    "/tasks/{task_id}/files/{file_id}",
    response_model=list[TaskFileResponse],
    summary="Remove my own upload while the task is in progress",
    responses=ERRORS,
)
def delete_my_upload(
    task_id: UUID, file_id: UUID, context: AuthenticatedContext
) -> list[TaskFileResponse]:
    return task_service.delete_file(context, task_id, file_id)


@router.get(
    "/earnings/commission",
    response_model=ManagerEarningsResponse,
    summary="My commission (managers)",
    responses=ERRORS,
)
def my_commission(context: AuthenticatedContext) -> ManagerEarningsResponse:
    return finance_service.my_commission(context)


@router.get(
    "/salary/payslips/{month}.pdf",
    summary="My payslip for one month, e.g. 2026-11 (employees)",
    responses=ERRORS,
    response_class=Response,
)
def my_payslip(month: str, context: AuthenticatedContext) -> Response:
    from datetime import date

    from app.services.authentication_service import AuthenticationError

    try:
        first = date.fromisoformat(f"{month[:7]}-01")
    except ValueError as error:
        raise AuthenticationError(422, "MONTH_INVALID", "Use a month like 2026-11.") from error
    content, filename = finance_service.my_payslip(context, first)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/earnings/sheets/{index}/statement.pdf",
    summary="One of my payment sheets as a statement PDF (managers)",
    responses=ERRORS,
    response_class=Response,
)
def my_sheet_statement(index: int, context: AuthenticatedContext) -> Response:
    from app.services.invoice_service import invoice_service

    content, filename = invoice_service.manager_statement_pdf(context, None, index)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/earnings/salary",
    response_model=EmployeeSalaryResponse,
    summary="My salary (employees)",
    responses=ERRORS,
)
def my_salary(context: AuthenticatedContext) -> EmployeeSalaryResponse:
    return finance_service.my_salary(context)


@portal_router.get(
    "/summary",
    response_model=ClientWorkspaceSummaryResponse,
    summary="Client's own work counts, budget and payments (no task list)",
    responses=ERRORS,
)
def client_summary(context: AuthenticatedContext) -> ClientWorkspaceSummaryResponse:
    return finance_service.client_summary(context)
