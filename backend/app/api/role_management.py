from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.registration import ErrorResponse
from app.schemas.role_management import (
    PermissionCatalogResponse,
    RoleCreate,
    RoleDetailResponse,
    RoleListResponse,
    RoleUpdate,
)
from app.services.role_management_service import role_management_service

router = APIRouter(prefix="/company/roles", tags=["company-role-management"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Company Admin role permission is required."},
    404: {"model": ErrorResponse, "description": "Tenant-scoped role was not found."},
    409: {
        "model": ErrorResponse,
        "description": "Duplicate name or assigned-role deletion conflict.",
    },
    422: {"model": ErrorResponse, "description": "Role or permission validation failed."},
}


@router.get("/permissions", response_model=PermissionCatalogResponse, responses=ERRORS)
def permission_catalog(context: AuthenticatedContext) -> PermissionCatalogResponse:
    return role_management_service.permission_catalog(context)


@router.post(
    "", response_model=RoleDetailResponse, status_code=status.HTTP_201_CREATED, responses=ERRORS
)
def create_role(request: RoleCreate, context: AuthenticatedContext) -> RoleDetailResponse:
    return role_management_service.create(context, request)


@router.get("", response_model=RoleListResponse, responses=ERRORS)
def list_roles(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    role_status: Literal["ACTIVE", "INACTIVE"] | None = Query(None, alias="status"),
) -> RoleListResponse:
    return role_management_service.list_roles(context, search, role_status)


@router.get("/{role_id}", response_model=RoleDetailResponse, responses=ERRORS)
def get_role(role_id: UUID, context: AuthenticatedContext) -> RoleDetailResponse:
    return role_management_service.get_role(context, role_id)


@router.patch("/{role_id}", response_model=RoleDetailResponse, responses=ERRORS)
def update_role(
    role_id: UUID, request: RoleUpdate, context: AuthenticatedContext
) -> RoleDetailResponse:
    return role_management_service.update(context, role_id, request)


@router.delete("/{role_id}", response_model=RoleDetailResponse, responses=ERRORS)
def delete_role(role_id: UUID, context: AuthenticatedContext) -> RoleDetailResponse:
    return role_management_service.delete(context, role_id)
