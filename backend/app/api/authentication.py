from typing import Any

from fastapi import APIRouter, Header, Query, Request

from app.core.settings import settings
from app.middleware.authentication import AuthenticatedContext
from app.schemas.authentication import (
    AuthContext,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SignupRequest,
    SignupResponse,
    TokenPairResponse,
    VerificationEmailRequest,
    VerificationEmailResponse,
    VerifyEmailOtpRequest,
    VerifyEmailResponse,
)
from app.schemas.registration import ErrorResponse
from app.services.authentication_service import AuthenticationError, authentication_service
from app.services.email_verification_service import email_verification_service
from app.services.password_recovery_service import password_recovery_service
from app.services.public_signup_service import public_signup_service

router = APIRouter(prefix="/auth", tags=["authentication"])
ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Request token is invalid, expired, or used."},
    401: {"model": ErrorResponse, "description": "Credentials or token are invalid."},
    403: {"model": ErrorResponse, "description": "User or company is inactive."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
    429: {"model": ErrorResponse, "description": "Login is temporarily rate limited or locked."},
}


@router.post(
    "/signup",
    response_model=SignupResponse,
    summary="Create a new role-based account",
    description="Creates a pending Admin, Manager, Employee, or Client account and sends a verification OTP.",
    status_code=201,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: ERRORS[422]},
)
def signup(request: SignupRequest) -> SignupResponse:
    if not settings.public_signup_enabled:
        raise AuthenticationError(
            403, "PUBLIC_SIGNUP_DISABLED", "Sign up is currently unavailable."
        )

    return public_signup_service.signup(request)


@router.post(
    "/send-verification-email",
    response_model=VerificationEmailResponse,
    summary="Send verification email",
    description="Creates a single-use verification OTP for a pending account.",
    responses={
        403: ERRORS[403],
        409: {"model": ErrorResponse},
        422: ERRORS[422],
        429: {"model": ErrorResponse},
    },
)
def send_verification_email(request: VerificationEmailRequest) -> VerificationEmailResponse:
    return email_verification_service.send(str(request.email))


@router.post(
    "/resend-verification",
    response_model=VerificationEmailResponse,
    summary="Resend verification email",
    description="Invalidates the previous token and sends a new rate-limited verification link.",
    responses={
        403: ERRORS[403],
        409: {"model": ErrorResponse},
        422: ERRORS[422],
        429: {"model": ErrorResponse},
    },
)
def resend_verification(request: VerificationEmailRequest) -> VerificationEmailResponse:
    return email_verification_service.send(str(request.email))


@router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify email and activate account",
    description="Consumes a valid one-time verification token and activates the pending account.",
    responses={400: ERRORS[400], 403: ERRORS[403], 409: {"model": ErrorResponse}, 422: ERRORS[422]},
)
def verify_email(token: str = Query(min_length=32, max_length=512)) -> VerifyEmailResponse:
    return email_verification_service.verify(token)


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify email with OTP",
    description="Consumes a valid one-time verification code and activates the pending account.",
    responses={400: ERRORS[400], 403: ERRORS[403], 409: {"model": ErrorResponse}, 422: ERRORS[422]},
)
def verify_email_otp(request: VerifyEmailOtpRequest) -> VerifyEmailResponse:
    return email_verification_service.verify_otp(str(request.email), request.otp)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request password reset",
    description="Returns a generic response and triggers reset-code delivery only for an eligible active account.",
    responses={422: ERRORS[422]},
)
def forgot_password(request: ForgotPasswordRequest) -> ForgotPasswordResponse:
    return password_recovery_service.forgot_password(request)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset password",
    description="Consumes a single-use reset token or OTP, updates the password hash, and revokes all active sessions.",
    responses={400: ERRORS[400], 403: ERRORS[403], 422: ERRORS[422]},
)
def reset_password(request: ResetPasswordRequest) -> ResetPasswordResponse:
    return password_recovery_service.reset_password(request)


@router.post(
    "/login",
    response_model=TokenPairResponse,
    summary="Login",
    description=(
        "Verifies credentials, creates a session, and returns JWT access and refresh tokens. "
        "Five consecutive failed attempts temporarily lock a known account for 15 minutes; "
        "repeated unknown-account attempts are rate limited."
    ),
    responses=ERRORS,
)
def login(
    payload: LoginRequest,
    request: Request,
    user_agent: str | None = Header(default=None),
) -> TokenPairResponse:
    return authentication_service.login(
        payload, user_agent, request.client.host if request.client else None
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="Rotate refresh token",
    description="Validates an active refresh token and rotates it while issuing new access and refresh tokens.",
    responses={401: ERRORS[401], 422: ERRORS[422]},
)
def refresh(payload: RefreshTokenRequest, request: Request) -> RefreshTokenResponse:
    return authentication_service.refresh_access_token(
        payload.refresh_token, request.client.host if request.client else None
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout current session",
    description="Revokes the authenticated session and prevents both access and refresh token reuse.",
    responses={401: ERRORS[401]},
)
def logout(context: AuthenticatedContext, request: Request) -> LogoutResponse:
    return authentication_service.logout(context, request.client.host if request.client else None)


@router.get(
    "/me",
    response_model=AuthContext,
    summary="Get authenticated context",
    description="Protected foundation route. Select Authorize in Swagger and provide the access token.",
    responses={401: ERRORS[401]},
)
def authenticated_context(context: AuthenticatedContext) -> AuthContext:
    return context
