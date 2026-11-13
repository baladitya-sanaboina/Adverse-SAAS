from math import ceil
from uuid import UUID

from app.repositories.developer_management_repository import (
    DeveloperManagementRepository,
    DeveloperRecord,
    PermissionRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.developer_management import (
    DeveloperAuditResponse,
    DeveloperCreateRequest,
    DeveloperListFilters,
    DeveloperListResponse,
    DeveloperPermission,
    DeveloperResponse,
    DeveloperStatusRequest,
    DeveloperUpdateRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.password_service import hash_password


class DeveloperManagementService:
    def __init__(self, repository: DeveloperManagementRepository | None = None):
        self.repository = repository or DeveloperManagementRepository()

    def _authorize(self, context: AuthContext) -> None:
        if context.role != "PLATFORM_OWNER" or not self.repository.actor_is_platform_owner(
            context.user_id
        ):
            raise AuthenticationError(
                403, "PLATFORM_OWNER_REQUIRED", "Platform Owner access is required."
            )

    @staticmethod
    def _permission_records(permissions: list[DeveloperPermission]) -> tuple[PermissionRecord, ...]:
        return tuple(
            dict.fromkeys(PermissionRecord(item.module, item.action) for item in permissions)
        )

    def _validate_permissions(self, permissions: tuple[PermissionRecord, ...]) -> None:
        catalog = set(self.repository.permission_catalog())
        invalid = [item for item in permissions if item not in catalog]
        if invalid:
            raise AuthenticationError(
                422,
                "INVALID_PERMISSION",
                f"Unknown permission {invalid[0].module}:{invalid[0].action}.",
            )

    def _response(self, record: DeveloperRecord, include_audits: bool = False) -> DeveloperResponse:
        return DeveloperResponse(
            **record.__dict__,
            permissions=[
                DeveloperPermission(**item.__dict__)
                for item in self.repository.permissions_for(record.id)
            ],
            audits=(
                [
                    DeveloperAuditResponse(**item.__dict__)
                    for item in self.repository.audits_for(record.id)
                ]
                if include_audits
                else []
            ),
        )

    def create(self, context: AuthContext, request: DeveloperCreateRequest) -> DeveloperResponse:
        self._authorize(context)
        email = str(request.email).lower()
        if self.repository.email_exists(email):
            raise AuthenticationError(409, "EMAIL_EXISTS", "Email address is already registered.")
        permissions = (
            self._permission_records(request.permissions)
            if request.permissions is not None
            else self.repository.default_permissions()
        )
        self._validate_permissions(permissions)
        try:
            record = self.repository.create_developer(
                actor_id=context.user_id,
                first_name=request.first_name.strip(),
                last_name=request.last_name.strip(),
                email=email,
                phone=request.phone.strip(),
                password_hash=hash_password(request.password.get_secret_value()),
                status=request.status,
                permissions=permissions,
            )
        except ValueError as error:
            raise AuthenticationError(409, "EMAIL_EXISTS", str(error)) from error
        return self._response(record, include_audits=True)

    def list(self, context: AuthContext, filters: DeveloperListFilters) -> DeveloperListResponse:
        self._authorize(context)
        records, total = self.repository.list_developers(**filters.model_dump())
        return DeveloperListResponse(
            items=[self._response(record) for record in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=ceil(total / filters.page_size) if total else 0,
            available_permissions=[
                DeveloperPermission(**item.__dict__)
                for item in self.repository.permission_catalog()
            ],
        )

    def get(self, context: AuthContext, developer_id: UUID) -> DeveloperResponse:
        self._authorize(context)
        record = self.repository.get_developer(developer_id)
        if record is None:
            raise AuthenticationError(404, "DEVELOPER_NOT_FOUND", "Developer does not exist.")
        return self._response(record, include_audits=True)

    def update(
        self, context: AuthContext, developer_id: UUID, request: DeveloperUpdateRequest
    ) -> DeveloperResponse:
        self._authorize(context)
        permissions = self._permission_records(request.permissions)
        self._validate_permissions(permissions)
        record = self.repository.update_developer(
            actor_id=context.user_id,
            developer_id=developer_id,
            first_name=request.first_name.strip(),
            last_name=request.last_name.strip(),
            phone=request.phone.strip(),
            status=request.status,
            permissions=permissions,
        )
        if record is None:
            raise AuthenticationError(404, "DEVELOPER_NOT_FOUND", "Developer does not exist.")
        return self._response(record, include_audits=True)

    def update_status(
        self, context: AuthContext, developer_id: UUID, request: DeveloperStatusRequest
    ) -> DeveloperResponse:
        self._authorize(context)
        record = self.repository.update_status(
            actor_id=context.user_id, developer_id=developer_id, status=request.status
        )
        if record is None:
            raise AuthenticationError(404, "DEVELOPER_NOT_FOUND", "Developer does not exist.")
        return self._response(record, include_audits=True)

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


developer_management_service = DeveloperManagementService()
