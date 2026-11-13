import hashlib
from datetime import UTC, datetime, timedelta

from app.core.settings import settings
from app.repositories.authentication_repository import (
    AuthenticationRepository,
    AuthenticationUserRecord,
)
from app.schemas.authentication import (
    AuthContext,
    AuthenticatedCompany,
    AuthenticatedUser,
    LoginRequest,
    LogoutResponse,
    RefreshTokenResponse,
    TokenPairResponse,
)
from app.services.jwt_service import (
    TokenClaims,
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.services.password_service import verify_password


class AuthenticationError(Exception):
    def __init__(self, status_code: int, code: str, detail: str):
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthenticationService:
    def __init__(self, repository: AuthenticationRepository | None = None):
        self.repository = repository or AuthenticationRepository()

    @staticmethod
    def _public_user(user: AuthenticationUserRecord) -> AuthenticatedUser:
        company = None
        if user.company_id and user.company_name and user.company_code and user.company_status:
            company = AuthenticatedCompany(
                id=user.company_id,
                name=user.company_name,
                code=user.company_code,
                status=user.company_status,
            )
        return AuthenticatedUser(
            id=user.id,
            name=user.name,
            email=user.email,
            status=user.status,
            role=user.role,
            company=company,
        )

    @staticmethod
    def _enforce_maintenance(role: str) -> None:
        from psycopg_pool import PoolClosed

        from app.repositories.platform_settings_repository import PlatformSettingsRepository

        try:
            platform = PlatformSettingsRepository().get()
        except PoolClosed:
            # Unit services intentionally run without opening the application database pool.
            return
        if platform.maintenance_enabled and role not in platform.maintenance_allowed_roles:
            raise AuthenticationError(503, "MAINTENANCE_MODE", platform.maintenance_message)

    def login(
        self, request: LoginRequest, device_info: str | None, ip_address: str | None = None
    ) -> TokenPairResponse:
        email = str(request.email).lower()
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=settings.account_lock_minutes)
        user = self.repository.find_user_by_email(email)
        if user is None and (
            self.repository.recent_failed_logins(email, ip_address, window_start)
            >= settings.login_max_failed_attempts
        ):
            raise AuthenticationError(
                429, "LOGIN_RATE_LIMITED", "Too many failed login attempts. Please try again later."
            )
        if user and user.locked_until:
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=UTC)
            if locked_until > now:
                raise AuthenticationError(
                    429, "ACCOUNT_LOCKED", "Account is temporarily locked. Please try again later."
                )
            self.repository.clear_login_protection(user.id)
        if user is None or not verify_password(
            request.password.get_secret_value(), user.password_hash
        ):
            protection = None
            if user:
                protection = self.repository.record_failed_login(
                    user.id,
                    settings.login_max_failed_attempts,
                    now + timedelta(minutes=settings.account_lock_minutes),
                )
            self.repository.log_event(
                "LOGIN_FAILED",
                user_id=user.id if user else None,
                email=email,
                company_id=user.company_id if user else None,
                ip_address=ip_address,
            )
            if user and protection and protection.locked_until:
                self.repository.log_event(
                    "ACCOUNT_LOCKED",
                    user_id=user.id,
                    email=email,
                    company_id=user.company_id,
                    ip_address=ip_address,
                    details=f"Locked after {protection.failed_attempts} failed attempts",
                )
                raise AuthenticationError(
                    429, "ACCOUNT_LOCKED", "Account is temporarily locked. Please try again later."
                )
            raise AuthenticationError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
        if user.status != "ACTIVE":
            self.repository.log_event(
                "LOGIN_FAILED",
                user_id=user.id,
                email=user.email,
                details="User inactive",
                company_id=user.company_id,
                ip_address=ip_address,
            )
            if user.status == "PENDING_VERIFICATION":
                raise AuthenticationError(
                    403, "EMAIL_NOT_VERIFIED", "Verify your email address before signing in."
                )
            raise AuthenticationError(403, "USER_INACTIVE", "User account is not active.")
        if user.role_status != "ACTIVE":
            self.repository.log_event(
                "LOGIN_FAILED",
                user_id=user.id,
                email=user.email,
                details="Role inactive",
                company_id=user.company_id,
                ip_address=ip_address,
            )
            raise AuthenticationError(403, "ROLE_INACTIVE", "Assigned role is not active.")
        if user.company_id and user.company_status != "ACTIVE":
            self.repository.log_event(
                "LOGIN_FAILED",
                user_id=user.id,
                email=user.email,
                details="Company inactive",
                company_id=user.company_id,
                ip_address=ip_address,
            )
            raise AuthenticationError(403, "COMPANY_INACTIVE", "Company is not active.")
        self._enforce_maintenance(user.role)
        session_expiry = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expiry_days)
        self.repository.clear_login_protection(user.id)
        session_id = self.repository.create_session(
            user.id, user.company_id, "pending", session_expiry, device_info
        )
        access_token = create_access_token(user.id, user.role, user.company_id, session_id)
        refresh_token = create_refresh_token(user.id, user.role, user.company_id, session_id)
        self.repository.set_refresh_hash(session_id, _token_hash(refresh_token))
        self.repository.log_event(
            "LOGIN_SUCCESS",
            user_id=user.id,
            session_id=session_id,
            email=user.email,
            company_id=user.company_id,
            ip_address=ip_address,
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_expiry_minutes * 60,
            user=self._public_user(user),
        )

    def authenticate_access_token(self, token: str) -> TokenClaims:
        try:
            claims = decode_token(token, "access")
        except TokenValidationError as error:
            raise AuthenticationError(401, "INVALID_TOKEN", str(error)) from error
        if not self.repository.session_is_active(claims.session_id, claims.user_id):
            if self.repository.expire_session(claims.session_id):
                self.repository.log_event(
                    "SESSION_EXPIRED", user_id=claims.user_id, session_id=claims.session_id
                )
            raise AuthenticationError(401, "SESSION_INACTIVE", "Session is inactive or expired.")
        user = self.repository.find_user_by_id(claims.user_id)
        if user is None or user.status != "ACTIVE":
            raise AuthenticationError(401, "USER_INACTIVE", "Authenticated user is not active.")
        if user.role_status != "ACTIVE":
            raise AuthenticationError(403, "ROLE_INACTIVE", "Assigned role is not active.")
        if user.company_id and user.company_status != "ACTIVE":
            raise AuthenticationError(403, "COMPANY_INACTIVE", "Company is not active.")
        if user.role != claims.role or user.company_id != claims.company_id:
            raise AuthenticationError(401, "TOKEN_CONTEXT_CHANGED", "User context has changed.")
        self._enforce_maintenance(user.role)
        self.repository.touch_session(claims.session_id)
        return claims

    def refresh_access_token(
        self, token: str, ip_address: str | None = None
    ) -> RefreshTokenResponse:
        try:
            claims = decode_token(token, "refresh")
        except TokenValidationError as error:
            raise AuthenticationError(401, "INVALID_REFRESH_TOKEN", str(error)) from error
        access_token = create_access_token(
            claims.user_id, claims.role, claims.company_id, claims.session_id
        )
        refresh_token = create_refresh_token(
            claims.user_id, claims.role, claims.company_id, claims.session_id
        )
        if not self.repository.rotate_refresh_token(
            claims.session_id,
            claims.user_id,
            _token_hash(token),
            _token_hash(refresh_token),
        ):
            self.repository.log_event(
                "TOKEN_REVOKED",
                user_id=claims.user_id,
                session_id=claims.session_id,
                details="Rejected refresh token reuse or inactive session",
            )
            raise AuthenticationError(
                401, "INVALID_REFRESH_TOKEN", "Refresh token is expired, revoked, or already used."
            )
        self.repository.log_event(
            "REFRESH_USED",
            user_id=claims.user_id,
            session_id=claims.session_id,
            company_id=claims.company_id,
            ip_address=ip_address,
        )
        return RefreshTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_expiry_minutes * 60,
        )

    def logout(self, context: AuthContext, ip_address: str | None = None) -> LogoutResponse:
        if not self.repository.revoke_session(context.session_id, context.user_id):
            raise AuthenticationError(401, "SESSION_INACTIVE", "Session is already inactive.")
        self.repository.log_event(
            "LOGOUT",
            user_id=context.user_id,
            session_id=context.session_id,
            company_id=context.company_id,
            ip_address=ip_address,
        )
        self.repository.log_event(
            "TOKEN_REVOKED", user_id=context.user_id, session_id=context.session_id
        )
        return LogoutResponse()

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


authentication_service = AuthenticationService()
