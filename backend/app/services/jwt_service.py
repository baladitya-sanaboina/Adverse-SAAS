from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from app.core.settings import settings

ALGORITHM = "HS256"


class TokenValidationError(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    role: str
    company_id: UUID | None
    user_type: str
    session_id: UUID
    issued_at: datetime
    expires_at: datetime
    token_type: Literal["access", "refresh"]


def _encode(
    *,
    user_id: UUID,
    role: str,
    company_id: UUID | None,
    session_id: UUID,
    token_type: Literal["access", "refresh"],
    expires_at: datetime,
) -> str:
    issued_at = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "company_id": str(company_id) if company_id else None,
        "user_type": "company" if company_id else "platform",
        "session_id": str(session_id),
        "jti": str(uuid4()),
        "token_type": token_type,
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def create_access_token(user_id: UUID, role: str, company_id: UUID | None, session_id: UUID) -> str:
    return _encode(
        user_id=user_id,
        role=role,
        company_id=company_id,
        session_id=session_id,
        token_type="access",
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.jwt_expiry_minutes),
    )


def create_refresh_token(
    user_id: UUID, role: str, company_id: UUID | None, session_id: UUID
) -> str:
    return _encode(
        user_id=user_id,
        role=role,
        company_id=company_id,
        session_id=session_id,
        token_type="refresh",
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expiry_days),
    )


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> TokenClaims:
    try:
        payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=[ALGORITHM])
        if payload.get("token_type") != expected_type:
            raise TokenValidationError("Invalid token type.")
        return TokenClaims(
            user_id=UUID(payload["sub"]),
            role=str(payload["role"]),
            company_id=UUID(payload["company_id"]) if payload.get("company_id") else None,
            user_type=str(payload["user_type"]),
            session_id=UUID(payload["session_id"]),
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
            token_type=expected_type,
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise TokenValidationError("Token is invalid or expired.") from error
