"""Calls and meetings (owner request 2026-11-14), without a database or Redis."""

import unittest
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.call_repository import CallRow, MeetingRow, SeatRow, WaitingRow
from app.schemas.chat import (
    CallStartRequest,
    DirectRequest,
    MeetingRequest,
    RoomRequest,
    SignalRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.call_service import CallService
from app.services.chat_service import ChatService
from tests.test_chat_service import (
    ADMIN,
    CLIENT,
    CLIENT_ID,
    EMPLOYEE,
    MANAGER,
    PEOPLE,
    FakeRepository,
    context,
)
from tests.test_chat_service import COMPANY

NOW = datetime(2026, 11, 14, 10, 0)


class FakeCalls:
    def __init__(self) -> None:
        self.calls: dict[UUID, CallRow] = {}
        self.seats_: dict[UUID, dict[UUID, bool]] = {}  # call -> user -> in call now
        self.meetings_: dict[UUID, MeetingRow] = {}
        self.codes: dict[UUID, str] = {}  # conversation -> meet code
        self.admissions: dict[tuple[UUID, UUID], str] = {}  # (call, user) -> status

    def get(self, call_id: UUID) -> CallRow | None:
        return self.calls.get(call_id)

    def active(self, conversation_id: UUID) -> CallRow | None:
        return next(
            (
                c
                for c in self.calls.values()
                if c.conversation_id == conversation_id and not c.ended_at
            ),
            None,
        )

    def start(self, company_id, conversation_id, user_id, kind):  # type: ignore[no-untyped-def]
        running = self.active(conversation_id)
        if running:
            return running.id, False
        call = CallRow(
            uuid4(), conversation_id, kind, user_id, NOW, None, self.codes.get(conversation_id)
        )
        self.calls[call.id] = call
        self.seats_[call.id] = {}
        return call.id, True

    def join(self, call_id: UUID, user_id: UUID) -> None:
        self.seats_[call_id][user_id] = True

    def leave(self, call_id: UUID, user_id: UUID) -> None:
        self.seats_[call_id][user_id] = False

    def ping(self, call_id: UUID, user_id: UUID) -> bool:
        return self.seats_[call_id].get(user_id, False)

    def prune(self, call_id: UUID) -> None:
        pass

    def seats(self, call_id: UUID) -> list[SeatRow]:
        return [
            SeatRow(u, PEOPLE[u].name, PEOPLE[u].role, None, NOW)
            for u, here in self.seats_[call_id].items()
            if here
        ]

    def ever_joined(self, call_id: UUID) -> set[UUID]:
        return set(self.seats_[call_id])

    def end(self, call_id: UUID) -> bool:
        call = self.calls[call_id]
        if call.ended_at:
            return False
        self.calls[call_id] = CallRow(
            call.id,
            call.conversation_id,
            call.kind,
            call.started_by_id,
            call.started_at,
            NOW + timedelta(minutes=12),
            call.meet_code,
        )
        self.seats_[call_id] = {u: False for u in self.seats_[call_id]}
        return True

    def create_meeting(self, company_id, conversation_id, user_id, title, notes, starts_at, duration, kind):  # type: ignore[no-untyped-def]
        meeting = MeetingRow(
            uuid4(),
            conversation_id,
            "GROUP",
            "Team",
            None,
            title,
            notes,
            starts_at,
            duration,
            kind,
            user_id,
            PEOPLE[user_id].name,
            None,
            None,
        )
        self.meetings_[meeting.id] = meeting
        return meeting.id

    def meeting(self, company_id: UUID, meeting_id: UUID) -> MeetingRow | None:
        return self.meetings_.get(meeting_id)

    def cancel_meeting(self, meeting_id: UUID) -> None:
        self.meetings_.pop(meeting_id, None)

    # meet links and the lobby
    def meet_code(self, conversation_id: UUID) -> str:
        return self.codes.setdefault(conversation_id, f"abc-defg-{len(self.codes):03d}")

    def by_code(self, company_id: UUID, code: str) -> UUID | None:
        if company_id != COMPANY:
            return None
        return next((c for c, value in self.codes.items() if value == code), None)

    def admission(self, call_id: UUID, user_id: UUID) -> str | None:
        return self.admissions.get((call_id, user_id))

    def knock(self, call_id: UUID, user_id: UUID) -> tuple[str, bool]:
        if (call_id, user_id) in self.admissions:
            return self.admissions[(call_id, user_id)], False
        self.admissions[(call_id, user_id)] = "WAITING"
        return "WAITING", True

    def withdraw(self, call_id: UUID, user_id: UUID) -> None:
        if self.admissions.get((call_id, user_id)) == "WAITING":
            del self.admissions[(call_id, user_id)]

    def waiting(self, call_id: UUID) -> list[WaitingRow]:
        return [
            WaitingRow(u, PEOPLE[u].name, PEOPLE[u].role, None, NOW)
            for (c, u), status in self.admissions.items()
            if c == call_id and status == "WAITING"
        ]

    def decide(self, call_id: UUID, user_id: UUID, status: str, decided_by: UUID) -> bool:
        if self.admissions.get((call_id, user_id)) != "WAITING":
            return False
        self.admissions[(call_id, user_id)] = status
        return True

    def admitted(self, call_id: UUID) -> list[UUID]:
        return [u for (c, u), s in self.admissions.items() if c == call_id and s == "ADMITTED"]


class FakeFinance:
    def company_timezone(self, company_id: UUID) -> str:
        return "Asia/Kolkata"


@patch("app.services.call_service.notification_service")
@patch("app.services.call_service.realtime")
@patch("app.services.chat_service.notification_service")
@patch("app.services.chat_service.realtime")
class CallRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.chat_repo = FakeRepository()
        self.chat = ChatService(self.chat_repo, storage=object())  # type: ignore[arg-type]
        self.calls = FakeCalls()
        self.service = CallService(self.chat, self.calls, FakeFinance())  # type: ignore[arg-type]

    def room(self, chat_realtime: Any) -> Any:
        chat_realtime.online.return_value = set()
        return self.chat.room(
            context(ADMIN),
            RoomRequest(client_id=CLIENT_ID, title="Reels", member_ids=[EMPLOYEE.id]),
        )

    def test_starting_rings_the_others_and_writes_into_the_chat(
        self, chat_rt: Any, _: Any, call_rt: Any, __: Any
    ) -> None:
        room = self.room(chat_rt)
        call = self.service.start(context(EMPLOYEE), room.id, CallStartRequest(kind="VIDEO"))
        self.assertEqual([p.id for p in call.participants], [EMPLOYEE.id])
        rings = [c for c in call_rt.publish.call_args_list if c.args[1] == "call.ring"]
        self.assertEqual(set(rings[0].args[0]), {ADMIN.id, CLIENT.id})
        self.assertIn("Video call started", next(iter(self.chat_repo.messages_.values())).body)
        again = self.service.start(context(ADMIN), room.id, CallStartRequest(kind="AUDIO"))
        self.assertEqual(again.id, call.id)  # a second press joins the same call
        self.assertEqual({p.id for p in again.participants}, {EMPLOYEE.id, ADMIN.id})

    def test_people_outside_the_chat_cannot_call_or_join(
        self, chat_rt: Any, _: Any, __: Any, ___: Any
    ) -> None:
        room = self.room(chat_rt)
        with self.assertRaises(AuthenticationError):
            self.service.start(context(MANAGER), room.id, CallStartRequest())
        call = self.service.start(context(EMPLOYEE), room.id, CallStartRequest())
        with self.assertRaises(AuthenticationError):
            self.service.join(context(MANAGER), call.id)

    def test_signals_only_between_people_in_the_call(
        self, chat_rt: Any, _: Any, call_rt: Any, __: Any
    ) -> None:
        room = self.room(chat_rt)
        call = self.service.start(context(EMPLOYEE), room.id, CallStartRequest())
        offer = SignalRequest(to_user_id=CLIENT.id, kind="offer", data={"sdp": "x"})
        with self.assertRaises(AuthenticationError):
            self.service.signal(context(EMPLOYEE), call.id, offer)  # the client has not joined
        self.service.join(context(CLIENT), call.id)
        self.service.signal(context(EMPLOYEE), call.id, offer)
        sent = call_rt.publish.call_args
        self.assertEqual((sent.args[0], sent.args[1]), ([CLIENT.id], "call.signal"))

    def test_last_one_out_ends_the_call_and_others_get_missed_call(
        self, chat_rt: Any, _: Any, __: Any, notes: Any
    ) -> None:
        room = self.room(chat_rt)
        call = self.service.start(context(EMPLOYEE), room.id, CallStartRequest(kind="AUDIO"))
        self.service.join(context(CLIENT), call.id)
        self.service.leave(context(CLIENT), call.id)
        self.assertIsNone(self.calls.calls[call.id].ended_at)
        self.service.leave(context(EMPLOYEE), call.id)
        self.assertIsNotNone(self.calls.calls[call.id].ended_at)
        bodies = [m.body for m in self.chat_repo.messages_.values()]
        self.assertTrue(any(b.startswith("📞 Call ended · 12 min") for b in bodies), bodies)
        missed = notes.notify.call_args
        self.assertEqual((missed.args[1], missed.args[2]), ([ADMIN.id], "chat.missed_call"))

    def test_meetings(self, chat_rt: Any, _: Any, __: Any, notes: Any) -> None:
        chat_rt.online.return_value = set()
        chat = self.chat.direct(context(MANAGER), DirectRequest(user_id=EMPLOYEE.id))
        soon = datetime.now(timezone.utc) + timedelta(days=1)
        with self.assertRaises(AuthenticationError):
            self.service.schedule(
                context(MANAGER),
                chat.id,
                MeetingRequest(title="Late", starts_at=soon - timedelta(days=3)),
            )
        meeting = self.service.schedule(
            context(MANAGER),
            chat.id,
            MeetingRequest(title="Review", starts_at=soon, duration_minutes=45),
        )
        self.assertEqual(meeting.ends_at - meeting.starts_at, timedelta(minutes=45))
        self.assertEqual(notes.notify.call_args.args[2], "chat.meeting")
        with self.assertRaises(AuthenticationError) as denied:
            self.service.cancel(context(EMPLOYEE), meeting.id)
        self.assertEqual(denied.exception.status_code, 403)
        self.service.cancel(context(MANAGER), meeting.id)
        with self.assertRaises(ValueError):
            MeetingRequest(title="No zone", starts_at=datetime(2026, 12, 1, 10, 0))


    # -- meet links and the lobby (owner decisions 2026-11-14) ---------------------------------

    def test_member_opening_the_link_joins_straight_away(
        self, chat_rt: Any, _: Any, call_rt: Any, __: Any
    ) -> None:
        room = self.room(chat_rt)
        code = self.service.link(context(EMPLOYEE), room.id).code
        with self.assertRaises(AuthenticationError):
            self.service.link(context(MANAGER), room.id)  # outsiders cannot fetch the link
        info = self.service.meet(context(CLIENT), code)
        self.assertTrue(info.member)
        self.assertFalse(info.live)
        self.assertEqual(info.conversation_id, room.id)
        call = self.service.start(context(EMPLOYEE), room.id, CallStartRequest())
        self.assertEqual(call.code, code)
        ring = next(c for c in call_rt.publish.call_args_list if c.args[1] == "call.ring")
        self.assertEqual(ring.args[2]["code"], code)

    def test_outsider_waits_until_the_host_admits_them(
        self, chat_rt: Any, _: Any, call_rt: Any, __: Any
    ) -> None:
        room = self.room(chat_rt)
        code = self.service.link(context(EMPLOYEE), room.id).code
        with self.assertRaises(AuthenticationError) as early:
            self.service.knock(context(MANAGER), code)
        self.assertEqual(early.exception.code, "CALL_NOT_STARTED")
        call = self.service.start(context(EMPLOYEE), room.id, CallStartRequest())
        self.service.join(context(CLIENT), call.id)

        info = self.service.meet(context(MANAGER), code)
        self.assertFalse(info.member)
        self.assertIsNone(info.conversation_id)
        self.assertIsNone(info.call)  # no call details before being let in
        self.assertEqual(set(info.in_call), {"Employee", "Client"})
        with self.assertRaises(AuthenticationError):
            self.service.join(context(MANAGER), call.id)

        waiting = self.service.knock(context(MANAGER), code)
        self.assertEqual(waiting.admission, "WAITING")
        knock = next(c for c in call_rt.publish.call_args_list if c.args[1] == "call.knock")
        self.assertEqual(knock.args[0], [EMPLOYEE.id])  # host only: the client is not an admitter
        self.assertEqual([p.id for p in self.service.lobby(context(EMPLOYEE), call.id).items], [MANAGER.id])
        self.assertEqual(self.service.lobby(context(CLIENT), call.id).items, [])
        with self.assertRaises(AuthenticationError) as client_try:
            self.service.decide(context(CLIENT), call.id, MANAGER.id, True)
        self.assertEqual(client_try.exception.status_code, 403)

        self.service.decide(context(EMPLOYEE), call.id, MANAGER.id, True)
        told = next(c for c in call_rt.publish.call_args_list if c.args[1] == "call.admission")
        self.assertEqual((told.args[0], told.args[2]["status"]), ([MANAGER.id], "ADMITTED"))
        joined = self.service.join(context(MANAGER), call.id)
        self.assertIn(MANAGER.id, {p.id for p in joined.participants})
        self.service.ping(context(MANAGER), call.id)
        offer = SignalRequest(to_user_id=EMPLOYEE.id, kind="offer", data={"sdp": "x"})
        self.service.signal(context(MANAGER), call.id, offer)
        self.assertIsNotNone(self.service.meet(context(MANAGER), code).call)

    def test_admin_in_the_call_can_admit_and_denied_stays_out(
        self, chat_rt: Any, _: Any, __: Any, ___: Any
    ) -> None:
        room = self.room(chat_rt)
        code = self.service.link(context(ADMIN), room.id).code
        call = self.service.start(context(EMPLOYEE), room.id, CallStartRequest())
        self.service.knock(context(MANAGER), code)
        with self.assertRaises(AuthenticationError):
            self.service.decide(context(ADMIN), call.id, MANAGER.id, False)  # not in the call yet
        self.service.join(context(ADMIN), call.id)
        self.service.decide(context(ADMIN), call.id, MANAGER.id, False)
        self.assertEqual(self.service.knock(context(MANAGER), code).admission, "DENIED")
        with self.assertRaises(AuthenticationError):
            self.service.join(context(MANAGER), call.id)

    def test_admission_is_for_one_call_and_one_company(
        self, chat_rt: Any, _: Any, __: Any, ___: Any
    ) -> None:
        room = self.room(chat_rt)
        code = self.service.link(context(EMPLOYEE), room.id).code
        first = self.service.start(context(EMPLOYEE), room.id, CallStartRequest())
        self.service.knock(context(MANAGER), code)
        self.service.decide(context(EMPLOYEE), first.id, MANAGER.id, True)
        self.service.leave(context(EMPLOYEE), first.id)  # call ends
        second = self.service.start(context(EMPLOYEE), room.id, CallStartRequest())
        self.assertNotEqual(first.id, second.id)
        with self.assertRaises(AuthenticationError):
            self.service.join(context(MANAGER), second.id)
        self.assertIsNone(self.service.meet(context(MANAGER), code).admission)
        outsider = context(MANAGER).model_copy(update={"company_id": uuid4()})
        with self.assertRaises(AuthenticationError) as other:
            self.service.meet(outsider, code)
        self.assertEqual(other.exception.code, "MEET_NOT_FOUND")

if __name__ == "__main__":
    unittest.main()
