from typing import Annotated, Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.core.constants import TENANT_HEADER
from app.middleware.authentication import AuthenticatedContext
from app.services.authentication_service import AuthenticationError

router = APIRouter(prefix="/tenant", tags=["tenant"])


class TenantContextResponse(BaseModel):
    id: str
    name: str
    code: str
    subscription_plan: str
    status: Literal["ACTIVE"]
    contact_email: str | None


@router.get(
    "/context",
    response_model=TenantContextResponse,
    summary="Get current tenant context",
    description=(
        "Returns the active company resolved by tenant middleware from the "
        f"{TENANT_HEADER} request header after matching it to the authenticated JWT company."
    ),
    operation_id="get_tenant_context",
    responses={
        401: {"description": "Authentication is required."},
        400: {"description": "Tenant header is missing or invalid."},
        403: {"description": "Company is unavailable or does not match the JWT tenant."},
        404: {"description": "Company does not exist."},
    },
)
def tenant_context(
    request: Request,
    context: AuthenticatedContext,
    _: Annotated[str, Header(alias=TENANT_HEADER)],
) -> TenantContextResponse:
    tenant = request.state.tenant
    if context.company_id is None or str(context.company_id) != tenant.id:
        raise AuthenticationError(
            403,
            "TENANT_CONTEXT_MISMATCH",
            "The requested tenant does not match the authenticated company.",
        )
    return TenantContextResponse(
        id=tenant.id,
        name=tenant.name,
        code=tenant.code,
        subscription_plan=tenant.subscription_plan,
        status=tenant.status,
        contact_email=tenant.contact_email,
    )
