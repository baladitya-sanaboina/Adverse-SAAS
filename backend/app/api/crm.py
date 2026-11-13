from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.crm import (
    CrmOptionsResponse,
    LeadCreate,
    LeadListFilters,
    LeadListResponse,
    LeadResponse,
    LeadSource,
    LeadStatus,
    LeadUpdate,
    OpportunityCreate,
    OpportunityListFilters,
    OpportunityListResponse,
    OpportunityResponse,
    OpportunityStage,
    OpportunityStatus,
    OpportunityUpdate,
)
from app.schemas.registration import ErrorResponse
from app.services.crm_service import crm_service

router = APIRouter()
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "The corresponding tenant-scoped CRM permission is required.",
    },
    404: {
        "model": ErrorResponse,
        "description": "The tenant-scoped CRM record or relationship was not found.",
    },
    409: {
        "model": ErrorResponse,
        "description": "The lead conflicts with an existing tenant-scoped record.",
    },
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "/crm/options",
    tags=["crm-pipeline"],
    response_model=CrmOptionsResponse,
    summary="List current tenant CRM relationship options",
    description=(
        "Returns active Employee owners and active Clients from the authenticated company only. "
        "The existing CRM VIEW permission is required."
    ),
    responses=ERRORS,
)
def crm_options(context: AuthenticatedContext) -> CrmOptionsResponse:
    return crm_service.options(context)


@router.post(
    "/leads",
    tags=["crm-leads"],
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tenant-scoped lead",
    description=(
        "Creates a potential customer under the company derived from the authenticated JWT. "
        "The optional client and required employee owner must belong to the same tenant."
    ),
    responses=ERRORS,
)
def create_lead(request: LeadCreate, context: AuthenticatedContext) -> LeadResponse:
    return crm_service.create_lead(context, request)


@router.get(
    "/leads",
    tags=["crm-leads"],
    response_model=LeadListResponse,
    summary="List current tenant leads",
    description="Returns only leads owned by the authenticated user's company.",
    responses=ERRORS,
)
def list_leads(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    lead_status: LeadStatus | None = Query(None, alias="status"),
    source: LeadSource | None = None,
    owner_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> LeadListResponse:
    return crm_service.list_leads(
        context,
        LeadListFilters(
            search=search.strip(),
            status=lead_status,
            source=source,
            owner_id=owner_id,
            page=page,
            page_size=page_size,
        ),
    )


@router.get(
    "/leads/{lead_id}",
    tags=["crm-leads"],
    response_model=LeadResponse,
    summary="Get a tenant-scoped lead",
    responses=ERRORS,
)
def get_lead(lead_id: UUID, context: AuthenticatedContext) -> LeadResponse:
    return crm_service.get_lead(context, lead_id)


@router.patch(
    "/leads/{lead_id}",
    tags=["crm-leads"],
    response_model=LeadResponse,
    summary="Update a tenant-scoped lead",
    responses=ERRORS,
)
def update_lead(lead_id: UUID, request: LeadUpdate, context: AuthenticatedContext) -> LeadResponse:
    return crm_service.update_lead(context, lead_id, request)


@router.post(
    "/opportunities",
    tags=["crm-opportunities"],
    response_model=OpportunityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tenant-scoped opportunity",
    description=(
        "Creates a qualified opportunity after validating the Client, optional originating Lead, "
        "and employee owner against the authenticated company. Status is derived from stage."
    ),
    responses=ERRORS,
)
def create_opportunity(
    request: OpportunityCreate, context: AuthenticatedContext
) -> OpportunityResponse:
    return crm_service.create_opportunity(context, request)


@router.get(
    "/opportunities",
    tags=["crm-opportunities"],
    response_model=OpportunityListResponse,
    summary="List current tenant opportunities",
    description="Returns only opportunities owned by the authenticated user's company.",
    responses=ERRORS,
)
def list_opportunities(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    stage: OpportunityStage | None = None,
    opportunity_status: OpportunityStatus | None = Query(None, alias="status"),
    owner_id: UUID | None = None,
    client_id: UUID | None = None,
    lead_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OpportunityListResponse:
    return crm_service.list_opportunities(
        context,
        OpportunityListFilters(
            search=search.strip(),
            stage=stage,
            status=opportunity_status,
            owner_id=owner_id,
            client_id=client_id,
            lead_id=lead_id,
            page=page,
            page_size=page_size,
        ),
    )


@router.get(
    "/opportunities/{opportunity_id}",
    tags=["crm-opportunities"],
    response_model=OpportunityResponse,
    summary="Get a tenant-scoped opportunity",
    responses=ERRORS,
)
def get_opportunity(opportunity_id: UUID, context: AuthenticatedContext) -> OpportunityResponse:
    return crm_service.get_opportunity(context, opportunity_id)


@router.patch(
    "/opportunities/{opportunity_id}",
    tags=["crm-opportunities"],
    response_model=OpportunityResponse,
    summary="Update a tenant-scoped opportunity",
    description="Opportunity OPEN/CLOSED status is derived atomically from its stage.",
    responses=ERRORS,
)
def update_opportunity(
    opportunity_id: UUID,
    request: OpportunityUpdate,
    context: AuthenticatedContext,
) -> OpportunityResponse:
    return crm_service.update_opportunity(context, opportunity_id, request)
