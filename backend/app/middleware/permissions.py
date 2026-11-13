from dataclasses import dataclass

from fastapi import HTTPException, status

from app.middleware.authentication import AuthenticatedContext
from app.services.permission_service import validate_action_access, validate_user_action_access


@dataclass(frozen=True)
class PermissionRequirement:
    module: str
    action: str

    def allows(self, role_code: str) -> bool:
        return validate_action_access(role_code, self.module, self.action)

    def enforce(self, role_code: str) -> None:
        if not self.allows(role_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{self.action} access to {self.module} is required.",
            )

    def __call__(self, context: AuthenticatedContext) -> None:
        if not validate_user_action_access(
            str(context.user_id), context.role, self.module, self.action
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{self.action} access to {self.module} is required.",
            )


def require_permission(module: str, action: str) -> PermissionRequirement:
    """Create a request-time authorization dependency."""
    return PermissionRequirement(module=module, action=action)
