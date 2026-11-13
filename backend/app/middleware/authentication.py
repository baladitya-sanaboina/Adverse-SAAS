from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.authentication import AuthContext
from app.services.authentication_service import authentication_service

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token returned by /auth/login")


def require_authenticated_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        from app.services.authentication_service import AuthenticationError

        raise AuthenticationError(
            401, "AUTHENTICATION_REQUIRED", "Bearer access token is required."
        )
    claims = authentication_service.authenticate_access_token(credentials.credentials)
    context = AuthContext(
        user_id=claims.user_id,
        role=claims.role,
        company_id=claims.company_id,
        user_type=claims.user_type,
        session_id=claims.session_id,
        issued_at=claims.issued_at,
        expires_at=claims.expires_at,
    )
    request.state.auth = context
    return context


AuthenticatedContext = Annotated[AuthContext, Depends(require_authenticated_user)]
