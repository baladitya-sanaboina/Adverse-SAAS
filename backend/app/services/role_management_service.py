from uuid import UUID

from app.repositories.role_management_repository import (
    RoleAssigned,
    RoleConflict,
    RoleManagementRepository,
    RoleRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.role_management import (
    PermissionActionOption,
    PermissionCatalogResponse,
    PermissionModuleOption,
    RoleCreate,
    RoleDetailResponse,
    RoleListResponse,
    RoleSummaryResponse,
    RoleUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class RoleManagementService:
    def __init__(self, repository: RoleManagementRepository | None = None):
        self.repository = repository or RoleManagementRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Company Admin access is required."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "ROLES", action):
            raise AuthenticationError(
                403, "ROLE_PERMISSION_REQUIRED", "Role management permission is required."
            )
        return context.company_id

    @staticmethod
    def _summary(record: RoleRecord) -> RoleSummaryResponse:
        return RoleSummaryResponse(**record.__dict__)

    def _validate_permissions(self, permissions: list[str]) -> None:
        invalid = set(permissions) - self.repository.valid_permission_keys()
        if invalid:
            raise AuthenticationError(
                422, "INVALID_ROLE_PERMISSION", "One or more permissions are invalid."
            )

    def list_roles(self, context: AuthContext, search: str, status: str | None) -> RoleListResponse:
        company_id = self._authorize(context, "VIEW")
        records = self.repository.list_roles(company_id, search.strip(), status)
        return RoleListResponse(
            items=[self._summary(record) for record in records], total=len(records)
        )

    def get_role(self, context: AuthContext, role_id: UUID) -> RoleDetailResponse:
        company_id = self._authorize(context, "VIEW")
        result = self.repository.get_role(company_id, role_id)
        if not result:
            raise AuthenticationError(404, "ROLE_NOT_FOUND", "Role was not found in this company.")
        record, permissions = result
        return RoleDetailResponse(**record.__dict__, permissions=permissions)

    def permission_catalog(self, context: AuthContext) -> PermissionCatalogResponse:
        self._authorize(context, "VIEW")
        grouped: dict[tuple[str, str], list[PermissionActionOption]] = {}
        for (
            module_code,
            module_name,
            action_code,
            action_name,
        ) in self.repository.permission_catalog():
            grouped.setdefault((module_code, module_name), []).append(
                PermissionActionOption(
                    code=action_code, name=action_name, key=f"{module_code}.{action_code}"
                )
            )
        return PermissionCatalogResponse(
            modules=[
                PermissionModuleOption(code=code, name=name, actions=actions)
                for (code, name), actions in grouped.items()
            ]
        )

    def create(self, context: AuthContext, request: RoleCreate) -> RoleDetailResponse:
        company_id = self._authorize(context, "CREATE")
        self._validate_permissions(request.permissions)
        try:
            role_id = self.repository.create(
                company_id, context.user_id, request.name, request.description, request.permissions
            )
        except RoleConflict as error:
            raise AuthenticationError(
                409, "ROLE_NAME_EXISTS", "A role with this name already exists in this company."
            ) from error
        return self.get_role(context, role_id)

    def update(
        self, context: AuthContext, role_id: UUID, request: RoleUpdate
    ) -> RoleDetailResponse:
        company_id = self._authorize(context, "EDIT")
        values = request.model_dump(exclude_unset=True)
        permissions = values.get("permissions")
        if isinstance(permissions, list):
            self._validate_permissions(permissions)
        try:
            updated = self.repository.update(company_id, context.user_id, role_id, values)
        except RoleConflict as error:
            raise AuthenticationError(
                409, "ROLE_NAME_EXISTS", "A role with this name already exists in this company."
            ) from error
        if not updated:
            raise AuthenticationError(
                404, "ROLE_NOT_FOUND", "Custom role was not found in this company."
            )
        return self.get_role(context, role_id)

    def delete(self, context: AuthContext, role_id: UUID) -> RoleDetailResponse:
        company_id = self._authorize(context, "DELETE")
        role = self.get_role(context, role_id)
        try:
            deleted = self.repository.delete(company_id, context.user_id, role_id)
        except RoleAssigned as error:
            raise AuthenticationError(
                409, "ROLE_ASSIGNED_TO_USERS", "Reassign users before deleting this role."
            ) from error
        if not deleted:
            raise AuthenticationError(
                404, "ROLE_NOT_FOUND", "Custom role was not found in this company."
            )
        return role

    def is_ready(self) -> bool:
        return self.repository.is_ready()


role_management_service = RoleManagementService()
