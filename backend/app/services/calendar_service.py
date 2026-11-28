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
from app.repositories.client_access_repository import ClientAccessRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.authentication import AuthContext
from app.schemas.calendar import (
    CalendarEntryCreate,
    CalendarEntryResponse,
    CalendarEntryUpdate,
    CalendarListResponse,
    CalendarScriptRef,
    CalendarServiceOption,
    CalendarTaskRef,
    StaffCalendarResponse,
    StaffCalendarTask,
)
from app.schemas.production import NamedRef, TaskPriority
from app.services.authentication_service import AuthenticationError
from app.services.notification_service import notification_service
from app.services.permission_service import validate_user_action_access
from app.services.production_rules import BILLABLE_STATUSES, access_allows
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
        "service_id",
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
        service=(
            NamedRef(id=row.service_id, name=row.service_name or "", code="")
            if row.service_id is not None
            else None
        ),
        added_by_team=row.added_by_team,
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
        access: ClientAccessRepository | None = None,
    ) -> None:
        self.repository = repository or CalendarRepository()
        self.access = access or ClientAccessRepository()
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

    def _check_service(self, company_id: UUID, service_id: UUID | None) -> None:
        """The chosen service must be one of the company's active services."""
        if service_id is None:
            return
        service = self.tasks.get_service(company_id, service_id)
        if service is None or service.status != "ACTIVE":
            raise AuthenticationError(
                422, "SERVICE_NOT_AVAILABLE", "Choose one of the services in the list."
            )

    def _check_service_change(
        self,
        company_id: UUID,
        before: CalendarEntryRow,
        changes: dict[str, object],
        client: bool = False,
    ) -> None:
        """A new service must be active. Waiting tickets follow it; an assigned ticket is
        cancelled and a new one goes to To assign (owner decision 2026-11-26). Never after the
        video is approved (it is billed), and the client only until work starts. A no-post day
        that becomes a video needs a service, like a new entry."""
        service_id = changes.get("service_id")
        if isinstance(service_id, UUID) and service_id != before.service_id:
            self._check_service(company_id, service_id)
            if before.task_status in BILLABLE_STATUSES:
                raise AuthenticationError(
                    409,
                    "SERVICE_LOCKED",
                    "This video is already approved, so its service cannot change.",
                )
            if client and before.task_status in ("IN_PROGRESS", "SUBMITTED", "REVIEW"):
                raise AuthenticationError(
                    409,
                    "ENTRY_IN_PRODUCTION",
                    "Your agency is working on this video, so its service cannot change now.",
                )
        if before.no_post and changes.get("no_post") is False:
            if (service_id or before.service_id) is None:
                raise AuthenticationError(
                    422, "SERVICE_REQUIRED", "Choose the service: Reel, Carousel, Thumbnail..."
                )

    def _service_options(self, company_id: UUID, client_id: UUID) -> list[CalendarServiceOption]:
        out = []
        for service_id in self.tasks.calendar_service_choices(company_id, client_id):
            service = self.tasks.get_service(company_id, service_id)
            if service is not None and service.status == "ACTIVE":
                out.append(
                    CalendarServiceOption(id=service.id, name=service.name, code=service.code)
                )
        return out

    def client_services(self, context: AuthContext) -> list[CalendarServiceOption]:
        """Services a client can pick for a video, the ones they use most first."""
        company_id, client = self._client(context)
        return self._service_options(company_id, client.id)

    def admin_services(
        self, context: AuthContext, client_id: UUID | None
    ) -> list[CalendarServiceOption]:
        company_id = self._admin(context, "VIEW")
        if client_id is not None:
            return self._service_options(company_id, client_id)
        return self._service_options(company_id, UUID(int=0))

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

    def _open_ticket(
        self,
        company_id: UUID,
        entry_id: UUID,
        actor_id: UUID,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
    ) -> UUID | None:
        """Make the ticket for an entry (never blocks saving the entry itself). `assignee_id`:
        the manager or employee who added it works on it."""
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
                company_id,
                row.client_id,
                actor_id,
                row.title,
                description,
                row.entry_date,
                priority=priority,
                service_id=row.service_id,
                assignee_id=assignee_id,
            )
        except Exception:  # noqa: BLE001 - the entry is saved even if the ticket fails
            logger.warning("Could not create the calendar ticket", exc_info=True)
            return None
        if task_id is not None:
            self.repository.set_task(company_id, entry_id, task_id)
        if assignee_id is not None and task_id is not None:
            self._tell_admins_of_team_ticket(company_id, row, task_id, actor_id)
        else:
            self._tell_admins(company_id, row, task_id, actor_id)
        return task_id

    def _tell_admins_of_team_ticket(
        self, company_id: UUID, row: CalendarEntryRow, task_id: UUID, actor_id: UUID
    ) -> None:
        """A manager or employee added a video and took the ticket (owner request 2026-11-26).
        No approval is needed, but every admin gets a starred mail from that person (so it is in
        Primary) and a bell. Never raises."""
        try:
            from app.repositories.chat_repository import ChatRepository
            from app.services.mail_service import mail_card, mail_service

            admins = [user for user in ChatRepository().admin_ids(company_id) if user != actor_id]
            task = self.tasks.get_task(company_id, task_id)
            if not admins or task is None:
                return
            who = task.assignee_name or "A team member"
            when = row.entry_date.strftime("%a %d %b %Y")
            notes = []
            if task.client_price_reason:
                notes.append(f"{row.client_name} has no rate for {task.service_name} yet: set it.")
            if task.assignee_type == "MANAGER" and task.commission_final is None:
                notes.append(
                    f"{who} has no fixed rate for {task.service_name}: set the commission."
                )
            subject = f"Priority: {who} created a ticket for {row.client_name}: {row.title}"
            body = (
                f'{who} added "{row.title}" ({task.service_name}) to {row.client_name}\'s content '
                f"calendar for {when} and is working on it ({task.code}). No approval is needed."
            )
            mail_service.system(
                company_id,
                admins,
                subject,
                body + ("\n\n" + "\n".join(notes) if notes else ""),
                link=f"/tasks?task={task_id}",
                kind="TASK",
                notify=True,
                sender_id=actor_id,
                starred=True,
                card=mail_card(
                    "New ticket from the team",
                    lines=[body, *notes],
                    rows=[
                        ("Client", row.client_name),
                        ("Video", row.title),
                        ("Service", task.service_name),
                        ("Due", when),
                        ("Working on it", who),
                        ("Ticket", task.code),
                    ],
                    action="Open the ticket",
                    status="Priority",
                ),
            )
        except Exception:  # noqa: BLE001
            logger.warning("Could not tell the admins about a team ticket", exc_info=True)

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
                once_key=f"calendar-task:{row.id}:{task_id}",
                notify=True,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Could not tell the admins about a calendar item", exc_info=True)

    def open_missing_tickets(self, limit: int = 20) -> int:
        """Catch-up (owner report 2026-11-19): an upcoming item a client added that has no task
        yet gets one, so it always reaches the admin's To assign list. Only the client's own
        entries (not rows the admin imported from a spreadsheet). Runs in the background loop."""
        from app.database.connectivity import database_pool

        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.company_id, e.id, e.created_by_id
                FROM content_calendar_entries e JOIN clients c ON c.id = e.client_id
                WHERE e.task_id IS NULL AND NOT e.no_post AND c.status::text = 'ACTIVE'
                  AND e.created_by_id = c.user_id
                  AND e.entry_date >= CURRENT_DATE - 1
                  AND e.created_at < (NOW() AT TIME ZONE 'UTC') - INTERVAL '1 minute'
                ORDER BY e.created_at LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
        opened = 0
        for company_id, entry_id, actor_id in rows:
            if self._open_ticket(company_id, entry_id, actor_id) is not None:
                opened += 1
        return opened

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
        if after.service_id is not None and after.service_id != before.service_id:
            if after.task_status == "PENDING":
                self.tickets.change_calendar_ticket_service(
                    company_id, after.task_id, actor_id, after.service_id
                )
            elif after.task_status in ("ASSIGNED", "IN_PROGRESS", "SUBMITTED", "REVIEW"):
                self._reopen_for_new_service(company_id, after, actor_id)

    def _reopen_for_new_service(
        self, company_id: UUID, entry: CalendarEntryRow, actor_id: UUID
    ) -> None:
        """The service of an assigned video changed (owner decision 2026-11-26): its ticket is
        cancelled (history kept) and a new one, with the new service's prices, goes to the
        admin's To assign list. Whoever had the old ticket is told."""
        old_task = entry.task_id
        if old_task is None:
            return
        service = entry.service_name or "another service"
        assignee = self.tickets.cancel_calendar_ticket(
            company_id,
            old_task,
            actor_id,
            note=f"Service changed to {service}; a new ticket was opened.",
            assigned_ok=True,
        )
        self.repository.set_task(company_id, entry.id, None)
        self._open_ticket(company_id, entry.id, actor_id)
        if assignee is not None:
            notification_service.notify(
                company_id,
                [assignee],
                "task.cancelled",
                f"TSK-{entry.task_number or 0:04d} was cancelled",
                f'The service of "{entry.title}" changed to {service}, so this ticket was '
                "cancelled. The admin will assign the new one.",
                "/tasks",
                {"task_id": str(old_task)},
                exclude=actor_id,
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
        self._check_service(company_id, request.service_id)
        entry_id = self.repository.create(
            company_id, client.id, context.user_id, request.model_dump(exclude={"client_id"})
        )
        self._open_ticket(company_id, entry_id, context.user_id, request.priority)
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
        values = request.model_dump(exclude_none=True)
        self._check_service_change(company_id, before, values)
        self.repository.update(company_id, entry_id, values)
        self._follow(company_id, before, context.user_id)
        return entry_response(self._entry(company_id, entry_id, None))

    def _cancel_entry_ticket(
        self, company_id: UUID, row: CalendarEntryRow, actor_id: UUID, note: str
    ) -> None:
        """A removed entry takes its unfinished ticket with it (owner report 2026-11-28: the
        ticket stayed in My Tasks). Delivered work stays: it is billed."""
        if row.task_id is None or row.task_status in (None, "CANCELLED", *BILLABLE_STATUSES):
            return
        had = self.tickets.cancel_calendar_ticket(
            company_id, row.task_id, actor_id, note=note, assigned_ok=True
        )
        notification_service.notify(
            company_id,
            [had, *notification_service.admins(company_id)],
            "task.cancelled",
            f"Task cancelled: {row.task_title or row.title}",
            f"{row.title} was removed from {row.client_name}'s calendar.",
            "/tasks",
            {"task_id": str(row.task_id)},
            exclude=actor_id,
        )

    def admin_delete(self, context: AuthContext, entry_id: UUID) -> None:
        company_id = self._admin(context, "DELETE")
        row = self._entry(company_id, entry_id, None)
        self._cancel_entry_ticket(
            company_id, row, context.user_id, "Removed from the client's calendar by the Admin."
        )
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
        self._check_service(company_id, request.service_id)
        entry_id = self.repository.create(
            company_id, client.id, context.user_id, request.model_dump(exclude={"client_id"})
        )
        task_id = self._open_ticket(company_id, entry_id, context.user_id, request.priority)
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
        self._check_service_change(company_id, before, changes, client=True)
        self.repository.update(company_id, entry_id, changes)
        self._follow(company_id, before, context.user_id)
        return entry_response(self._entry(company_id, entry_id, client.id))

    def client_delete(self, context: AuthContext, entry_id: UUID) -> None:
        """A client can remove an entry until the video is delivered (owner rule 2026-11-28: also
        while it is in progress); its ticket is cancelled. Delivered work cannot be removed."""
        company_id, client = self._client(context)
        row = self._entry(company_id, entry_id, client.id)
        if row.task_status in BILLABLE_STATUSES:
            raise AuthenticationError(
                409,
                "ENTRY_DELIVERED",
                "This video is already delivered, so it cannot be removed.",
            )
        self._cancel_entry_ticket(
            company_id, row, context.user_id, "Removed from the calendar by the client."
        )
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

    # -- managers and employees with client access (owner request 2026-11-26) ------------------

    def _staff_levels(self, context: AuthContext) -> tuple[UUID, dict[UUID, str]]:
        if (
            context.role not in ("COMPANY_MANAGER", "COMPANY_EMPLOYEE")
            or context.company_id is None
        ):
            raise AuthenticationError(
                403, "STAFF_ONLY", "This calendar is for managers and employees."
            )
        return context.company_id, self.access.levels_for_user(context.company_id, context.user_id)

    @staticmethod
    def _require_level(levels: dict[UUID, str], client_id: UUID, needed: str) -> None:
        if client_id not in levels:
            # Same answer for "no such client" and "not yours".
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        if not access_allows(levels[client_id], needed):
            raise AuthenticationError(
                403,
                "CREATE_ACCESS_REQUIRED",
                "You can view this client's calendar but not add to it.",
            )

    def staff_list(
        self,
        context: AuthContext,
        client_id: UUID | None,
        start: date | None,
        end: date | None,
    ) -> CalendarListResponse:
        """The content calendars of the clients this person has access to."""
        company_id, levels = self._staff_levels(context)
        self._check_range(start, end)
        if client_id is not None:
            self._require_level(levels, client_id, "READ")
        return CalendarListResponse(
            items=[
                entry_response(row)
                for row in self.repository.list(
                    company_id, client_id, start, end, client_ids=list(levels)
                )
            ]
        )

    def staff_services(self, context: AuthContext, client_id: UUID) -> list[CalendarServiceOption]:
        company_id, levels = self._staff_levels(context)
        self._require_level(levels, client_id, "READ")
        return self._service_options(company_id, client_id)

    def staff_create(
        self, context: AuthContext, request: CalendarEntryCreate
    ) -> CalendarEntryResponse:
        """Create access: the video goes into the client's own calendar (shown in the team colour)
        and its ticket is assigned to the person who added it."""
        company_id, levels = self._staff_levels(context)
        if request.client_id is None:
            raise AuthenticationError(422, "CLIENT_REQUIRED", "Choose the client for this video.")
        self._require_level(levels, request.client_id, "CREATE")
        if request.no_post:
            raise AuthenticationError(
                422, "VIDEO_ONLY", "Add a video; no-post days are set by the client or admin."
            )
        self._check_service(company_id, request.service_id)
        entry_id = self.repository.create(
            company_id,
            request.client_id,
            context.user_id,
            request.model_dump(exclude={"client_id"}),
        )
        self._open_ticket(
            company_id, entry_id, context.user_id, request.priority, assignee_id=context.user_id
        )
        notification_service.notify(
            company_id,
            [notification_service.client_user(company_id, request.client_id)],
            "calendar.entry",
            "New calendar entry",
            f"{request.title} on {request.entry_date:%d %b %Y} was added to your calendar.",
            "/calendar",
            {"entry_id": str(entry_id)},
            exclude=context.user_id,
        )
        return entry_response(self._entry(company_id, entry_id, None))

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
