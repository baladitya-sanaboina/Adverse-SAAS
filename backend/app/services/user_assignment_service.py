from uuid import UUID

from app.repositories.user_assignment_repository import CompanyUserRecord, UserAssignmentRepository
from app.schemas.authentication import AuthContext
from app.schemas.user_assignments import (
    AssignmentOption,
    AssignmentOptionsResponse,
    CompanyUserListResponse,
    CompanyUserResponse,
    UserAssignmentUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class UserAssignmentService:
    def __init__(self, repository: UserAssignmentRepository | None = None):
        self.repository = repository or UserAssignmentRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Company Admin access is required."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "USERS", action):
            raise AuthenticationError(
                403,
                "USER_ASSIGNMENT_PERMISSION_REQUIRED",
                "User assignment permission is required.",
            )
        return context.company_id

    @staticmethod
    def _response(record: CompanyUserRecord) -> CompanyUserResponse:
        return CompanyUserResponse(**record.__dict__)

    def list_users(self, context: AuthContext) -> CompanyUserListResponse:
        company_id = self._authorize(context, "VIEW")
        records = self.repository.list_users(company_id)
        return CompanyUserListResponse(
            items=[self._response(item) for item in records], total=len(records)
        )

    def options(self, context: AuthContext) -> AssignmentOptionsResponse:
        company_id = self._authorize(context, "VIEW")
        roles, departments, branches = self.repository.options(company_id)
        return AssignmentOptionsResponse(
            roles=[AssignmentOption(id=item[0], name=item[1]) for item in roles],
            departments=[AssignmentOption(id=item[0], name=item[1]) for item in departments],
            branches=[AssignmentOption(id=item[0], name=item[1]) for item in branches],
        )

    def assign(
        self, context: AuthContext, user_id: UUID, request: UserAssignmentUpdate
    ) -> CompanyUserResponse:
        company_id = self._authorize(context, "MANAGE")
        if user_id == context.user_id:
            raise AuthenticationError(
                409,
                "SELF_ASSIGNMENT_NOT_ALLOWED",
                "You cannot change your own role or organization assignment.",
            )
        record = self.repository.assign(
            company_id,
            user_id,
            context.user_id,
            request.role_id,
            request.department_id,
            request.branch_id,
        )
        if not record:
            raise AuthenticationError(
                404,
                "ASSIGNMENT_RESOURCE_NOT_FOUND",
                "User or assignment option was not found in this company.",
            )
        return self._response(record)

    def is_ready(self) -> bool:
        return self.repository.is_ready()


user_assignment_service = UserAssignmentService()
