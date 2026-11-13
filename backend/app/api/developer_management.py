from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.developer_management import (
    DeveloperCreateRequest,
    DeveloperListFilters,
    DeveloperListResponse,
    DeveloperResponse,
    DeveloperStatusRequest,
    DeveloperUpdateRequest,
)
from app.schemas.registration import ErrorResponse
from app.services.developer_management_service import developer_management_service

router = APIRouter(prefix="/platform/developers", tags=["developer-management"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Bearer token or session is invalid."},
    403: {"model": ErrorResponse, "description": "Platform Owner role is required."},
    404: {"model": ErrorResponse, "description": "Developer does not exist."},
    409: {"model": ErrorResponse, "description": "Email address already exists."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.post(
    "",
    response_model=DeveloperResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Developer",
    responses=ERRORS,
)
def create_developer(
    request: DeveloperCreateRequest, context: AuthenticatedContext
) -> DeveloperResponse:
    return developer_management_service.create(context, request)


@router.get("", response_model=DeveloperListResponse, summary="List Developers", responses=ERRORS)
def list_developers(
    context: AuthenticatedContext,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    developer_status: Literal["ACTIVE", "INACTIVE"] | None = Query(None, alias="status"),
    created_from: date | None = None,
    created_to: date | None = None,
    sort: Literal["newest", "oldest", "a-z"] = "newest",
) -> DeveloperListResponse:
    return developer_management_service.list(
        context,
        DeveloperListFilters(
            page=page,
            page_size=page_size,
            search=search,
            status=developer_status,
            created_from=created_from,
            created_to=created_to,
            sort=sort,
        ),
    )


@router.get(
    "/{developer_id}", response_model=DeveloperResponse, summary="Get Developer", responses=ERRORS
)
def get_developer(developer_id: UUID, context: AuthenticatedContext) -> DeveloperResponse:
    return developer_management_service.get(context, developer_id)


@router.put(
    "/{developer_id}",
    response_model=DeveloperResponse,
    summary="Update Developer",
    responses=ERRORS,
)
def update_developer(
    developer_id: UUID, request: DeveloperUpdateRequest, context: AuthenticatedContext
) -> DeveloperResponse:
    return developer_management_service.update(context, developer_id, request)


@router.patch(
    "/{developer_id}/status",
    response_model=DeveloperResponse,
    summary="Activate or deactivate Developer",
    responses=ERRORS,
)
def update_developer_status(
    developer_id: UUID, request: DeveloperStatusRequest, context: AuthenticatedContext
) -> DeveloperResponse:
    return developer_management_service.update_status(context, developer_id, request)
