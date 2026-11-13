from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListFilters,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.schemas.registration import ErrorResponse
from app.services.employee_service import employee_service

router = APIRouter(prefix="/company/employees", tags=["employee-profiles"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "The corresponding tenant-scoped Employees permission is required.",
    },
    404: {
        "model": ErrorResponse,
        "description": "The tenant-scoped employee or selected relationship was not found.",
    },
    409: {
        "model": ErrorResponse,
        "description": "The user already has a profile or employee code already exists.",
    },
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an employee profile",
    description=(
        "Creates a tenant-bound business profile for an existing company user and synchronizes "
        "the selected Department, Branch, and existing RBAC Role onto that user atomically."
    ),
    responses=ERRORS,
)
def create_employee(request: EmployeeCreate, context: AuthenticatedContext) -> EmployeeResponse:
    return employee_service.create(context, request)


@router.get(
    "",
    response_model=EmployeeListResponse,
    summary="List current tenant employee profiles",
    description="Returns employee profiles only for the company derived from the authenticated JWT.",
    responses=ERRORS,
)
def list_employees(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    employee_status: Literal["PENDING", "ACTIVE", "INACTIVE"] | None = Query(None, alias="status"),
    department_id: UUID | None = None,
    branch_id: UUID | None = None,
    role_id: UUID | None = None,
) -> EmployeeListResponse:
    return employee_service.list(
        context,
        EmployeeListFilters(
            search=search.strip(),
            page=page,
            page_size=page_size,
            status=employee_status,
            department_id=department_id,
            branch_id=branch_id,
            role_id=role_id,
        ),
    )


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get a tenant-scoped employee profile",
    responses=ERRORS,
)
def get_employee(employee_id: UUID, context: AuthenticatedContext) -> EmployeeResponse:
    return employee_service.get(context, employee_id)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Update an employee profile",
    description=(
        "Updates employee lifecycle or organization relationships. Role, Department, and Branch "
        "changes remain synchronized with the existing User/RBAC assignment."
    ),
    responses=ERRORS,
)
def update_employee(
    employee_id: UUID, request: EmployeeUpdate, context: AuthenticatedContext
) -> EmployeeResponse:
    return employee_service.update(context, employee_id, request)
