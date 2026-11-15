"""Calendar for the admin, managers and employees (owner request 2026-11-15).

Who sees what: the admin sees everyone's calendar; a manager sees their own and their team's
(the people on the tasks they monitor); an employee sees their own. Meetings planned in chats,
task deadlines and todos show up next to events.

Events can be video calls: the call lives in a chat (the direct chat with one other person, or a
new group for more), so Join works from the calendar and the call keeps its chat. Invitations,
changes and cancellations go to the people by internal mail, with a bell. Alerts go out 10
minutes before and at the start (bell; the 10-minute one also as a mail from Adverse).
"""

from __future__ import annotations

import builtins
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.repositories.agenda_repository import AgendaRepository, EventRow, TodoRow
from app.repositories.call_repository import CallRepository
from app.repositories.chat_repository import ChatRepository, PersonRef
from app.repositories.finance_repository import FinanceRepository
from app.schemas.agenda import (
    AgendaAttendee,
    AgendaEvent,
    AgendaFeed,
    AgendaMeeting,
    AgendaPerson,
    AgendaTaskDue,
    AgendaTodo,
    EventRequest,
    EventUpdate,
    RespondRequest,
    Scope,
    TodoRequest,
    TodoUpdate,
)
from app.schemas.authentication import AuthContext
from app.services import realtime
from app.services.authentication_service import AuthenticationError
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

ROLES = {"COMPANY_ADMIN": "ADMIN", "COMPANY_MANAGER": "MANAGER", "COMPANY_EMPLOYEE": "EMPLOYEE"}
STAFF = tuple(ROLES)
ALERT_MINUTES = 10
MAX_EVENT_DAYS = 14
MAX_RANGE_DAYS = 62


def _naive(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class AgendaService:
    def __init__(
        self,
        repository: AgendaRepository | None = None,
        people: ChatRepository | None = None,
        calls: CallRepository | None = None,
        finance: FinanceRepository | None = None,
    ) -> None:
        self.repository = repository or AgendaRepository()
        self.people_repository = people or ChatRepository()
        self.calls = calls or CallRepository()
        self.finance = finance or FinanceRepository()

    # -- who --------------------------------------------------------------------------------

    @staticmethod
    def _me(context: AuthContext) -> tuple[UUID, str]:
        role = ROLES.get(context.role)
        if role is None or context.company_id is None:
            raise AuthenticationError(
                403, "CALENDAR_STAFF_ONLY", "The calendar is for the admin, managers and employees."
            )
        return context.company_id, role

    def _staff(self, company_id: UUID) -> dict[UUID, PersonRef]:
        return {row.id: row for row in self.people_repository.people(company_id, STAFF)}

    def _visible(self, company_id: UUID, role: str, me: UUID) -> builtins.list[UUID] | None:
        """None: everyone (admin). Otherwise the people whose calendars I can see."""
        if role == "ADMIN":
            return None
        if role == "MANAGER":
            return list(dict.fromkeys([me, *self.repository.team(company_id, me)]))
        return [me]

    @staticmethod
    def _person(row: PersonRef) -> AgendaPerson:
        return AgendaPerson(
            id=row.id, name=row.name, role=ROLES.get(row.role, "EMPLOYEE"), image=row.image
        )

    def _zone(self, company_id: UUID) -> ZoneInfo:
        try:
            return ZoneInfo(self.finance.company_timezone(company_id))
        except Exception:  # noqa: BLE001
            return ZoneInfo("UTC")

    def _when(self, company_id: UUID, moment: datetime, all_day: bool = False) -> str:
        local = _aware(moment).astimezone(self._zone(company_id))
        return f"{local:%a %d %b}" if all_day else f"{local:%a %d %b, %I:%M %p}"

    # -- shaping ----------------------------------------------------------------------------

    def _event(self, row: EventRow, me: UUID, role: str) -> AgendaEvent:
        mine = next((response for user, _, _, response in row.attendees if user == me), None)
        return AgendaEvent(
            id=row.id,
            title=row.title,
            notes=row.notes,
            location=row.location,
            starts_at=_aware(row.starts_at),
            ends_at=_aware(row.ends_at),
            all_day=row.all_day,
            colour=row.colour,
            video=row.video,
            conversation_id=row.conversation_id,
            mail_thread_id=row.mail_thread_id,
            owner=AgendaPerson(
                id=row.owner_id, name=row.owner_name, role=ROLES.get(row.owner_role, "EMPLOYEE")
            ),
            attendees=[
                AgendaAttendee(
                    person=AgendaPerson(id=user, name=name, role=ROLES.get(code, "EMPLOYEE")),
                    response=response,
                )
                for user, name, code, response in row.attendees
            ],
            my_response=mine,
            can_edit=row.owner_id == me or role == "ADMIN",
        )

    @staticmethod
    def _todo(row: TodoRow, me: UUID) -> AgendaTodo:
        return AgendaTodo(
            id=row.id,
            title=row.title,
            notes=row.notes,
            due_date=row.due_date,
            due_at=_aware(row.due_at) if row.due_at else None,
            priority=row.priority,
            done=row.done_at is not None,
            owner=AgendaPerson(id=row.owner_id, name=row.owner_name, role="EMPLOYEE"),
            mine=row.owner_id == me,
        )

    # -- reading ----------------------------------------------------------------------------

    def feed(
        self,
        context: AuthContext,
        start: datetime,
        end: datetime,
        scope: Scope,
        person: UUID | None,
    ) -> AgendaFeed:
        company_id, role = self._me(context)
        me = context.user_id
        start, end = _naive(start), _naive(end)
        if end <= start or end - start > timedelta(days=MAX_RANGE_DAYS):
            raise AuthenticationError(422, "BAD_RANGE", "Pick a range of up to two months.")
        visible = self._visible(company_id, role, me)
        if scope == "mine" or (scope == "team" and role == "EMPLOYEE"):
            people: builtins.list[UUID] | None = [me]
        else:
            people = visible
        if person is not None:
            if visible is not None and person not in visible:
                raise AuthenticationError(
                    403, "CALENDAR_NOT_YOURS", "You cannot see that calendar."
                )
            people = [person]
        staff = self._staff(company_id)
        everyone = [
            self._person(row) for user, row in staff.items() if visible is None or user in visible
        ]
        invite = [self._person(row) for row in staff.values()]
        events = [
            self._event(row, me, role)
            for row in self.repository.events(company_id, start, end, people)
        ]
        meetings = [
            AgendaMeeting(
                id=row.id,
                conversation_id=row.conversation_id,
                title=row.title,
                starts_at=_aware(row.starts_at),
                ends_at=_aware(row.starts_at + timedelta(minutes=row.duration_minutes)),
                kind=row.kind,
                room=row.room,
            )
            for row in self.repository.meetings(
                company_id,
                start,
                end,
                None if people is None and role == "ADMIN" else (person or me),
            )
        ]
        tasks = [
            AgendaTaskDue(
                id=row.id,
                code=f"TSK-{row.number:04d}",
                title=row.title,
                due_date=row.due_date,
                status=row.status,
                assignee=row.assignee_name,
                client=row.client_name,
            )
            for row in self.repository.tasks_due(
                company_id,
                start.date(),
                end.date() + timedelta(days=1),
                people,
                me if role == "MANAGER" and scope != "mine" and person is None else None,
            )
        ]
        todos = [
            self._todo(row, me)
            for row in self.repository.todos(
                company_id, people, start.date(), end.date() + timedelta(days=1)
            )
        ]
        # People I can invite (any staff), and people whose calendars I can open.
        return AgendaFeed(
            events=events,
            meetings=meetings,
            tasks=tasks,
            todos=todos,
            people=everyone if scope != "mine" else invite,
            scope=scope,
            role=role,
        )

    def people(self, context: AuthContext) -> builtins.list[AgendaPerson]:
        company_id, _ = self._me(context)
        return [
            self._person(row)
            for row in self._staff(company_id).values()
            if row.id != context.user_id
        ]

    def todos(self, context: AuthContext) -> builtins.list[AgendaTodo]:
        company_id, _ = self._me(context)
        return [
            self._todo(row, context.user_id)
            for row in self.repository.todos(company_id, [context.user_id])
        ]

    def event_for_thread(self, context: AuthContext, thread_id: UUID) -> AgendaEvent | None:
        """The calendar event made from a mail conversation (shown on the mail)."""
        try:
            company_id, role = self._me(context)
        except AuthenticationError:
            return None
        row = self.repository.event_for_thread(company_id, thread_id)
        return self._event(row, context.user_id, role) if row else None

    def _owned(self, context: AuthContext, event_id: UUID) -> tuple[UUID, str, EventRow]:
        company_id, role = self._me(context)
        row = self.repository.event(company_id, event_id)
        if row is None:
            raise AuthenticationError(404, "EVENT_NOT_FOUND", "That event was not found.")
        return company_id, role, row

    def event(self, context: AuthContext, event_id: UUID) -> AgendaEvent:
        company_id, role, row = self._owned(context, event_id)
        me = context.user_id
        visible = self._visible(company_id, role, me)
        involved = {row.owner_id, *(user for user, _, _, _ in row.attendees)}
        if visible is not None and not involved & set(visible):
            raise AuthenticationError(404, "EVENT_NOT_FOUND", "That event was not found.")
        return self._event(row, me, role)

    # -- events -----------------------------------------------------------------------------

    def _times(self, starts: datetime, ends: datetime, all_day: bool) -> tuple[datetime, datetime]:
        starts, ends = _naive(starts), _naive(ends)
        if all_day:
            starts = starts.replace(hour=0, minute=0, second=0, microsecond=0)
            ends = max(ends, starts + timedelta(days=1))
        if ends <= starts:
            raise AuthenticationError(
                422, "EVENT_ENDS_BEFORE_START", "The end must be after the start."
            )
        if ends - starts > timedelta(days=MAX_EVENT_DAYS):
            raise AuthenticationError(
                422, "EVENT_TOO_LONG", f"An event can last at most {MAX_EVENT_DAYS} days."
            )
        return starts, ends

    def _attendees(
        self, company_id: UUID, me: UUID, ids: builtins.list[UUID]
    ) -> builtins.list[UUID]:
        staff = self._staff(company_id)
        people = [user for user in dict.fromkeys(ids) if user != me]
        if any(user not in staff for user in people):
            raise AuthenticationError(
                422,
                "ATTENDEE_NOT_STAFF",
                "Invite people from the team (admin, managers, employees).",
            )
        return people

    def _room(
        self, context: AuthContext, role: str, title: str, attendees: builtins.list[UUID]
    ) -> UUID:
        """The chat where the video call happens."""
        from app.schemas.chat import DirectRequest, GroupRequest
        from app.services.chat_service import chat_service

        if not attendees:
            raise AuthenticationError(422, "VIDEO_NEEDS_PEOPLE", "Invite someone to a video call.")
        if len(attendees) == 1:
            return chat_service.direct(context, DirectRequest(user_id=attendees[0])).id
        if role not in ("ADMIN", "MANAGER"):
            raise AuthenticationError(
                403,
                "GROUP_NOT_ALLOWED",
                "Only the admin and managers host group video calls. Invite one person, or ask them.",
            )
        return chat_service.group(context, GroupRequest(title=title[:120], member_ids=attendees)).id

    def _meeting(
        self,
        company_id: UUID,
        me: UUID,
        conversation_id: UUID,
        title: str,
        notes: str,
        starts: datetime,
        ends: datetime,
    ) -> UUID:
        minutes = max(5, min(480, int((ends - starts).total_seconds() // 60)))
        return self.calls.create_meeting(
            company_id, conversation_id, me, title[:160], notes[:1000], starts, minutes, "VIDEO"
        )

    def create_event(self, context: AuthContext, request: EventRequest) -> AgendaEvent:
        company_id, role = self._me(context)
        me = context.user_id
        starts, ends = self._times(request.starts_at, request.ends_at, request.all_day)
        attendees = self._attendees(company_id, me, request.attendee_ids)
        fields: dict[str, Any] = {
            "title": request.title,
            "notes": request.notes,
            "location": request.location,
            "starts_at": starts,
            "ends_at": ends,
            "all_day": request.all_day,
            "colour": request.colour,
            "video": request.video and not request.all_day,
            "mail_thread_id": request.mail_thread_id,
        }
        if fields["video"]:
            conversation = self._room(context, role, request.title, attendees)
            fields["conversation_id"] = conversation
            fields["meeting_id"] = self._meeting(
                company_id, me, conversation, request.title, request.notes, starts, ends
            )
        event_id = self.repository.create_event(company_id, me, fields)
        self.repository.set_attendees(event_id, attendees)
        row = self.repository.event(company_id, event_id)
        assert row is not None
        if attendees and request.invite:
            self._tell(company_id, me, row, attendees, "Invitation")
        self._changed([me, *attendees], event_id)
        return self._event(row, me, role)

    def update_event(
        self, context: AuthContext, event_id: UUID, request: EventUpdate
    ) -> AgendaEvent:
        company_id, role, row = self._owned(context, event_id)
        me = context.user_id
        if row.owner_id != me and role != "ADMIN":
            raise AuthenticationError(
                403, "EVENT_NOT_YOURS", "Only the organiser or the admin changes it."
            )
        changes: dict[str, Any] = {
            key: value
            for key, value in request.model_dump(exclude_unset=True).items()
            if key not in ("attendee_ids", "starts_at", "ends_at", "all_day") and value is not None
        }
        all_day = request.all_day if request.all_day is not None else row.all_day
        if request.starts_at or request.ends_at or request.all_day is not None:
            starts, ends = self._times(
                request.starts_at or _aware(row.starts_at),
                request.ends_at or _aware(row.ends_at),
                all_day,
            )
            if (starts, ends, all_day) != (row.starts_at, row.ends_at, row.all_day):
                changes.update(starts_at=starts, ends_at=ends, all_day=all_day)
        before = [user for user, _, _, _ in row.attendees]
        after = before
        if request.attendee_ids is not None:
            after = self._attendees(company_id, row.owner_id, request.attendee_ids)
            self.repository.set_attendees(event_id, after)
        if row.video and "starts_at" in changes and row.conversation_id:
            # The chat meeting follows the new time.
            if row.meeting_id:
                self.calls.cancel_meeting(row.meeting_id)
            changes["meeting_id"] = self._meeting(
                company_id,
                row.owner_id,
                row.conversation_id,
                changes.get("title", row.title),
                changes.get("notes", row.notes),
                changes["starts_at"],
                changes["ends_at"],
            )
        self.repository.update_event(event_id, changes)
        updated = self.repository.event(company_id, event_id)
        assert updated is not None
        added = [user for user in after if user not in before]
        if added:
            self._tell(company_id, me, updated, added, "Invitation")
        kept = [user for user in after if user in before]
        if kept and ({"starts_at", "title", "location"} & set(changes)):
            self._tell(company_id, me, updated, kept, "Updated")
        removed = [user for user in before if user not in after]
        if removed:
            self._tell(company_id, me, updated, removed, "Removed")
        self._changed([row.owner_id, *before, *after], event_id)
        return self._event(updated, me, role)

    def cancel_event(self, context: AuthContext, event_id: UUID) -> None:
        company_id, role, row = self._owned(context, event_id)
        me = context.user_id
        if row.owner_id != me and role != "ADMIN":
            raise AuthenticationError(
                403, "EVENT_NOT_YOURS", "Only the organiser or the admin cancels it."
            )
        self.repository.cancel_event(event_id)
        if row.meeting_id:
            self.calls.cancel_meeting(row.meeting_id)
        people = [user for user, _, _, _ in row.attendees]
        if people:
            self._tell(company_id, me, row, people, "Cancelled")
        self._changed([row.owner_id, *people], event_id)

    def respond(self, context: AuthContext, event_id: UUID, request: RespondRequest) -> AgendaEvent:
        company_id, role, row = self._owned(context, event_id)
        me = context.user_id
        if not self.repository.respond(event_id, me, request.response):
            raise AuthenticationError(403, "NOT_INVITED", "You are not invited to this event.")
        person = self.people_repository.person(company_id, me)
        word = {"YES": "is going to", "NO": "declined", "MAYBE": "might join"}[request.response]
        if row.owner_id != me:
            notification_service.notify(
                company_id,
                [row.owner_id],
                "agenda.response",
                f"{person.name if person else 'Someone'} {word} {row.title}",
                self._when(company_id, row.starts_at, row.all_day),
                f"/agenda?event={event_id}",
                {"event_id": str(event_id)},
            )
        self._changed([row.owner_id, me], event_id)
        updated = self.repository.event(company_id, event_id)
        assert updated is not None
        return self._event(updated, me, role)

    def _tell(
        self, company_id: UUID, sender: UUID, row: EventRow, people: builtins.list[UUID], what: str
    ) -> None:
        """Invitation / Updated / Cancelled / Removed, as a mail from the organiser (with a bell)."""
        from app.services.mail_service import mail_service

        when = self._when(company_id, row.starts_at, row.all_day)
        lines = {
            "Invitation": "You are invited.",
            "Updated": "The event changed.",
            "Cancelled": "This event was cancelled.",
            "Removed": "You were taken off this event.",
        }
        body = [
            lines[what],
            "",
            f"What: {row.title}",
            f"When: {when}"
            + ("" if row.all_day else f" to {self._when(company_id, row.ends_at)[-8:].strip()}"),
        ]
        if row.location:
            body.append(f"Where: {row.location}")
        if row.video and what != "Cancelled":
            body.append("Video call: join from the calendar or the chat.")
        if row.notes:
            body += ["", row.notes]
        if what in ("Invitation", "Updated"):
            body += ["", "Answer Yes, No or Maybe in the calendar."]
        mail_service.send_from(
            company_id,
            sender,
            people,
            f"{what}: {row.title} · {when}",
            "\n".join(body),
            link="" if what in ("Cancelled", "Removed") else f"/agenda?event={row.id}",
            kind="CALENDAR",
        )

    @staticmethod
    def _changed(people: builtins.list[UUID], event_id: UUID) -> None:
        realtime.publish(list(dict.fromkeys(people)), "agenda.changed", {"event_id": str(event_id)})

    # -- todos ------------------------------------------------------------------------------

    def _my_todo(self, context: AuthContext, todo_id: UUID) -> tuple[UUID, TodoRow]:
        company_id, _ = self._me(context)
        row = self.repository.todo(company_id, todo_id)
        if row is None or row.owner_id != context.user_id:
            raise AuthenticationError(404, "TODO_NOT_FOUND", "That todo was not found.")
        return company_id, row

    def create_todo(self, context: AuthContext, request: TodoRequest) -> AgendaTodo:
        company_id, _ = self._me(context)
        due_at = _naive(request.due_at) if request.due_at else None
        due_date = request.due_date
        if due_at and not due_date:
            due_date = _aware(due_at).astimezone(self._zone(company_id)).date()
        todo_id = self.repository.create_todo(
            company_id,
            context.user_id,
            {
                "title": request.title,
                "notes": request.notes,
                "due_date": due_date,
                "due_at": due_at,
                "priority": request.priority,
            },
        )
        row = self.repository.todo(company_id, todo_id)
        assert row is not None
        self._changed([context.user_id], todo_id)
        return self._todo(row, context.user_id)

    def update_todo(self, context: AuthContext, todo_id: UUID, request: TodoUpdate) -> AgendaTodo:
        company_id, row = self._my_todo(context, todo_id)
        changes: dict[str, Any] = {}
        for key in ("title", "notes", "priority"):
            value = getattr(request, key)
            if value is not None:
                changes[key] = value
        if request.clear_due:
            changes.update(due_date=None, due_at=None)
        else:
            if request.due_at is not None:
                changes["due_at"] = _naive(request.due_at)
                changes["due_date"] = (
                    request.due_date
                    or _aware(request.due_at).astimezone(self._zone(company_id)).date()
                )
            elif request.due_date is not None:
                changes.update(due_date=request.due_date, due_at=None)
        if request.done is not None:
            changes["done"] = request.done
        self.repository.update_todo(todo_id, changes)
        updated = self.repository.todo(company_id, todo_id)
        assert updated is not None
        self._changed([context.user_id], todo_id)
        return self._todo(updated, context.user_id)

    def delete_todo(self, context: AuthContext, todo_id: UUID) -> None:
        self._my_todo(context, todo_id)
        self.repository.delete_todo(todo_id)
        self._changed([context.user_id], todo_id)

    # -- alerts -----------------------------------------------------------------------------

    def run_alerts(self) -> int:
        """Called every ~20 seconds: 10 minutes before and at the start of events and todos."""
        from app.services.mail_service import mail_service

        sent = 0
        for alert in self.repository.due_alerts(ALERT_MINUTES):
            try:
                when = self._when(alert.company_id, alert.starts_at)
                link = f"/agenda?event={alert.id}" if alert.kind == "EVENT" else "/agenda"
                if alert.moment == "BEFORE":
                    title = f"In {ALERT_MINUTES} minutes: {alert.title}"
                    detail = f"{when}" + (
                        " · video call, join from the calendar" if alert.video else ""
                    )
                else:
                    title = (
                        f"Starting now: {alert.title}"
                        if alert.kind == "EVENT"
                        else f"Due now: {alert.title}"
                    )
                    detail = "Join from the calendar." if alert.video else when
                notification_service.notify(
                    alert.company_id,
                    alert.people,
                    "agenda.alert",
                    title,
                    detail,
                    link,
                    {"event_id": str(alert.id), "kind": alert.kind, "moment": alert.moment},
                )
                if alert.moment == "BEFORE":
                    mail_service.system(
                        alert.company_id,
                        alert.people,
                        title,
                        f"{alert.title}\n{when}\n\nThis is your {ALERT_MINUTES}-minute reminder.",
                        link=link,
                        kind="CALENDAR",
                    )
                sent += 1
            except Exception:  # noqa: BLE001
                logger.warning("Calendar alert failed", exc_info=True)
        return sent


agenda_service = AgendaService()
