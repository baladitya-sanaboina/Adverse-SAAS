"""Content calendar (Phase 13, owner decision 2026-11-14).

Every entry (except a no-post day) becomes a ticket: a Pending, unassigned task for that date,
ranked by how soon the date is (owner request 2026-11-14). While nobody has the ticket yet, it
follows the entry's title and date, and removing the entry cancels it.

- Client: sees and edits only their own entries; ticks Recorded, Script, Instagram, YouTube;
  cannot tick Edited or link tasks; cannot delete an entry once a task is linked to it.
- Admin (TASKS permission): sees every client's entries, can change anything, links tasks.
- Managers and employees have no access (they see the task once it is created).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.repositories.calendar_repository import CalendarEntryRow, CalendarRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.authentication import AuthContext
from app.schemas.calendar import (
    CalendarEntryCreate,
    CalendarEntryResponse,
    CalendarEntryUpdate,
    CalendarListResponse,
    CalendarScriptRef,
    CalendarTaskRef,
    StaffCalendarResponse,
    StaffCalendarTask,
)
from app.schemas.production import NamedRef
from app.services.authentication_service import AuthenticationError
from app.services.notification_service import notification_service
from app.services.permission_service import validate_user_action_access
from app.services.production_rules import BILLABLE_STATUSES
from app.services.task_file_storage import TaskFileStorage
from app.services.task_service import TaskService, task_service

logger = logging.getLogger(__name__)

MAX_SCRIPT_BYTES = 25 * 1024 * 1024  # scripts are documents, not videos
CLIENT_FIELDS = frozenset(
    {
        "entry_date",
        "title",
        "reference_url",
        "script_url",
        "pdf_url",
        "notes",
        "no_post",
        "recorded",
        "script_ready",
        "posted_instagram",
        "posted_youtube",
    }
)


def entry_response(row: CalendarEntryRow) -> CalendarEntryResponse:
    approved = row.task_status in BILLABLE_STATUSES
    return CalendarEntryResponse(
        id=row.id,
        client=NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
        entry_date=row.entry_date,
        title=row.title,
        reference_url=row.reference_url,
        script_url=row.script_url,
        pdf_url=row.pdf_url,
        notes=row.notes,
        no_post=row.no_post,
        recorded=row.recorded,
        script_ready=row.script_ready,
        posted_instagram=row.posted_instagram,
        posted_youtube=row.posted_youtube,
        edited=approved or row.edited_manual,
        edited_manual=row.edited_manual,
        script=(
            CalendarScriptRef(file_name=row.script_file_name, size_bytes=row.script_size_bytes or 0)
            if row.script_file_name and row.script_storage_path
            else None
        ),
        task=(
            CalendarTaskRef(
                id=row.task_id,
                code=f"TSK-{row.task_number:04d}",
                title=row.task_title or "",
                status=row.task_status,
            )
            if row.task_id is not None and row.task_number is not None and row.task_status
            else None
        ),
        created_by_name=row.created_by_name,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class CalendarService:
    def __init__(
        self,
        repository: CalendarRepository | None = None,
        tasks: TaskRepository | None = None,
        storage: TaskFileStorage | None = None,
        tickets: TaskService | None = None,
    ) -> None:
        self.repository = repository or CalendarRepository()
        self.tickets = tickets or task_service
        self.tasks = tasks or TaskRepository()
        self.storage = storage or TaskFileStorage(
            Path("private-storage/calendar-scripts"), MAX_SCRIPT_BYTES
        )

    # -- access ------------------------------------------------------------------------------

    @staticmethod
    def _admin(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Only the Company Admin can manage the calendar."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "TASKS", action):
            raise AuthenticationError(
                403, f"TASKS_{action}_REQUIRED", f"Tasks {action.lower()} permission is required."
            )
        return context.company_id

    def _client(self, context: AuthContext) -> tuple[UUID, NamedRef]:
        if context.role != "COMPANY_CLIENT" or context.company_id is None:
            raise AuthenticationError(
                403, "CLIENT_REQUIRED", "Only client accounts have a content calendar."
            )
        client = self.tasks.get_client_for_user(context.company_id, context.user_id)
        if client is None:
            raise AuthenticationError(
                404, "CLIENT_PROFILE_NOT_FOUND", "No client profile is linked to this account."
            )
        return context.company_id, NamedRef(id=client.id, name=client.name, code=client.code)

    def _entry(self, company_id: UUID, entry_id: UUID, client_id: UUID | None) -> CalendarEntryRow:
        row = self.repository.get(company_id, entry_id)
        # A client asking for another client's entry gets the same answer as a missing one.
        if row is None or (client_id is not None and row.client_id != client_id):
            raise AuthenticationError(404, "CALENDAR_ENTRY_NOT_FOUND", "Calendar entry not found.")
        return row

    @staticmethod
    def _check_range(start: date | None, end: date | None) -> None:
        if start is not None and end is not None and end < start:
            raise AuthenticationError(422, "INVALID_PERIOD", "The end date is before the start.")

    # -- tickets ------------------------------------------------------------------------------

    def _open_ticket(self, company_id: UUID, entry_id: UUID, actor_id: UUID) -> UUID | None:
        """Make the ticket for an entry (never blocks saving the entry itself)."""
        row = self.repository.get(company_id, entry_id)
        if row is None or row.no_post or row.task_id is not None:
            return None
        description = "\n\n".join(
            part
            for part in (
                row.notes,
                f"Reference: {row.reference_url}" if row.reference_url else "",
                f"Script: {row.script_url}" if row.script_url else "",
                f"PDF: {row.pdf_url}" if row.pdf_url else "",
                "From the client's content calendar.",
            )
            if part
        )
        try:
            task_id = self.tickets.create_calendar_ticket(
                company_id, row.client_id, actor_id, row.title, description, row.entry_date
            )
        except Exception:  # noqa: BLE001 - the entry is saved even if the ticket fails
            logger.warning("Could not create the calendar ticket", exc_info=True)
            return None
        if task_id is not None:
            self.repository.set_task(company_id, entry_id, task_id)
        self._tell_admins(company_id, row, task_id, actor_id)
        return task_id

    @staticmethod
    def _tell_admins(
        company_id: UUID, row: CalendarEntryRow, task_id: UUID | None, actor_id: UUID
    ) -> None:
        """A new calendar item is work to assign (owner request 2026-11-19): every admin gets a
        bell and an internal mail with a link to the task (or a note when no task could be made
        because the client has no rate yet). Never raises."""
        try:
            from app.repositories.chat_repository import ChatRepository
            from app.services.mail_service import mail_service

            admins = [user for user in ChatRepository().admin_ids(company_id) if user != actor_id]
            if not admins:
                return
            when = row.entry_date.strftime("%a %d %b")
            if task_id is not None:
                subject = f"New task from {row.client_name}: {row.title}"
                body = (
                    f'{row.client_name} added "{row.title}" to their content calendar for {when}.\n\n'
                    "It is in Tasks as Pending and not assigned yet. Open it to assign someone."
                )
                link = f"/tasks?task={task_id}"
            else:
                subject = f"Calendar item needs a task: {row.title}"
                body = (
                    f'{row.client_name} added "{row.title}" to their content calendar for {when}, '
                    "but no task could be made: this client has no service rate yet.\n\n"
                    "Set the client's rate, or create the task by hand."
                )
                link = "/tasks?mode=create"
            mail_service.system(
                company_id,
                admins,
                subject,
                body,
                link=link,
                kind="TASK",
                once_key=f"calendar-task:{row.id}",
                notify=True,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Could not tell the admins about a calendar item", exc_info=True)

    def _follow(self, company_id: UUID, before: CalendarEntryRow, actor_id: UUID) -> None:
        """After an edit: keep the ticket in step, cancel it for a no-post day, or open one."""
        after = self._entry(company_id, before.id, None)
        if after.task_id is None:
            self._open_ticket(company_id, after.id, actor_id)
            return
        if after.no_post and not before.no_post:
            if after.task_status == "PENDING":
                self.tickets.cancel_calendar_ticket(company_id, after.task_id, actor_id)
                self.repository.set_task(company_id, after.id, None)
            return
        if (after.title, after.entry_date) != (before.title, before.entry_date):
            self.tickets.sync_calendar_ticket(
                company_id, after.task_id, actor_id, after.title, after.entry_date
            )

    # -- admin -------------------------------------------------------------------------------

    def admin_list(
        self,
        context: AuthContext,
        client_id: UUID | None,
        start: date | None,
        end: date | None,
    ) -> CalendarListResponse:
        company_id = self._admin(context, "VIEW")
        self._check_range(start, end)
        return CalendarListResponse(
            items=[
                entry_response(row)
                for row in self.repository.list(company_id, client_id, start, end)
            ]
        )

    def admin_create(
        self, context: AuthContext, request: CalendarEntryCreate
    ) -> CalendarEntryResponse:
        company_id = self._admin(context, "CREATE")
        if request.client_id is None:
            raise AuthenticationError(422, "CLIENT_REQUIRED", "Choose the client for this entry.")
        client = self.tasks.get_client(company_id, request.client_id)
        if client is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        entry_id = self.repository.create(
            company_id, client.id, context.user_id, request.model_dump(exclude={"client_id"})
        )
        self._open_ticket(company_id, entry_id, context.user_id)
        notification_service.notify(
            company_id,
            [notification_service.client_user(company_id, client.id)],
            "calendar.entry",
            "New calendar entry",
            f"{request.title} on {request.entry_date:%d %b %Y} was added to your calendar.",
            "/calendar",
            {"entry_id": str(entry_id)},
            exclude=context.user_id,
        )
        return entry_response(self._entry(company_id, entry_id, None))

    def admin_update(
        self, context: AuthContext, entry_id: UUID, request: CalendarEntryUpdate
    ) -> CalendarEntryResponse:
        company_id = self._admin(context, "EDIT")
        before = self._entry(company_id, entry_id, None)
        self.repository.update(company_id, entry_id, request.model_dump(exclude_none=True))
        self._follow(company_id, before, context.user_id)
        return entry_response(self._entry(company_id, entry_id, None))

    def admin_delete(self, context: AuthContext, entry_id: UUID) -> None:
        company_id = self._admin(context, "DELETE")
        row = self._entry(company_id, entry_id, None)
        self.repository.delete(company_id, entry_id)
        self._remove_script(row)

    def link_task(
        self, context: AuthContext, entry_id: UUID, task_id: UUID | None
    ) -> CalendarEntryResponse:
        company_id = self._admin(context, "EDIT")
        row = self._entry(company_id, entry_id, None)
        if task_id is not None:
            task_client = self.repository.task_client(company_id, task_id)
            if task_client is None:
                raise AuthenticationError(404, "TASK_NOT_FOUND", "Task was not found.")
            if task_client != row.client_id:
                raise AuthenticationError(
                    422, "TASK_CLIENT_MISMATCH", "That task belongs to a different client."
                )
        self.repository.set_task(company_id, entry_id, task_id)
        return entry_response(self._entry(company_id, entry_id, None))

    # -- client ------------------------------------------------------------------------------

    def client_list(
        self, context: AuthContext, start: date | None, end: date | None
    ) -> CalendarListResponse:
        company_id, client = self._client(context)
        self._check_range(start, end)
        return CalendarListResponse(
            items=[
                entry_response(row)
                for row in self.repository.list(company_id, client.id, start, end)
            ]
        )

    def client_create(
        self, context: AuthContext, request: CalendarEntryCreate
    ) -> CalendarEntryResponse:
        company_id, client = self._client(context)
        if request.client_id is not None and request.client_id != client.id:
            raise AuthenticationError(
                403, "CLIENT_MISMATCH", "You can only add to your own calendar."
            )
        entry_id = self.repository.create(
            company_id, client.id, context.user_id, request.model_dump(exclude={"client_id"})
        )
        task_id = self._open_ticket(company_id, entry_id, context.user_id)
        if not request.no_post:
            notification_service.notify(
                company_id,
                notification_service.admins(company_id),
                "calendar.entry",
                (
                    f"New ticket from {client.name}"
                    if task_id
                    else f"{client.name} added to the calendar"
                ),
                f"{request.title} for {request.entry_date:%d %b %Y}."
                + (
                    "" if task_id else " Set a client rate, then create the task from the calendar."
                ),
                f"/tasks?task={task_id}" if task_id else f"/calendar?entry={entry_id}",
                {
                    "entry_id": str(entry_id),
                    "client_id": str(client.id),
                    **({"task_id": str(task_id)} if task_id else {}),
                },
            )
        return entry_response(self._entry(company_id, entry_id, client.id))

    def client_update(
        self, context: AuthContext, entry_id: UUID, request: CalendarEntryUpdate
    ) -> CalendarEntryResponse:
        company_id, client = self._client(context)
        before = self._entry(company_id, entry_id, client.id)
        values = request.model_dump(exclude_none=True)
        if "edited_manual" in values:
            raise AuthenticationError(
                403,
                "EDITED_IS_AUTOMATIC",
                "Edited ticks itself when your agency approves the video.",
            )
        changes = {key: value for key, value in values.items() if key in CLIENT_FIELDS}
        started = before.task_status not in (None, "PENDING", "ASSIGNED", "CANCELLED")
        moved = any(
            key in changes and changes[key] != getattr(before, key)
            for key in ("entry_date", "title", "no_post")
        )
        if started and moved:
            raise AuthenticationError(
                409,
                "ENTRY_IN_PRODUCTION",
                "Your agency is working on this video, so only the ticks can change.",
            )
        self.repository.update(company_id, entry_id, changes)
        self._follow(company_id, before, context.user_id)
        return entry_response(self._entry(company_id, entry_id, client.id))

    def client_delete(self, context: AuthContext, entry_id: UUID) -> None:
        """A client can remove an entry until someone takes the ticket; the ticket is cancelled."""
        company_id, client = self._client(context)
        row = self._entry(company_id, entry_id, client.id)
        if row.task_id is not None and row.task_status != "CANCELLED":
            self.tickets.cancel_calendar_ticket(company_id, row.task_id, context.user_id)
        self.repository.delete(company_id, entry_id)
        self._remove_script(row)

    # -- script file (both roles) -----------------------------------------------------------

    def _owner(self, context: AuthContext, action: str) -> tuple[UUID, UUID | None]:
        if context.role == "COMPANY_CLIENT":
            company_id, client = self._client(context)
            return company_id, client.id
        return self._admin(context, action), None

    def upload_script(
        self, context: AuthContext, entry_id: UUID, upload: UploadFile
    ) -> CalendarEntryResponse:
        company_id, client_id = self._owner(context, "EDIT")
        row = self._entry(company_id, entry_id, client_id)
        stored = self.storage.save(company_id, entry_id, upload)
        self.repository.set_script(
            company_id,
            entry_id,
            stored.file_name,
            stored.storage_path,
            stored.mime_type,
            stored.size_bytes,
        )
        self._remove_script(row)
        return entry_response(self._entry(company_id, entry_id, client_id))

    def script_file(self, context: AuthContext, entry_id: UUID) -> tuple[Path, str, str]:
        company_id, client_id = self._owner(context, "VIEW")
        row = self._entry(company_id, entry_id, client_id)
        if not row.script_storage_path or not row.script_file_name:
            raise AuthenticationError(404, "FILE_NOT_FOUND", "This entry has no script file.")
        return (
            self.storage.path_for(row.script_storage_path),
            row.script_file_name,
            row.script_mime_type or "application/octet-stream",
        )

    def delete_script(self, context: AuthContext, entry_id: UUID) -> CalendarEntryResponse:
        company_id, client_id = self._owner(context, "EDIT")
        row = self._entry(company_id, entry_id, client_id)
        self.repository.set_script(company_id, entry_id, None, None, None, None)
        self._remove_script(row)
        return entry_response(self._entry(company_id, entry_id, client_id))

    def _remove_script(self, row: CalendarEntryRow) -> None:
        if not row.script_storage_path:
            return
        try:
            self.storage.path_for(row.script_storage_path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001 - a missing old file must not fail the request
            logger.warning("Could not remove an old calendar script", exc_info=True)

    # -- staff calendar ---------------------------------------------------------------------

    def staff_calendar(self, context: AuthContext, start: date, end: date) -> StaffCalendarResponse:
        """Managers and employees: their own tasks by due date and the content entries those
        tasks came from. Never prices or other people's work."""
        if (
            context.role not in ("COMPANY_MANAGER", "COMPANY_EMPLOYEE")
            or context.company_id is None
        ):
            raise AuthenticationError(
                403, "STAFF_ONLY", "This calendar is for managers and employees."
            )
        self._check_range(start, end)
        if (end - start).days > 92:
            raise AuthenticationError(422, "RANGE_TOO_LONG", "Ask for at most three months.")
        company_id = context.company_id
        return StaffCalendarResponse(
            tasks=[
                StaffCalendarTask(
                    id=row[0],
                    code=f"TSK-{row[1]:04d}",
                    title=row[2],
                    status=row[3],
                    due_date=row[4],
                    client_name=row[5],
                    my_role=row[6],
                )
                for row in self.repository.staff_tasks(company_id, context.user_id, start, end)
            ],
            entries=[
                entry_response(row)
                for row in self.repository.staff_entries(company_id, context.user_id, start, end)
            ],
        )


calendar_service = CalendarService()
