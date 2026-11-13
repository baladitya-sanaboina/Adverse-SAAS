from uuid import UUID

from app.repositories.organization_repository import (
    BranchRecord,
    DepartmentRecord,
    OrganizationConflict,
    OrganizationRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.organization import (
    BranchCreate,
    BranchListResponse,
    BranchResponse,
    BranchUpdate,
    DepartmentCreate,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class OrganizationService:
    def __init__(self, repository: OrganizationRepository | None = None):
        self.repository = repository or OrganizationRepository()

    @staticmethod
    def _authorize(context: AuthContext, module: str, action: str) -> UUID:
        if context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_CONTEXT_REQUIRED", "Company access is required."
            )
        if not validate_user_action_access(str(context.user_id), context.role, module, action):
            raise AuthenticationError(
                403,
                "ORGANIZATION_PERMISSION_REQUIRED",
                f"{module.replace('_', ' ').title()} {action.lower()} permission is required.",
            )
        return context.company_id

    @staticmethod
    def _department(record: DepartmentRecord) -> DepartmentResponse:
        return DepartmentResponse(**record.__dict__)

    @staticmethod
    def _branch(record: BranchRecord) -> BranchResponse:
        return BranchResponse(**record.__dict__)

    def list_departments(
        self, context: AuthContext, search: str = "", status: str | None = None
    ) -> DepartmentListResponse:
        company_id = self._authorize(context, "DEPARTMENTS", "VIEW")
        items = self.repository.list_departments(company_id, search.strip(), status)
        return DepartmentListResponse(
            items=[self._department(item) for item in items], total=len(items)
        )

    def get_department(self, context: AuthContext, item_id: UUID) -> DepartmentResponse:
        company_id = self._authorize(context, "DEPARTMENTS", "VIEW")
        record = self.repository.get_department(company_id, item_id)
        if not record:
            raise AuthenticationError(404, "DEPARTMENT_NOT_FOUND", "Department was not found.")
        return self._department(record)

    def create_department(
        self, context: AuthContext, request: DepartmentCreate
    ) -> DepartmentResponse:
        company_id = self._authorize(context, "DEPARTMENTS", "CREATE")
        try:
            record = self.repository.create_department(
                company_id, request.name, request.description
            )
        except OrganizationConflict as error:
            raise AuthenticationError(
                409, "DEPARTMENT_EXISTS", "Department name already exists."
            ) from error
        self.repository.write_audit(
            "DEPARTMENT_CREATED",
            context.user_id,
            company_id,
            "DEPARTMENT",
            record.id,
            {"name": record.name},
        )
        return self._department(record)

    def update_department(
        self, context: AuthContext, item_id: UUID, request: DepartmentUpdate
    ) -> DepartmentResponse:
        company_id = self._authorize(context, "DEPARTMENTS", "EDIT")
        try:
            record = self.repository.update_department(
                company_id, item_id, request.model_dump(exclude_none=True)
            )
        except OrganizationConflict as error:
            raise AuthenticationError(
                409, "DEPARTMENT_EXISTS", "Department name already exists."
            ) from error
        if not record:
            raise AuthenticationError(404, "DEPARTMENT_NOT_FOUND", "Department was not found.")
        action = (
            "DEPARTMENT_ACTIVATED"
            if request.status == "ACTIVE"
            else "DEPARTMENT_DEACTIVATED" if request.status == "INACTIVE" else "DEPARTMENT_UPDATED"
        )
        self.repository.write_audit(
            action,
            context.user_id,
            company_id,
            "DEPARTMENT",
            record.id,
            {"name": record.name, "changed_fields": sorted(request.model_fields_set)},
        )
        return self._department(record)

    def disable_department(self, context: AuthContext, item_id: UUID) -> DepartmentResponse:
        company_id = self._authorize(context, "DEPARTMENTS", "DELETE")
        record = self.repository.update_department(company_id, item_id, {"status": "INACTIVE"})
        if not record:
            raise AuthenticationError(404, "DEPARTMENT_NOT_FOUND", "Department was not found.")
        self.repository.write_audit(
            "DEPARTMENT_DEACTIVATED",
            context.user_id,
            company_id,
            "DEPARTMENT",
            record.id,
            {"name": record.name},
        )
        return self._department(record)

    def list_branches(
        self, context: AuthContext, search: str = "", status: str | None = None
    ) -> BranchListResponse:
        company_id = self._authorize(context, "BRANCHES", "VIEW")
        items = self.repository.list_branches(company_id, search.strip(), status)
        return BranchListResponse(items=[self._branch(item) for item in items], total=len(items))

    def get_branch(self, context: AuthContext, item_id: UUID) -> BranchResponse:
        company_id = self._authorize(context, "BRANCHES", "VIEW")
        record = self.repository.get_branch(company_id, item_id)
        if not record:
            raise AuthenticationError(404, "BRANCH_NOT_FOUND", "Branch was not found.")
        return self._branch(record)

    def create_branch(self, context: AuthContext, request: BranchCreate) -> BranchResponse:
        company_id = self._authorize(context, "BRANCHES", "CREATE")
        try:
            record = self.repository.create_branch(company_id, request.model_dump())
        except OrganizationConflict as error:
            raise AuthenticationError(
                409, "BRANCH_EXISTS", "Branch name or code already exists."
            ) from error
        self.repository.write_audit(
            "BRANCH_CREATED",
            context.user_id,
            company_id,
            "BRANCH",
            record.id,
            {"name": record.name, "code": record.code},
        )
        return self._branch(record)

    def update_branch(
        self, context: AuthContext, item_id: UUID, request: BranchUpdate
    ) -> BranchResponse:
        company_id = self._authorize(context, "BRANCHES", "EDIT")
        try:
            record = self.repository.update_branch(
                company_id, item_id, request.model_dump(exclude_none=True)
            )
        except OrganizationConflict as error:
            raise AuthenticationError(
                409, "BRANCH_EXISTS", "Branch name or code already exists."
            ) from error
        if not record:
            raise AuthenticationError(404, "BRANCH_NOT_FOUND", "Branch was not found.")
        action = (
            "BRANCH_ACTIVATED"
            if request.status == "ACTIVE"
            else "BRANCH_DEACTIVATED" if request.status == "INACTIVE" else "BRANCH_UPDATED"
        )
        self.repository.write_audit(
            action,
            context.user_id,
            company_id,
            "BRANCH",
            record.id,
            {
                "name": record.name,
                "code": record.code,
                "changed_fields": sorted(request.model_fields_set),
            },
        )
        return self._branch(record)

    def disable_branch(self, context: AuthContext, item_id: UUID) -> BranchResponse:
        company_id = self._authorize(context, "BRANCHES", "DELETE")
        record = self.repository.update_branch(company_id, item_id, {"status": "INACTIVE"})
        if not record:
            raise AuthenticationError(404, "BRANCH_NOT_FOUND", "Branch was not found.")
        self.repository.write_audit(
            "BRANCH_DEACTIVATED",
            context.user_id,
            company_id,
            "BRANCH",
            record.id,
            {"name": record.name, "code": record.code},
        )
        return self._branch(record)

    def is_ready(self) -> bool:
        return self.repository.is_ready()


organization_service = OrganizationService()
