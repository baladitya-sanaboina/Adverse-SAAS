from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.constants import ERROR_TENANT_REQUIRED, TENANT_HEADER
from app.services.tenant_service import (
    InvalidTenantIdentifier,
    TenantNotFound,
    TenantUnavailable,
    tenant_service,
)


class TenantContextMiddleware(BaseHTTPMiddleware):
    header_name = TENANT_HEADER

    def __init__(
        self,
        app: ASGIApp,
        exempt_paths: set[str] | None = None,
        exempt_path_prefixes: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.exempt_paths = exempt_paths or set()
        self.exempt_path_prefixes = exempt_path_prefixes or set()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in self.exempt_paths or any(
            request.url.path.startswith(prefix) for prefix in self.exempt_path_prefixes
        ):
            request.state.tenant = None
            return await call_next(request)

        company_id = request.headers.get(self.header_name)
        if not company_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": ERROR_TENANT_REQUIRED},
            )

        try:
            request.state.tenant = await run_in_threadpool(
                tenant_service.resolve_tenant, company_id
            )
        except InvalidTenantIdentifier as error:
            return JSONResponse(status_code=400, content={"detail": str(error)})
        except TenantNotFound as error:
            return JSONResponse(status_code=404, content={"detail": str(error)})
        except TenantUnavailable as error:
            return JSONResponse(status_code=403, content={"detail": str(error)})

        return await call_next(request)
