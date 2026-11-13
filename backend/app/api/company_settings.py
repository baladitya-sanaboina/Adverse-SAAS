from typing import Any, Literal

from fastapi import APIRouter, File, UploadFile, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.company_settings import (
    BrandingAssetResponse,
    CompanyBrandingResponse,
    CompanyPreferencesUpdate,
    CompanySettingsResponse,
    CompanySettingsUpdate,
)
from app.schemas.registration import ErrorResponse
from app.services.company_settings_service import company_settings_service

router = APIRouter(tags=["company-settings"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Company Admin access is required."},
    404: {"model": ErrorResponse, "description": "Company settings were not found."},
    409: {"model": ErrorResponse, "description": "A unique company value is already in use."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "/company/settings",
    response_model=CompanySettingsResponse,
    summary="Get current tenant settings",
    operation_id="get_company_settings",
    responses=ERRORS,
)
def get_settings(context: AuthenticatedContext) -> CompanySettingsResponse:
    return company_settings_service.get(context)


@router.get(
    "/company/branding",
    response_model=CompanyBrandingResponse,
    summary="Get current tenant visual identity",
    operation_id="get_company_branding",
    responses=ERRORS,
)
def get_branding(context: AuthenticatedContext) -> CompanyBrandingResponse:
    return company_settings_service.branding(context)


@router.put(
    "/company/settings",
    response_model=CompanySettingsResponse,
    summary="Update current tenant settings",
    operation_id="update_company_settings",
    responses=ERRORS,
)
def update_settings(
    request: CompanySettingsUpdate, context: AuthenticatedContext
) -> CompanySettingsResponse:
    return company_settings_service.update(context, request)


@router.put(
    "/company/settings/preferences",
    response_model=CompanySettingsResponse,
    summary="Update tenant preferences and notifications",
    operation_id="update_company_preferences",
    responses=ERRORS,
)
def update_preferences(
    request: CompanyPreferencesUpdate, context: AuthenticatedContext
) -> CompanySettingsResponse:
    return company_settings_service.update_preferences(context, request)


@router.post(
    "/company/settings/branding/{asset}",
    response_model=BrandingAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload tenant logo or favicon",
    operation_id="upload_company_branding_asset",
    responses=ERRORS,
)
async def upload_branding(
    asset: Literal["logo", "favicon"], context: AuthenticatedContext, file: UploadFile = File(...)
) -> BrandingAssetResponse:
    return await company_settings_service.upload(context, asset, file)


@router.delete(
    "/company/settings/branding/{asset}",
    response_model=BrandingAssetResponse,
    summary="Remove tenant logo or favicon",
    operation_id="remove_company_branding_asset",
    responses=ERRORS,
)
def remove_branding(
    asset: Literal["logo", "favicon"], context: AuthenticatedContext
) -> BrandingAssetResponse:
    return company_settings_service.remove(context, asset)
