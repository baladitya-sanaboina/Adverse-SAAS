from app.repositories.current_user_repository import CurrentUserRepository
from app.schemas.authentication import AuthContext
from app.schemas.current_user import (
    CurrentUserCompany,
    CurrentUserPermission,
    CurrentUserProfile,
    CurrentUserResponse,
    CurrentUserRole,
)
from app.services.authentication_service import AuthenticationError


class CurrentUserService:
    def __init__(self, repository: CurrentUserRepository | None = None):
        self.repository = repository or CurrentUserRepository()

    def get_current_user(self, context: AuthContext) -> CurrentUserResponse:
        record = self.repository.load_profile(context.user_id)
        if record is None:
            raise AuthenticationError(401, "USER_NOT_FOUND", "Authenticated user no longer exists.")
        if record.status != "ACTIVE":
            raise AuthenticationError(403, "USER_INACTIVE", "User account is not active.")
        if record.company_id and record.company_status != "ACTIVE":
            raise AuthenticationError(403, "COMPANY_INACTIVE", "Company is not active.")
        if record.role_code != context.role or record.company_id != context.company_id:
            raise AuthenticationError(401, "TOKEN_CONTEXT_CHANGED", "User context has changed.")

        company = None
        if (
            record.company_id
            and record.company_name
            and record.company_code
            and record.subscription_plan
            and record.company_status
        ):
            company = CurrentUserCompany(
                id=record.company_id,
                name=record.company_name,
                code=record.company_code,
                subscription_plan=record.subscription_plan,
                status=record.company_status,
                subscription_features=record.subscription_features,
            )

        permissions = [
            CurrentUserPermission(
                module=permission.module,
                module_name=permission.module_name,
                action=permission.action,
                action_name=permission.action_name,
            )
            for permission in self.repository.load_permissions(record.role_id, record.id)
        ]
        return CurrentUserResponse(
            user=CurrentUserProfile(
                id=record.id,
                name=record.name,
                email=record.email,
                status=record.status,
                created_at=record.created_at,
                profile_image_url=record.profile_image_url,
            ),
            company=company,
            role=CurrentUserRole(id=record.role_id, name=record.role_name, code=record.role_code),
            permissions=permissions,
        )

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


current_user_service = CurrentUserService()
