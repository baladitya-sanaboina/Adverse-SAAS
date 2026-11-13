from typing import Any

from fastapi import APIRouter, File, UploadFile

from app.middleware.authentication import AuthenticatedContext
from app.schemas.profile import (
    ChangePasswordRequest,
    ProfileImageResponse,
    ProfileMessageResponse,
    ProfileResponse,
    UpdateProfileRequest,
)
from app.schemas.registration import ErrorResponse
from app.services.profile_service import MAX_IMAGE_SIZE, profile_service

router = APIRouter(prefix="/profile", tags=["profile"])
ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("", response_model=ProfileResponse, summary="Get own profile", responses=ERRORS)
def get_profile(context: AuthenticatedContext) -> ProfileResponse:
    return profile_service.get_profile(context)


@router.put(
    "",
    response_model=ProfileResponse,
    summary="Update own profile and preferences",
    responses=ERRORS,
)
def update_profile(request: UpdateProfileRequest, context: AuthenticatedContext) -> ProfileResponse:
    return profile_service.update_profile(context, request)


@router.put(
    "/change-password",
    response_model=ProfileMessageResponse,
    summary="Change own password",
    responses=ERRORS,
)
def change_password(
    request: ChangePasswordRequest, context: AuthenticatedContext
) -> ProfileMessageResponse:
    return profile_service.change_password(context, request)


@router.post(
    "/image",
    response_model=ProfileImageResponse,
    summary="Upload own profile image",
    responses=ERRORS,
)
async def upload_profile_image(
    context: AuthenticatedContext, image: UploadFile = File()
) -> ProfileImageResponse:
    return profile_service.upload_image(
        context, image.content_type or "", await image.read(MAX_IMAGE_SIZE + 1)
    )
