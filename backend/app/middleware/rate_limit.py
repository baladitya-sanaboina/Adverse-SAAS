"""A ceiling on changes per signed-in session (security checklist, 2026-11-15).

Sign-in, sign-up, password reset and email codes already have their own limits (see the
authentication, password recovery and email verification services). This adds one more for
everything else that changes data (POST, PUT, PATCH, DELETE): at most WRITE_LIMIT a minute per
signed-in session, keyed by a hash of its bearer token. Reads are not limited, and requests
without a token are left to those per-flow limits (they all come through the apps' servers, so
an address would lump every user together). If Redis cannot be reached the request goes
through: the limiter must never take the app down.
"""

from __future__ import annotations

import hashlib
import logging
import time

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.settings import settings

logger = logging.getLogger(__name__)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# A busy person (chat, a call with several people sending network candidates, quick edits)
# stays far below this; a script hammering the API does not.
WRITE_LIMIT = 300
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limit: int = WRITE_LIMIT, redis: Redis | None = None) -> None:
        super().__init__(app)
        self.limit = limit
        self._redis = redis

    def _client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(
                settings.redis_url, socket_connect_timeout=1, socket_timeout=1
            )
        return self._redis

    @staticmethod
    def session_key(request: Request) -> str | None:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer ") or len(header) <= 7:
            return None
        return hashlib.sha256(header[7:].strip().encode()).hexdigest()[:40]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in WRITE_METHODS:
            return await call_next(request)
        session = self.session_key(request)
        if session is None:
            return await call_next(request)
        window = int(time.time() // WINDOW_SECONDS)
        key = f"ratelimit:write:{session}:{window}"
        try:
            client = self._client()
            count = int(await client.incr(key))
            if count == 1:
                await client.expire(key, WINDOW_SECONDS + 10)
        except Exception:  # noqa: BLE001 - fail open when Redis is down
            logger.warning("Rate limit check skipped (Redis unavailable)", exc_info=True)
            return await call_next(request)
        if count > self.limit:
            retry = WINDOW_SECONDS - int(time.time()) % WINDOW_SECONDS
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMITED",
                    "detail": "Too many changes in a short time. Wait a moment and try again.",
                    "errors": None,
                },
                headers={"Retry-After": str(retry)},
            )
        return await call_next(request)
