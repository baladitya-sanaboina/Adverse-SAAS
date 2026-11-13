"""Admin task management endpoints. Only the Company Admin can call these."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.middleware.authentication import AuthenticatedContext
from app.schemas.production import (
    AdminTaskDetailResponse,
    AdminTaskListResponse,
    AssigneeOptionResponse,
    PricingPreviewResponse,
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
)
from app.schemas.registration import ErrorResponse
from app.services.production_rules import TaskStatus
from app.services.task_service import task_service

router = APIRouter(prefix="/company/tasks", tags=["tasks"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Company Admin task permissions are required."},
    404: {
        "model": ErrorResponse,
        "description": "The task, client, service or person was not found.",
    },
    409: {
        "model": ErrorResponse,
        "description": "The change conflicts with the task's current state.",
    },
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get("", response_model=AdminTaskListResponse, summary="List tasks", responses=ERRORS)
def list_tasks(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    task_status: TaskStatus | None = Query(None, alias="status"),
    client_id: UUID | None = Query(None),
    service_id: UUID | None = Query(None),
    assignee_user_id: UUID | None = Query(None),
    overdue_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
) -> AdminTaskListResponse:
    return task_service.list_tasks(
        context,
        TaskListFilters(
            search=search.strip(),
            status=task_status,
            client_id=client_id,
            service_id=service_id,
            assignee_user_id=assignee_user_id,
            overdue_only=overdue_only,
            page=page,
            page_size=page_size,
        ),
    )


@router.post(
    "",
    response_model=TaskWriteResponse,
    status_code=201,
    summary="Create a task with its price snapshot (optionally assigned)",
    responses=ERRORS,
)
def create_task(request: TaskCreateRequest, context: AuthenticatedContext) -> TaskWriteResponse:
    return task_service.create_task(context, request)


@router.get(
    "/assignee-options",
    response_model=list[AssigneeOptionResponse],
    summary="Active managers and employees who can be assigned work",
    responses=ERRORS,
)
def assignee_options(context: AuthenticatedContext) -> list[AssigneeOptionResponse]:
    return task_service.assignee_options(context)


@router.get(
    "/pricing-preview",
    response_model=PricingPreviewResponse,
    summary="Default client rate, manager commission and budget impact before saving",
    responses=ERRORS,
)
def pricing_preview(
    context: AuthenticatedContext,
    client_id: UUID,
    service_id: UUID,
    assignee_user_id: UUID | None = Query(None),
    client_price: Decimal | None = Query(None, ge=0, max_digits=12, decimal_places=2),
) -> PricingPreviewResponse:
    return task_service.pricing_preview(
        context, client_id, service_id, assignee_user_id, client_price
    )


@router.get(
    "/{task_id}", response_model=AdminTaskDetailResponse, summary="Get a task", responses=ERRORS
)
def get_task(task_id: UUID, context: AuthenticatedContext) -> AdminTaskDetailResponse:
    return task_service.get_task(context, task_id)


@router.patch(
    "/{task_id}",
    response_model=AdminTaskDetailResponse,
    summary="Edit title, description, priority or due date",
    responses=ERRORS,
)
def update_task(
    task_id: UUID, request: TaskUpdateRequest, context: AuthenticatedContext
) -> AdminTaskDetailResponse:
    return task_service.update_task(context, task_id, request)


@router.post(
    "/{task_id}/assign",
    response_model=TaskWriteResponse,
    summary="Assign or reassign a task to a manager or employee",
    responses=ERRORS,
)
def assign_task(
    task_id: UUID, request: TaskAssignRequest, context: AuthenticatedContext
) -> TaskWriteResponse:
    return task_service.assign_task(context, task_id, request)


@router.put(
    "/{task_id}/monitor",
    response_model=AdminTaskDetailResponse,
    summary="Set or clear the monitoring manager",
    responses=ERRORS,
)
def set_monitor(
    task_id: UUID, request: TaskMonitorRequest, context: AuthenticatedContext
) -> AdminTaskDetailResponse:
    return task_service.set_monitor(context, task_id, request)


@router.post(
    "/{task_id}/prices",
    response_model=TaskWriteResponse,
    summary="Manually change this task's client price or manager commission",
    responses=ERRORS,
)
def change_prices(
    task_id: UUID, request: TaskPriceChangeRequest, context: AuthenticatedContext
) -> TaskWriteResponse:
    return task_service.change_prices(context, task_id, request)


@router.post(
    "/{task_id}/status",
    response_model=TaskWriteResponse,
    summary="Move a task to any status (Admin)",
    responses=ERRORS,
)
def change_status(
    task_id: UUID, request: TaskStatusChangeRequest, context: AuthenticatedContext
) -> TaskWriteResponse:
    return task_service.change_status_admin(context, task_id, request)


@router.post(
    "/{task_id}/comments",
    response_model=list[TaskCommentResponse],
    status_code=201,
    summary="Add a comment",
    responses=ERRORS,
)
def add_comment(
    task_id: UUID, request: TaskCommentRequest, context: AuthenticatedContext
) -> list[TaskCommentResponse]:
    return task_service.add_comment(context, task_id, request)


@router.post(
    "/{task_id}/files",
    response_model=list[TaskFileResponse],
    status_code=201,
    summary="Upload a reference file or deliverable (stored on this server)",
    responses=ERRORS,
)
def upload_file(
    task_id: UUID,
    context: AuthenticatedContext,
    file: UploadFile = File(...),
    kind: TaskFileKind = Form("REFERENCE"),
) -> list[TaskFileResponse]:
    return task_service.upload_file(context, task_id, kind, file)


@router.get("/{task_id}/files/{file_id}", summary="Download a task file", responses=ERRORS)
def download_file(task_id: UUID, file_id: UUID, context: AuthenticatedContext) -> FileResponse:
    path, name, mime = task_service.file_for_download(context, task_id, file_id)
    return FileResponse(path, media_type=mime, filename=name)


@router.delete(
    "/{task_id}/files/{file_id}",
    response_model=list[TaskFileResponse],
    summary="Delete a task file",
    responses=ERRORS,
)
def delete_file(
    task_id: UUID, file_id: UUID, context: AuthenticatedContext
) -> list[TaskFileResponse]:
    return task_service.delete_file(context, task_id, file_id)
