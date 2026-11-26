"""Per-client access for managers and employees (owner request 2026-11-26).

The admin gives each manager or employee Read, Write or Create access to chosen clients. Read sees
that client's tickets and content calendar, Write also changes status (up to Review), comments and
uploads files, Create also adds videos to the client's calendar. Access also puts the person in
the client's automatic chat group. No money is ever shown through this access.
"""

from __future__ import annotations

import logging
from typing import cast
from uuid import UUID

from app.repositories.client_access_repository import ClientAccessRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.authentication import AuthContext
from app.schemas.production import (
    ClientAccessGrant,
    ClientAccessLevel,
    ClientAccessOverview,
    ClientAccessPerson,
    ClientAccessUpdate,
    MyClientAccess,
    MyClientAccessResponse,
    NamedRef,
)
from app.services.authentication_service import AuthenticationError
from app.services.chat_service import ChatService, chat_service
from app.services.permission_service import validate_user_action_access

logger = logging.getLogger(__name__)
WORKER_ROLES = ("COMPANY_MANAGER", "COMPANY_EMPLOYEE")


class ClientAccessService:
    def __init__(
        self,
        repository: ClientAccessRepository | None = None,
        tasks: TaskRepository | None = None,
        chat: ChatService | None = None,
    ) -> None:
        self.repository = repository or ClientAccessRepository()
        self.tasks = tasks or TaskRepository()
        self.chat = chat or chat_service

    @staticmethod
    def _admin(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Only the Company Admin manages client access."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "TASKS", action):
            raise AuthenticationError(
                403, f"TASKS_{action}_REQUIRED", f"Tasks {action.lower()} permission is required."
            )
        return context.company_id

    def overview(self, context: AuthContext) -> ClientAccessOverview:
        company_id = self._admin(context, "VIEW")
        return ClientAccessOverview(
            people=[
                ClientAccessPerson(
                    id=person.id,
                    name=person.name,
                    role="MANAGER" if person.role == "MANAGER" else "EMPLOYEE",
                    code=person.code,
                )
                for person in self.tasks.list_people(company_id)
            ],
            clients=[
                NamedRef(id=client.id, name=client.name, code=client.code)
                for client in self.repository.clients(company_id)
            ],
            grants=[
                ClientAccessGrant(
                    user_id=grant.user_id,
                    client_id=grant.client_id,
                    level=cast(ClientAccessLevel, grant.level),
                )
                for grant in self.repository.grants(company_id)
            ],
        )

    def update(self, context: AuthContext, request: ClientAccessUpdate) -> ClientAccessOverview:
        company_id = self._admin(context, "ASSIGN")
        if self.tasks.get_person(company_id, request.user_id) is None:
            raise AuthenticationError(
                404, "PERSON_NOT_FOUND", "That person is not an active manager or employee."
            )
        if self.tasks.get_client(company_id, request.client_id) is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        self.repository.set(
            company_id, request.user_id, request.client_id, request.level, context.user_id
        )
        try:
            self.chat.sync_client_group(
                company_id,
                request.client_id,
                self.repository.user_ids_for_client(company_id, request.client_id),
                context.user_id,
            )
        except Exception:  # noqa: BLE001 - the access is saved even if the chat could not follow
            logger.warning("Could not update the client's chat group", exc_info=True)
        return self.overview(context)

    def mine(self, context: AuthContext) -> MyClientAccessResponse:
        if context.role not in WORKER_ROLES or context.company_id is None:
            raise AuthenticationError(
                403, "TEAM_MEMBER_REQUIRED", "Only managers and employees have client access."
            )
        return MyClientAccessResponse(
            items=[
                MyClientAccess(
                    client=NamedRef(id=client.id, name=client.name, code=client.code),
                    level=cast(ClientAccessLevel, level),
                )
                for client, level in self.repository.my_clients(context.company_id, context.user_id)
            ]
        )


client_access_service = ClientAccessService()
