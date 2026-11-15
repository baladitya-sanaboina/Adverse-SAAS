"""Chat calls and scheduled meetings (owner request 2026-11-14: "like Google Meet / Zoom").

Audio and video go straight between browsers (WebRTC, one connection per pair of people, which
suits the small calls an agency has). The server decides who may call, keeps who is in the call,
relays the WebRTC offers, answers and network candidates, and writes the call into the chat.
Who may call, join or schedule follows the chat's own rules (chat_service._visible).

Meet links (owner decisions 2026-11-14): every chat has one link, /call/<code>. Chat members who
open it join straight away. Anyone else in the same company waits in a lobby until the call's
host or an admin who is in the call admits them; that admission is for that one call only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.repositories.call_repository import CallRepository, CallRow, MeetingRow
from app.repositories.chat_repository import ConversationRow
from app.repositories.finance_repository import FinanceRepository
from app.schemas.authentication import AuthContext
from app.schemas.chat import (
    ActiveCallResponse,
    CallParticipantResponse,
    CallResponse,
    CallStartRequest,
    ChatMessageResponse,
    ChatMessagesResponse,
    LobbyResponse,
    MeetInfoResponse,
    MeetingListResponse,
    MeetingRequest,
    MeetingResponse,
    MeetLinkResponse,
    SignalRequest,
    WaitingPersonResponse,
)
from app.services import realtime
from app.services.authentication_service import AuthenticationError
from app.services.chat_service import ROLES, ChatService, chat_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# The call's chat panel shows at most this many lines from the call.
CALL_CHAT_LIMIT = 200


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _minutes(start: datetime, end: datetime) -> str:
    seconds = max(0, int((end - start).total_seconds()))
    if seconds < 60:
        return f"{seconds} sec"
    return f"{seconds // 60} min"


class CallService:
    def __init__(
        self,
        chat: ChatService | None = None,
        repository: CallRepository | None = None,
        finance: FinanceRepository | None = None,
    ) -> None:
        self.chat = chat or chat_service
        self.repository = repository or CallRepository()
        self.finance = finance or FinanceRepository()

    # -- helpers -------------------------------------------------------------------------------

    def _access(
        self, context: AuthContext, conversation_id: UUID
    ) -> tuple[UUID, str, ConversationRow]:
        company_id, role = self.chat._me(context)
        row = self.chat._visible(company_id, role, context.user_id, conversation_id)
        return company_id, role, row

    def _call(self, call: CallRow) -> CallResponse:
        return CallResponse(
            id=call.id,
            conversation_id=call.conversation_id,
            kind=call.kind,
            started_by_id=call.started_by_id,
            started_at=_utc(call.started_at),
            ended_at=_utc(call.ended_at) if call.ended_at else None,
            participants=[
                CallParticipantResponse(
                    id=seat.user_id,
                    name=seat.name,
                    role=ROLES.get(seat.role, "EMPLOYEE"),
                    image=seat.image,
                    joined_at=_utc(seat.joined_at),
                )
                for seat in self.repository.seats(call.id)
            ],
            code=call.meet_code,
        )

    def _post(self, company_id: UUID, row: ConversationRow, sender_id: UUID, body: str) -> None:
        """Write a call line into the chat ("Video call started") and send it live."""
        message_id = self.chat.repository.add_message(company_id, row.id, sender_id, body, None, [])
        saved = self.chat.repository.message(company_id, message_id)
        if saved is None:
            return
        message = self.chat._messages([saved])[0]
        realtime.publish(
            self.chat._audience(company_id, row),
            "chat.message",
            {
                "conversation_id": str(row.id),
                "title": row.title or row.client_name or "",
                "type": row.type,
                "message": message.model_dump(mode="json"),
                "call": True,
            },
        )

    def _call_audience(self, company_id: UUID, row: ConversationRow, call: CallRow) -> list[UUID]:
        """The chat's audience plus people admitted to this call from the lobby."""
        people = self.chat._audience(company_id, row) + self.repository.admitted(call.id)
        return list(dict.fromkeys(people))

    def _update(self, company_id: UUID, row: ConversationRow, call: CallRow) -> CallResponse:
        shaped = self._call(call)
        realtime.publish(
            self._call_audience(company_id, row, call),
            "call.update",
            {"conversation_id": str(row.id), "call": shaped.model_dump(mode="json")},
        )
        return shaped

    def _member(self, company_id: UUID, role: str, user_id: UUID, row: ConversationRow) -> bool:
        return self.chat.repository.is_member(row.id, user_id) or (
            row.type == "CLIENT" and role == "ADMIN"
        )

    def _live(
        self, call_id: UUID, context: AuthContext
    ) -> tuple[UUID, str, ConversationRow, CallRow]:
        """The call, if this person is in its chat or was admitted to it from the lobby."""
        call = self.repository.get(call_id)
        if call is None:
            raise AuthenticationError(404, "CALL_NOT_FOUND", "Call not found.")
        company_id, role = self.chat._me(context)
        row = self.chat.repository.get_conversation(
            company_id, call.conversation_id, context.user_id
        )
        if row is None or not (
            self._member(company_id, role, context.user_id, row)
            or self.repository.admission(call.id, context.user_id) == "ADMITTED"
        ):
            raise AuthenticationError(404, "CALL_NOT_FOUND", "Call not found.")
        return company_id, role, row, call

    def _can_admit(self, role: str, user_id: UUID, call: CallRow) -> bool:
        """Host or an admin, and in the call right now."""
        seated = any(seat.user_id == user_id for seat in self.repository.seats(call.id))
        return seated and (user_id == call.started_by_id or role == "ADMIN")

    def _admitters(self, company_id: UUID, call: CallRow) -> list[UUID]:
        admins = set(self.chat.repository.admin_ids(company_id))
        return [
            seat.user_id
            for seat in self.repository.seats(call.id)
            if seat.user_id == call.started_by_id or seat.user_id in admins
        ]

    def _finish(self, company_id: UUID, row: ConversationRow, call: CallRow) -> None:
        """End the call once: write its length into the chat and tell people who missed it."""
        if not self.repository.end(call.id):
            return
        ended = self.repository.get(call.id) or call
        label = "Video call" if call.kind == "VIDEO" else "Call"
        self._post(
            company_id,
            row,
            call.started_by_id,
            f"📞 {label} ended · {_minutes(call.started_at, ended.ended_at or datetime.utcnow())}",
        )
        joined = self.repository.ever_joined(call.id)
        starter = self.chat.repository.person(company_id, call.started_by_id)
        missed = [user for user in self.chat._audience(company_id, row) if user not in joined]
        where = "" if row.type == "DIRECT" else f" in {row.title or row.client_name or 'a chat'}"
        notification_service.notify(
            company_id,
            missed,
            "chat.missed_call",
            f"Missed {label.lower()} from {starter.name if starter else 'someone'}",
            f"The call{where} has ended.",
            f"/chat?c={row.id}",
            {"conversation_id": str(row.id), "call_id": str(call.id)},
        )
        self._update(company_id, row, ended)

    # -- calls ---------------------------------------------------------------------------------

    def start(
        self, context: AuthContext, conversation_id: UUID, request: CallStartRequest
    ) -> CallResponse:
        """Start a call in the chat, or join the one already running there."""
        company_id, _, row = self._access(context, conversation_id)
        code = self.repository.meet_code(conversation_id)
        call_id, created = self.repository.start(
            company_id, conversation_id, context.user_id, request.kind
        )
        self.repository.join(call_id, context.user_id)
        call = self.repository.get(call_id)
        assert call is not None
        if created:
            me = self.chat.repository.person(company_id, context.user_id)
            label = "Video call" if call.kind == "VIDEO" else "Call"
            self._post(company_id, row, context.user_id, f"📞 {label} started")
            realtime.publish(
                [u for u in self.chat._audience(company_id, row) if u != context.user_id],
                "call.ring",
                {
                    "call_id": str(call.id),
                    "conversation_id": str(row.id),
                    "kind": call.kind,
                    "title": (
                        (me.name if me else "")
                        if row.type == "DIRECT"
                        else (row.title or row.client_name or "Chat")
                    ),
                    "from": {"id": str(context.user_id), "name": me.name if me else ""},
                    "code": code,
                },
            )
        return self._update(company_id, row, call)

    def active(self, context: AuthContext, conversation_id: UUID) -> ActiveCallResponse:
        company_id, _, row = self._access(context, conversation_id)
        call = self.repository.active(conversation_id)
        if call is None:
            return ActiveCallResponse(call=None)
        self.repository.prune(call.id)
        if not self.repository.seats(call.id):
            self._finish(company_id, row, call)
            return ActiveCallResponse(call=None)
        return ActiveCallResponse(call=self._call(call))

    def join(self, context: AuthContext, call_id: UUID) -> CallResponse:
        company_id, _, row, call = self._live(call_id, context)
        if call.ended_at is not None:
            raise AuthenticationError(409, "CALL_ENDED", "This call has ended.")
        self.repository.join(call_id, context.user_id)
        return self._update(company_id, row, call)

    def leave(self, context: AuthContext, call_id: UUID) -> ActiveCallResponse:
        company_id, _, row, call = self._live(call_id, context)
        self.repository.leave(call_id, context.user_id)
        self.repository.prune(call_id)
        if call.ended_at is None and not self.repository.seats(call_id):
            self._finish(company_id, row, call)
            return ActiveCallResponse(call=None)
        if call.ended_at is None:
            self._update(company_id, row, call)
        return ActiveCallResponse(call=None)

    def ping(self, context: AuthContext, call_id: UUID) -> CallResponse:
        company_id, _, row, call = self._live(call_id, context)
        if call.ended_at is not None or not self.repository.ping(call_id, context.user_id):
            raise AuthenticationError(409, "NOT_IN_CALL", "You are no longer in this call.")
        before = len(self.repository.seats(call_id))
        self.repository.prune(call_id)
        if len(self.repository.seats(call_id)) != before:
            return self._update(company_id, row, call)
        return self._call(call)

    def decline(self, context: AuthContext, call_id: UUID) -> None:
        company_id, _, row, call = self._live(call_id, context)
        me = self.chat.repository.person(company_id, context.user_id)
        realtime.publish(
            [seat.user_id for seat in self.repository.seats(call_id)],
            "call.declined",
            {
                "call_id": str(call_id),
                "conversation_id": str(row.id),
                "user_id": str(context.user_id),
                "name": me.name if me else "",
                "direct": row.type == "DIRECT",
            },
        )

    def signal(self, context: AuthContext, call_id: UUID, request: SignalRequest) -> None:
        """Pass a WebRTC offer, answer or candidate to another person in the same call."""
        _, _, _, call = self._live(call_id, context)
        seats = {seat.user_id for seat in self.repository.seats(call_id)}
        if (
            call.ended_at is not None
            or context.user_id not in seats
            or request.to_user_id not in seats
        ):
            raise AuthenticationError(409, "NOT_IN_CALL", "Both people must be in the call.")
        realtime.publish(
            [request.to_user_id],
            "call.signal",
            {
                "call_id": str(call_id),
                "from_user_id": str(context.user_id),
                "kind": request.kind,
                "data": request.data,
            },
        )

    # -- chat inside the call (owner request 2026-11-15) ---------------------------------------

    def _seated(self, call: CallRow, user_id: UUID) -> None:
        if call.ended_at is not None or not any(
            seat.user_id == user_id for seat in self.repository.seats(call.id)
        ):
            raise AuthenticationError(409, "NOT_IN_CALL", "You are no longer in this call.")

    def messages(self, context: AuthContext, call_id: UUID) -> ChatMessagesResponse:
        """The chat lines written since the call started, for the people in the call."""
        _, _, row, call = self._live(call_id, context)
        self._seated(call, context.user_id)
        since = _naive_utc(_utc(call.started_at))
        rows = [
            item
            for item in self.chat.repository.messages(row.id, None, CALL_CHAT_LIMIT)
            if _naive_utc(_utc(item.created_at)) >= since
        ]
        return ChatMessagesResponse(items=self.chat._messages(rows), has_more=False)

    def say(self, context: AuthContext, call_id: UUID, body: str) -> ChatMessageResponse:
        """Write in the call's chat. The line is saved in the chat too, so members see it later;
        people admitted from the lobby (not members) can write while they are in the call."""
        company_id, role, row, call = self._live(call_id, context)
        self._seated(call, context.user_id)
        text = body.strip()
        if not text:
            raise AuthenticationError(422, "EMPTY_MESSAGE", "Write a message.")
        if self._member(company_id, role, context.user_id, row):
            message = self.chat.send(context, row.id, text, None, [])
        else:
            message_id = self.chat.repository.add_message(
                company_id, row.id, context.user_id, text, None, []
            )
            saved = self.chat.repository.message(company_id, message_id)
            if saved is None:
                raise AuthenticationError(500, "MESSAGE_NOT_SAVED", "The message was not saved.")
            message = self.chat._messages([saved])[0]
            members = self.chat._audience(company_id, row)
            realtime.publish(
                members,
                "chat.message",
                {
                    "conversation_id": str(row.id),
                    "title": row.title or row.client_name or "",
                    "type": row.type,
                    "message": message.model_dump(mode="json"),
                },
            )
            notification_service.notify_chat(
                company_id,
                members,
                row.id,
                row.title or row.client_name or "Chat",
                f"{message.sender.name}: {text[:120]}",
            )
        realtime.publish(
            [seat.user_id for seat in self.repository.seats(call_id)],
            "call.chat",
            {"call_id": str(call_id), "message": message.model_dump(mode="json")},
        )
        return message

    # -- meet links and the lobby -------------------------------------------------------------

    def link(self, context: AuthContext, conversation_id: UUID) -> MeetLinkResponse:
        """The chat's meet link code (members only)."""
        self._access(context, conversation_id)
        return MeetLinkResponse(code=self.repository.meet_code(conversation_id))

    def _title(self, company_id: UUID, row: ConversationRow, user_id: UUID) -> str:
        if row.type != "DIRECT":
            return row.title or row.client_name or "Chat"
        others = [
            member.name
            for member in self.chat.repository.members([row.id])
            if member.user_id != user_id
        ]
        return " & ".join(others) or "Call"

    def meet(self, context: AuthContext, code: str) -> MeetInfoResponse:
        """What the meet link page shows: join straight away, ask to join, or wait."""
        company_id, role = self.chat._me(context)
        conversation_id = self.repository.by_code(company_id, code.strip().lower())
        row = (
            self.chat.repository.get_conversation(company_id, conversation_id, context.user_id)
            if conversation_id
            else None
        )
        if row is None:
            raise AuthenticationError(404, "MEET_NOT_FOUND", "This meeting link does not exist.")
        member = self._member(company_id, role, context.user_id, row)
        call = self.repository.active(row.id)
        if call is not None:
            self.repository.prune(call.id)
            if not self.repository.seats(call.id):
                self._finish(company_id, row, call)
                call = None
        admission = (
            self.repository.admission(call.id, context.user_id)
            if call is not None and not member
            else None
        )
        seats = self.repository.seats(call.id) if call else []
        host = self.chat.repository.person(company_id, call.started_by_id) if call else None
        allowed = member or admission == "ADMITTED"
        return MeetInfoResponse(
            code=code.strip().lower(),
            title=self._title(company_id, row, context.user_id),
            type=row.type,
            member=member,
            conversation_id=row.id if member else None,
            kind=call.kind if call else "VIDEO",
            live=call is not None,
            in_call=[seat.name for seat in seats],
            host_name=host.name if host else None,
            call=self._call(call) if call and allowed else None,
            admission=admission,
            can_admit=bool(call and self._can_admit(role, context.user_id, call)),
        )

    def knock(self, context: AuthContext, code: str) -> MeetInfoResponse:
        """Ask to join the running call (or say "still here" while waiting)."""
        info = self.meet(context, code)
        if info.member:
            return info
        company_id, _ = self.chat._me(context)
        conversation_id = self.repository.by_code(company_id, info.code)
        call = self.repository.active(conversation_id) if conversation_id else None
        if call is None:
            raise AuthenticationError(
                409, "CALL_NOT_STARTED", "The call has not started yet. Wait for the host."
            )
        status, new = self.repository.knock(call.id, context.user_id)
        if new:
            me = self.chat.repository.person(company_id, context.user_id)
            realtime.publish(
                self._admitters(company_id, call),
                "call.knock",
                {
                    "call_id": str(call.id),
                    "user_id": str(context.user_id),
                    "name": me.name if me else "",
                    "role": ROLES.get(me.role, "EMPLOYEE") if me else "EMPLOYEE",
                },
            )
        return self.meet(context, code)

    def withdraw(self, context: AuthContext, code: str) -> None:
        company_id, _ = self.chat._me(context)
        conversation_id = self.repository.by_code(company_id, code.strip().lower())
        call = self.repository.active(conversation_id) if conversation_id else None
        if call is None:
            return
        self.repository.withdraw(call.id, context.user_id)
        realtime.publish(self._admitters(company_id, call), "call.lobby", {"call_id": str(call.id)})

    def lobby(self, context: AuthContext, call_id: UUID) -> LobbyResponse:
        _, role, _, call = self._live(call_id, context)
        if not self._can_admit(role, context.user_id, call):
            return LobbyResponse(items=[])
        return LobbyResponse(
            items=[
                WaitingPersonResponse(
                    id=person.user_id,
                    name=person.name,
                    role=ROLES.get(person.role, "EMPLOYEE"),
                    image=person.image,
                    requested_at=_utc(person.requested_at),
                )
                for person in self.repository.waiting(call.id)
            ]
        )

    def decide(self, context: AuthContext, call_id: UUID, user_id: UUID, admit: bool) -> None:
        company_id, role, _, call = self._live(call_id, context)
        if call.ended_at is not None:
            raise AuthenticationError(409, "CALL_ENDED", "This call has ended.")
        if not self._can_admit(role, context.user_id, call):
            raise AuthenticationError(
                403, "HOST_ONLY", "Only the host or an admin in the call can let people in."
            )
        status = "ADMITTED" if admit else "DENIED"
        if not self.repository.decide(call.id, user_id, status, context.user_id):
            raise AuthenticationError(404, "NOT_WAITING", "That person is no longer waiting.")
        realtime.publish(
            [user_id],
            "call.admission",
            {"call_id": str(call.id), "code": call.meet_code, "status": status},
        )
        realtime.publish(self._admitters(company_id, call), "call.lobby", {"call_id": str(call.id)})

    # -- meetings ------------------------------------------------------------------------------

    def _meeting(self, row: MeetingRow) -> MeetingResponse:
        starts = _utc(row.starts_at)
        return MeetingResponse(
            id=row.id,
            conversation_id=row.conversation_id,
            conversation_type=row.conversation_type,
            conversation_title=row.conversation_title or row.client_name or "",
            title=row.title,
            notes=row.notes,
            starts_at=starts,
            ends_at=starts + timedelta(minutes=row.duration_minutes),
            duration_minutes=row.duration_minutes,
            kind=row.kind,
            created_by_id=row.created_by_id,
            created_by_name=row.created_by_name,
            code=row.meet_code or self.repository.meet_code(row.conversation_id),
        )

    def schedule(
        self, context: AuthContext, conversation_id: UUID, request: MeetingRequest
    ) -> MeetingResponse:
        company_id, _, row = self._access(context, conversation_id)
        if request.starts_at < datetime.now(timezone.utc) - timedelta(minutes=5):
            raise AuthenticationError(422, "MEETING_IN_PAST", "Pick a time that has not passed.")
        meeting_id = self.repository.create_meeting(
            company_id,
            conversation_id,
            context.user_id,
            request.title,
            request.notes,
            _naive_utc(request.starts_at),
            request.duration_minutes,
            request.kind,
        )
        saved = self.repository.meeting(company_id, meeting_id)
        assert saved is not None
        meeting = self._meeting(saved)
        try:
            zone = ZoneInfo(self.finance.company_timezone(company_id))
        except Exception:  # noqa: BLE001
            zone = ZoneInfo("UTC")
        local = meeting.starts_at.astimezone(zone)
        audience = self.chat._audience(company_id, row)
        notification_service.notify(
            company_id,
            audience,
            "chat.meeting",
            f"Meeting: {meeting.title}",
            f"{local:%a %d %b, %I:%M %p} · {meeting.duration_minutes} min · join from the chat or your calendar.",
            f"/chat?c={conversation_id}",
            {"conversation_id": str(conversation_id), "meeting_id": str(meeting_id)},
            exclude=context.user_id,
        )
        realtime.publish(audience, "meeting.update", {"conversation_id": str(conversation_id)})
        self._meeting_mail(company_id, context.user_id, row, meeting, local, audience)
        return meeting

    def _meeting_mail(
        self,
        company_id: UUID,
        organiser: UUID,
        row: ConversationRow,
        meeting: MeetingResponse,
        local: datetime,
        audience: list[UUID],
    ) -> None:
        """Internal mail (owner request 2026-11-15): everyone in the chat, plus anyone in the
        company @mentioned in the title or agenda (by their full name)."""
        from app.services.mail_service import mail_service

        text = f"{meeting.title}\n{meeting.notes or ''}".lower()
        staff = self.chat.repository.people(
            company_id, ("COMPANY_ADMIN", "COMPANY_MANAGER", "COMPANY_EMPLOYEE", "COMPANY_CLIENT")
        )
        mentioned = [person.id for person in staff if f"@{person.name.lower()}" in text]
        organiser_ref = self.chat.repository.person(company_id, organiser)
        when = f"{local:%A %d %B %Y, %I:%M %p} · {meeting.duration_minutes} min"
        join = f"/call/{meeting.code}" if meeting.code else f"/chat?c={row.id}"
        body = "\n".join(
            [
                f"{organiser_ref.name if organiser_ref else 'Someone'} scheduled a "
                f"{'video' if meeting.kind == 'VIDEO' else 'voice'} meeting.",
                "",
                f"When: {when}",
                f"Chat: {row.title or row.client_name or 'Direct chat'}",
                *(["", "Agenda:", meeting.notes] if meeting.notes else []),
                "",
                "Join from the link below, the chat or your calendar.",
            ]
        )
        recipients = [user for user in dict.fromkeys([*audience, *mentioned]) if user != organiser]
        mail_service.system(
            company_id,
            recipients,
            f"Meeting: {meeting.title} · {local:%d %b, %I:%M %p}",
            body,
            join,
            "MEETING",
            once_key=f"meeting:{meeting.id}",
        )

    def meetings(
        self,
        context: AuthContext,
        start: datetime | None,
        end: datetime | None,
        conversation_id: UUID | None,
    ) -> MeetingListResponse:
        company_id, role = self.chat._me(context)
        if conversation_id is not None:
            self.chat._visible(company_id, role, context.user_id, conversation_id)
        rows = self.repository.meetings(
            company_id,
            context.user_id,
            role == "ADMIN",
            _naive_utc(start) if start and start.tzinfo else start,
            _naive_utc(end) if end and end.tzinfo else end,
            conversation_id,
        )
        return MeetingListResponse(items=[self._meeting(row) for row in rows])

    def cancel(self, context: AuthContext, meeting_id: UUID) -> None:
        company_id, role = self.chat._me(context)
        meeting = self.repository.meeting(company_id, meeting_id)
        if meeting is None:
            raise AuthenticationError(404, "MEETING_NOT_FOUND", "Meeting not found.")
        row = self.chat._visible(company_id, role, context.user_id, meeting.conversation_id)
        if meeting.created_by_id != context.user_id and role != "ADMIN":
            raise AuthenticationError(
                403, "MEETING_OWNER_ONLY", "Only the person who scheduled it can cancel it."
            )
        self.repository.cancel_meeting(meeting_id)
        realtime.publish(
            self.chat._audience(company_id, row),
            "meeting.update",
            {"conversation_id": str(meeting.conversation_id)},
        )


call_service = CallService()
