from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.organization import (
    BranchCreate,
    BranchListResponse,
    BranchResponse,
    BranchUpdate,
    DepartmentCreate,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.schemas.registration import ErrorResponse
from app.services.organization_service import organization_service

router = APIRouter(prefix="/company", tags=["organization"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Company Admin permission is required."},
    404: {"model": ErrorResponse, "description": "Tenant-scoped resource was not found."},
    409: {"model": ErrorResponse, "description": "Name or code already exists in this tenant."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_department(
    request: DepartmentCreate, context: AuthenticatedContext
) -> DepartmentResponse:
    return organization_service.create_department(context, request)


@router.get("/departments", response_model=DepartmentListResponse, responses=ERRORS)
def list_departments(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    item_status: Literal["ACTIVE", "INACTIVE"] | None = Query(None, alias="status"),
) -> DepartmentListResponse:
    return organization_service.list_departments(context, search, item_status)


@router.get("/departments/{item_id}", response_model=DepartmentResponse, responses=ERRORS)
def get_department(item_id: UUID, context: AuthenticatedContext) -> DepartmentResponse:
    return organization_service.get_department(context, item_id)


@router.patch("/departments/{item_id}", response_model=DepartmentResponse, responses=ERRORS)
def update_department(
    item_id: UUID, request: DepartmentUpdate, context: AuthenticatedContext
) -> DepartmentResponse:
    return organization_service.update_department(context, item_id, request)


@router.delete("/departments/{item_id}", response_model=DepartmentResponse, responses=ERRORS)
def disable_department(item_id: UUID, context: AuthenticatedContext) -> DepartmentResponse:
    return organization_service.disable_department(context, item_id)


@router.post(
    "/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_branch(request: BranchCreate, context: AuthenticatedContext) -> BranchResponse:
    return organization_service.create_branch(context, request)


@router.get("/branches", response_model=BranchListResponse, responses=ERRORS)
def list_branches(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    item_status: Literal["ACTIVE", "INACTIVE"] | None = Query(None, alias="status"),
) -> BranchListResponse:
    return organization_service.list_branches(context, search, item_status)


@router.get("/branches/{item_id}", response_model=BranchResponse, responses=ERRORS)
def get_branch(item_id: UUID, context: AuthenticatedContext) -> BranchResponse:
    return organization_service.get_branch(context, item_id)


@router.patch("/branches/{item_id}", response_model=BranchResponse, responses=ERRORS)
def update_branch(
    item_id: UUID, request: BranchUpdate, context: AuthenticatedContext
) -> BranchResponse:
    return organization_service.update_branch(context, item_id, request)


@router.delete("/branches/{item_id}", response_model=BranchResponse, responses=ERRORS)
def disable_branch(item_id: UUID, context: AuthenticatedContext) -> BranchResponse:
    return organization_service.disable_branch(context, item_id)
