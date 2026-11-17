from uuid import UUID

from app.repositories.employee_repository import (
    EmployeeConflict,
    EmployeeDeletionError,
    EmployeeRecord,
    EmployeeReferenceError,
    EmployeeRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListFilters,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class EmployeeService:
    def __init__(self, repository: EmployeeRepository | None = None):
        self.repository = repository or EmployeeRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> UUID:
        if context.user_type != "company" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_CONTEXT_REQUIRED", "Company access is required."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "EMPLOYEES", action):
            raise AuthenticationError(
                403,
                f"EMPLOYEES_{action}_REQUIRED",
                f"Employees {action.lower()} permission is required.",
            )
        return context.company_id

    @staticmethod
    def _response(record: EmployeeRecord) -> EmployeeResponse:
        return EmployeeResponse(**record.__dict__)

    def list(self, context: AuthContext, filters: EmployeeListFilters) -> EmployeeListResponse:
        company_id = self._authorize(context, "VIEW")
        records, total = self.repository.list(company_id, filters)
        return EmployeeListResponse(
            items=[self._response(record) for record in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=(total + filters.page_size - 1) // filters.page_size,
        )

    def get(self, context: AuthContext, employee_id: UUID) -> EmployeeResponse:
        company_id = self._authorize(context, "VIEW")
        record = self.repository.get(company_id, employee_id)
        if record is None:
            raise AuthenticationError(404, "EMPLOYEE_NOT_FOUND", "Employee was not found.")
        return self._response(record)

    def create(self, context: AuthContext, request: EmployeeCreate) -> EmployeeResponse:
        company_id = self._authorize(context, "CREATE")
        try:
            record = self.repository.create(
                company_id,
                context.user_id,
                request.user_id,
                request.employee_code,
                request.department_id,
                request.branch_id,
                request.role_id,
                request.status,
            )
        except EmployeeConflict as error:
            code = "EMPLOYEE_PROFILE_EXISTS" if error.field == "user" else "EMPLOYEE_CODE_EXISTS"
            detail = (
                "The user already has an employee profile."
                if error.field == "user"
                else "Employee code already exists in this company."
            )
            raise AuthenticationError(409, code, detail) from error
        except EmployeeReferenceError as error:
            raise AuthenticationError(
                404,
                f"EMPLOYEE_{error.reference.upper()}_NOT_FOUND",
                f"The selected {error.reference} was not found in this company.",
            ) from error
        return self._response(record)

    def update(
        self, context: AuthContext, employee_id: UUID, request: EmployeeUpdate
    ) -> EmployeeResponse:
        company_id = self._authorize(context, "EDIT")
        try:
            record = self.repository.update(
                company_id,
                context.user_id,
                employee_id,
                request.model_dump(exclude_unset=True),
            )
        except EmployeeConflict as error:
            raise AuthenticationError(
                409, "EMPLOYEE_CODE_EXISTS", "Employee code already exists in this company."
            ) from error
        except EmployeeReferenceError as error:
            raise AuthenticationError(
                404,
                f"EMPLOYEE_{error.reference.upper()}_NOT_FOUND",
                f"The selected {error.reference} was not found in this company.",
            ) from error
        if record is None:
            raise AuthenticationError(404, "EMPLOYEE_NOT_FOUND", "Employee was not found.")
        return self._response(record)

    def delete(self, context: AuthContext, employee_id: UUID) -> None:
        company_id = self._authorize(context, "DELETE")
        try:
            deleted = self.repository.delete_pending(company_id, employee_id)
        except EmployeeDeletionError as error:
            if error.reason == "ACTIVE_ACCOUNT":
                raise AuthenticationError(
                    409,
                    "EMPLOYEE_DELETE_PENDING_ONLY",
                    "Only employees with an unaccepted invite can be deleted.",
                ) from error
            raise AuthenticationError(
                409,
                "EMPLOYEE_IN_USE",
                "Employee cannot be deleted because company work is already linked.",
            ) from error
        if deleted is None:
            raise AuthenticationError(404, "EMPLOYEE_NOT_FOUND", "Employee was not found.")

    def is_ready(self) -> bool:
        return self.repository.is_ready()


employee_service = EmployeeService()
