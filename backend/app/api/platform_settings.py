from typing import Any, Literal

from fastapi import APIRouter, File, UploadFile, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.platform_settings import (
    ActionResponse,
    BrandingAssetResponse,
    MaintenanceSettingsUpdate,
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
    PublicMaintenanceResponse,
    SmtpSettingsUpdate,
    TestEmailRequest,
)
from app.schemas.registration import ErrorResponse
from app.services.platform_settings_service import platform_settings_service

router = APIRouter(tags=["platform-settings"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Platform Owner access is required."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
    502: {"model": ErrorResponse, "description": "SMTP connection failed."},
}


@router.get(
    "/platform/settings/maintenance/status",
    response_model=PublicMaintenanceResponse,
    summary="Get public maintenance status",
    operation_id="get_public_maintenance_status",
)
def maintenance_status() -> PublicMaintenanceResponse:
    return platform_settings_service.public_maintenance()


@router.get(
    "/platform/settings",
    response_model=PlatformSettingsResponse,
    summary="Get global platform settings",
    operation_id="get_platform_settings",
    responses=ERRORS,
)
def get_settings(context: AuthenticatedContext) -> PlatformSettingsResponse:
    return platform_settings_service.get(context)


@router.put(
    "/platform/settings",
    response_model=PlatformSettingsResponse,
    summary="Update general platform defaults",
    operation_id="update_platform_settings",
    responses=ERRORS,
)
def update_settings(
    request: PlatformSettingsUpdate, context: AuthenticatedContext
) -> PlatformSettingsResponse:
    return platform_settings_service.update(context, request)


@router.put(
    "/platform/settings/smtp",
    response_model=PlatformSettingsResponse,
    summary="Update global SMTP configuration",
    operation_id="update_platform_smtp_settings",
    responses=ERRORS,
)
def update_smtp(
    request: SmtpSettingsUpdate, context: AuthenticatedContext
) -> PlatformSettingsResponse:
    return platform_settings_service.update_smtp(context, request)


@router.post(
    "/platform/settings/test-email",
    response_model=ActionResponse,
    summary="Send SMTP test email",
    operation_id="test_platform_smtp_settings",
    responses=ERRORS,
)
def test_smtp(request: TestEmailRequest, context: AuthenticatedContext) -> ActionResponse:
    return platform_settings_service.send_test_email(context, str(request.email))


@router.put(
    "/platform/settings/maintenance",
    response_model=PlatformSettingsResponse,
    summary="Update maintenance mode",
    operation_id="update_platform_maintenance_settings",
    responses=ERRORS,
)
def update_maintenance(
    request: MaintenanceSettingsUpdate, context: AuthenticatedContext
) -> PlatformSettingsResponse:
    return platform_settings_service.update_maintenance(context, request)


@router.post(
    "/platform/settings/branding/{asset}",
    response_model=BrandingAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload platform logo or favicon",
    operation_id="upload_platform_branding_asset",
    responses=ERRORS,
)
async def upload_branding_asset(
    asset: Literal["logo", "favicon"],
    context: AuthenticatedContext,
    file: UploadFile = File(...),
) -> BrandingAssetResponse:
    return await platform_settings_service.upload(context, asset, file)
