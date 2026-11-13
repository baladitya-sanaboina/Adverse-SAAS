from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.middleware.authentication import AuthenticatedContext
from app.middleware.permissions import require_permission
from app.schemas.registration import (
    CreateClientRequest,
    CreateCompanyAdminRequest,
    CreateCompanyOnboardingRequest,
    CreateDeveloperRequest,
    CreateEmployeeRequest,
    ErrorResponse,
    RegisteredCompanyOnboardingResponse,
    RegisteredCompanyResponse,
    RegisteredUserResponse,
)
from app.services.registration_service import registration_service

router = APIRouter(prefix="/registration", tags=["registration"])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "Creator or company is not allowed."},
    404: {"model": ErrorResponse, "description": "Creator or company does not exist."},
    409: {"model": ErrorResponse, "description": "Email or company code already exists."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "/developers",
    response_model=list[RegisteredUserResponse],
    summary="List Developers",
    description="Lists Developer accounts for an authenticated Platform Owner.",
    operation_id="list_developers",
    responses=ERROR_RESPONSES,
)
def list_developers(context: AuthenticatedContext) -> list[RegisteredUserResponse]:
    return [
        RegisteredUserResponse(**user.__dict__)
        for user in registration_service.list_developers(context.user_id)
    ]


@router.post(
    "/developers",
    response_model=RegisteredUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Developer",
    description="Allows an active Platform Owner to create an active Developer account.",
    operation_id="create_developer",
    responses=ERROR_RESPONSES,
)
def create_developer(
    request: CreateDeveloperRequest, context: AuthenticatedContext
) -> RegisteredUserResponse:
    user = registration_service.create_developer(request, context.user_id)
    return RegisteredUserResponse(**user.__dict__)


@router.post(
    "/companies",
    response_model=RegisteredCompanyOnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Company and Default Admin",
    description="Atomically creates an active tenant company and its default Company Admin.",
    operation_id="create_company",
    responses=ERROR_RESPONSES,
)
def create_company(
    request: CreateCompanyOnboardingRequest,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("COMPANIES", "CREATE"))],
) -> RegisteredCompanyOnboardingResponse:
    company, admin = registration_service.onboard_company(request, context.user_id)
    return RegisteredCompanyOnboardingResponse(
        company=RegisteredCompanyResponse(**company.__dict__),
        admin=RegisteredUserResponse(**admin.__dict__),
    )


@router.get(
    "/companies",
    response_model=list[RegisteredCompanyResponse],
    summary="List Companies",
    description="Lists companies created by the authenticated Developer.",
    operation_id="list_companies",
    responses=ERROR_RESPONSES,
)
def list_companies(
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("COMPANIES", "VIEW"))],
) -> list[RegisteredCompanyResponse]:
    return [
        RegisteredCompanyResponse(**company.__dict__)
        for company in registration_service.list_companies(context.user_id)
    ]


@router.post(
    "/company-admins",
    response_model=RegisteredUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Company Admin",
    description="Allows an active Developer to create a Company Admin for an active company.",
    operation_id="create_company_admin",
    responses=ERROR_RESPONSES,
)
def create_company_admin(
    request: CreateCompanyAdminRequest,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("COMPANIES", "CREATE"))],
) -> RegisteredUserResponse:
    user = registration_service.create_company_admin(request, context.user_id)
    return RegisteredUserResponse(**user.__dict__)


@router.post(
    "/employees",
    response_model=RegisteredUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Employee",
    description="Allows a Company Admin to create an Employee inside the same active company.",
    operation_id="create_employee",
    responses=ERROR_RESPONSES,
)
def create_employee(
    request: CreateEmployeeRequest, context: AuthenticatedContext
) -> RegisteredUserResponse:
    if context.company_id is None:
        from app.services.registration_service import RegistrationError

        raise RegistrationError(403, "COMPANY_CONTEXT_REQUIRED", "Company context is required.")
    user = registration_service.create_employee(request, context.user_id, context.company_id)
    return RegisteredUserResponse(**user.__dict__)


@router.get(
    "/employees",
    response_model=list[RegisteredUserResponse],
    summary="List Employees",
    description="Lists Employees inside the authenticated Company Admin's company.",
    operation_id="list_employees",
    responses=ERROR_RESPONSES,
)
def list_employees(context: AuthenticatedContext) -> list[RegisteredUserResponse]:
    if context.company_id is None:
        from app.services.registration_service import RegistrationError

        raise RegistrationError(403, "COMPANY_CONTEXT_REQUIRED", "Company context is required.")
    return [
        RegisteredUserResponse(**user.__dict__)
        for user in registration_service.list_employees(context.user_id, context.company_id)
    ]


@router.post(
    "/clients",
    response_model=RegisteredUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Client",
    description="Allows a Company Admin to create a Client inside the same active company.",
    operation_id="create_client",
    responses=ERROR_RESPONSES,
)
def create_client(
    request: CreateClientRequest, context: AuthenticatedContext
) -> RegisteredUserResponse:
    if context.company_id is None:
        from app.services.registration_service import RegistrationError

        raise RegistrationError(403, "COMPANY_CONTEXT_REQUIRED", "Company context is required.")
    user = registration_service.create_client(request, context.user_id, context.company_id)
    return RegisteredUserResponse(**user.__dict__)


@router.get(
    "/clients",
    response_model=list[RegisteredUserResponse],
    summary="List Clients",
    description="Lists Clients inside the authenticated Company Admin's company.",
    operation_id="list_clients",
    responses=ERROR_RESPONSES,
)
def list_clients(context: AuthenticatedContext) -> list[RegisteredUserResponse]:
    if context.company_id is None:
        from app.services.registration_service import RegistrationError

        raise RegistrationError(403, "COMPANY_CONTEXT_REQUIRED", "Company context is required.")
    return [
        RegisteredUserResponse(**user.__dict__)
        for user in registration_service.list_clients(context.user_id, context.company_id)
    ]
