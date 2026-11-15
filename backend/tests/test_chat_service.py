"""Chat access rules (Phase 14, owner decisions 2026-11-14), without a database or Redis."""

import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.chat_repository import ConversationRow, MemberRow, MessageRow, PersonRef
from app.schemas.authentication import AuthContext
from app.schemas.chat import DirectRequest, GroupRequest, ReactionRequest, RoomRequest
from app.services.authentication_service import AuthenticationError
from app.services.chat_service import ChatService

COMPANY = uuid4()
NOW = datetime(2026, 11, 14, 10, 0)
ADMIN = PersonRef(uuid4(), "Admin", "COMPANY_ADMIN", None)
MANAGER = PersonRef(uuid4(), "Manager", "COMPANY_MANAGER", None)
EMPLOYEE = PersonRef(uuid4(), "Employee", "COMPANY_EMPLOYEE", None)
CLIENT = PersonRef(uuid4(), "Client", "COMPANY_CLIENT", None)
CLIENT_ID = uuid4()
PEOPLE = {p.id: p for p in (ADMIN, MANAGER, EMPLOYEE, CLIENT)}


def context(person: PersonRef) -> AuthContext:
    return AuthContext(
        user_id=person.id,
        role=person.role,
        company_id=COMPANY,
        user_type="company",
        session_id=uuid4(),
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )


class FakeRepository:
    def __init__(self) -> None:
        self.chats: dict[UUID, dict[str, Any]] = {}
        self.messages_: dict[UUID, MessageRow] = {}
        self.status: dict[UUID, str] = {}
        self.reacted: list[tuple[UUID, UUID, str]] = []

    # people
    def person(self, company_id: UUID, user_id: UUID) -> PersonRef | None:
        return PEOPLE.get(user_id)

    def people(self, company_id: UUID, roles: tuple[str, ...]) -> list[PersonRef]:
        return [p for p in PEOPLE.values() if p.role in roles]

    def client_user(self, company_id: UUID, client_id: UUID) -> tuple[str, UUID | None] | None:
        return ("Client Co", CLIENT.id) if client_id == CLIENT_ID else None

    def admin_ids(self, company_id: UUID) -> list[UUID]:
        return [ADMIN.id]

    def statuses(self, user_ids: list[UUID]) -> dict[UUID, str]:
        return {u: self.status[u] for u in user_ids if u in self.status}

    def set_status(self, user_id: UUID, status: str) -> None:
        self.status[user_id] = status

    # chats
    def _new(
        self,
        kind: str,
        members: list[UUID],
        creator: UUID,
        title: str = "",
        client: UUID | None = None,
    ) -> UUID:
        chat_id = uuid4()
        self.chats[chat_id] = {
            "type": kind,
            "members": set(members),
            "creator": creator,
            "title": title,
            "client": client,
        }
        return chat_id

    def direct(self, company_id: UUID, key: str, user_ids: list[UUID], actor_id: UUID) -> UUID:
        for chat_id, chat in self.chats.items():
            if chat.get("key") == key:
                return chat_id
        chat_id = self._new("DIRECT", user_ids, actor_id)
        self.chats[chat_id]["key"] = key
        return chat_id

    def create_group(self, company_id, title, user_ids, actor_id, client_id=None):  # type: ignore[no-untyped-def]
        return self._new("CLIENT" if client_id else "GROUP", user_ids, actor_id, title, client_id)

    def update_group(self, conversation_id, title, user_ids):  # type: ignore[no-untyped-def]
        if user_ids is not None:
            self.chats[conversation_id]["members"] = set(user_ids)

    def get_conversation(
        self, company_id: UUID, conversation_id: UUID, user_id: UUID
    ) -> ConversationRow | None:
        chat = self.chats.get(conversation_id)
        if chat is None:
            return None
        return ConversationRow(
            conversation_id,
            chat["type"],
            chat["title"],
            chat["client"],
            "Client Co" if chat["client"] else None,
            chat["creator"],
            None,
            NOW,
            None,
            None,
            None,
            None,
            None,
            False,
            0,
            None,
            0,
        )

    def is_member(self, conversation_id: UUID, user_id: UUID) -> bool:
        return user_id in self.chats[conversation_id]["members"]

    def members(self, conversation_ids: list[UUID]) -> list[MemberRow]:
        return [
            MemberRow(chat_id, uid, PEOPLE[uid].name, PEOPLE[uid].role, None, None)
            for chat_id in conversation_ids
            for uid in self.chats[chat_id]["members"]
        ]

    def list_conversations(
        self, company_id: UUID, user_id: UUID, admin: bool
    ) -> list[ConversationRow]:
        rows = []
        for chat_id, chat in self.chats.items():
            if user_id in chat["members"] or (chat["type"] == "CLIENT" and admin):
                row = self.get_conversation(company_id, chat_id, user_id)
                assert row is not None
                rows.append(row)
        return rows

    def mark_read(self, conversation_id: UUID, user_id: UUID, member: bool) -> datetime:
        return NOW

    # messages
    def message(self, company_id: UUID, message_id: UUID) -> MessageRow | None:
        return self.messages_.get(message_id)

    def add_message(self, company_id, conversation_id, sender_id, body, reply_to_id, files, call=None):  # type: ignore[no-untyped-def]
        message_id = uuid4()
        sender = PEOPLE[sender_id]
        self.messages_[message_id] = MessageRow(
            message_id,
            conversation_id,
            sender_id,
            sender.name,
            sender.role,
            None,
            body,
            reply_to_id,
            None,
            None,
            False,
            None,
            None,
            NOW,
            call[0] if call else None,
            call[1] if call else None,
            call[2] if call else None,
            "VIDEO" if call else None,
            None,
        )
        return message_id

    def messages(self, conversation_id: UUID, before: Any, limit: int) -> list[MessageRow]:
        return [m for m in self.messages_.values() if m.conversation_id == conversation_id]

    def attachments(self, message_ids: list[UUID]) -> list[Any]:
        return []

    def reactions(self, message_ids: list[UUID]) -> list[tuple[UUID, UUID, str]]:
        return [r for r in self.reacted if r[0] in message_ids]

    def toggle_reaction(self, message_id: UUID, user_id: UUID, emoji: str) -> None:
        key = (message_id, user_id, emoji)
        if key in self.reacted:
            self.reacted.remove(key)
        else:
            self.reacted.append(key)

    def edit_message(self, message_id: UUID, body: str) -> None:
        pass

    def delete_message(self, message_id: UUID) -> list[str]:
        return []


@patch("app.services.chat_service.notification_service")
@patch("app.services.chat_service.realtime")
class ChatRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FakeRepository()
        self.service = ChatService(self.repo, storage=object())  # type: ignore[arg-type]

    def test_direct_chat_rules(self, realtime: Any, notifications: Any) -> None:
        realtime.online.return_value = set()
        self.service.direct(context(MANAGER), DirectRequest(user_id=EMPLOYEE.id))
        self.service.direct(context(ADMIN), DirectRequest(user_id=EMPLOYEE.id))
        self.service.direct(context(EMPLOYEE), DirectRequest(user_id=ADMIN.id))
        self.service.direct(context(CLIENT), DirectRequest(user_id=ADMIN.id))
        self.service.direct(context(ADMIN), DirectRequest(user_id=CLIENT.id))
        for person in (MANAGER, EMPLOYEE):
            with self.assertRaises(AuthenticationError) as error:
                self.service.direct(context(person), DirectRequest(user_id=CLIENT.id))
            self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(AuthenticationError):
            self.service.direct(context(CLIENT), DirectRequest(user_id=MANAGER.id))

    def test_same_pair_reuses_one_direct_chat(self, realtime: Any, notifications: Any) -> None:
        realtime.online.return_value = set()
        first = self.service.direct(context(ADMIN), DirectRequest(user_id=CLIENT.id))
        second = self.service.direct(context(CLIENT), DirectRequest(user_id=ADMIN.id))
        self.assertEqual(first.id, second.id)

    def test_only_admin_creates_client_rooms_and_client_is_in_them(
        self, realtime: Any, notifications: Any
    ) -> None:
        realtime.online.return_value = set()
        with self.assertRaises(AuthenticationError) as error:
            self.service.room(
                context(MANAGER), RoomRequest(client_id=CLIENT_ID, title="Reels", member_ids=[])
            )
        self.assertEqual(error.exception.status_code, 403)
        room = self.service.room(
            context(ADMIN),
            RoomRequest(client_id=CLIENT_ID, title="Reels", member_ids=[EMPLOYEE.id]),
        )
        self.assertEqual({m.id for m in room.members}, {ADMIN.id, EMPLOYEE.id, CLIENT.id})
        self.assertEqual(room.type, "CLIENT")

    def test_people_outside_a_room_cannot_read_it_but_admins_can(
        self, realtime: Any, notifications: Any
    ) -> None:
        realtime.online.return_value = set()
        room = self.service.room(
            context(ADMIN),
            RoomRequest(client_id=CLIENT_ID, title="Reels", member_ids=[EMPLOYEE.id]),
        )
        with self.assertRaises(AuthenticationError) as error:
            self.service.messages(context(MANAGER), room.id, None, 50)
        self.assertEqual(error.exception.status_code, 404)
        self.repo.chats[room.id]["members"].discard(ADMIN.id)
        self.service.messages(context(ADMIN), room.id, None, 50)  # admins see every room
        self.assertNotIn(room.id, {c.id for c in self.service.list_chats(context(MANAGER)).items})

    def test_admin_and_managers_make_groups_employees_and_clients_do_not(
        self, realtime: Any, notifications: Any
    ) -> None:
        realtime.online.return_value = set()
        group = self.service.group(
            context(MANAGER), GroupRequest(title="Edit team", member_ids=[EMPLOYEE.id])
        )
        self.assertEqual({m.id for m in group.members}, {MANAGER.id, EMPLOYEE.id})
        for person in (EMPLOYEE, CLIENT):
            with self.assertRaises(AuthenticationError) as denied:
                self.service.group(
                    context(person), GroupRequest(title="Mine", member_ids=[ADMIN.id])
                )
            self.assertEqual(denied.exception.status_code, 403)
        with self.assertRaises(AuthenticationError) as error:
            self.service.group(context(ADMIN), GroupRequest(title="Team", member_ids=[CLIENT.id]))
        self.assertEqual(error.exception.status_code, 422)

    def test_edit_and_delete_rules(self, realtime: Any, notifications: Any) -> None:
        realtime.online.return_value = set()
        room = self.service.room(
            context(ADMIN),
            RoomRequest(client_id=CLIENT_ID, title="Reels", member_ids=[EMPLOYEE.id]),
        )
        message = self.service.send(context(EMPLOYEE), room.id, "Draft ready", None, [])
        with self.assertRaises(AuthenticationError) as error:
            self.service.edit(context(CLIENT), message.id, "changed")
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(AuthenticationError):
            self.service.delete(context(CLIENT), message.id)
        self.service.edit(context(EMPLOYEE), message.id, "Draft v2 ready")
        self.service.delete(context(ADMIN), message.id)  # the admin may remove any message
        self.assertEqual(realtime.publish.call_args.args[1], "chat.message.updated")

    def test_empty_message_is_refused(self, realtime: Any, notifications: Any) -> None:
        realtime.online.return_value = set()
        chat = self.service.direct(context(MANAGER), DirectRequest(user_id=EMPLOYEE.id))
        with self.assertRaises(AuthenticationError) as error:
            self.service.send(context(MANAGER), chat.id, "   ", None, [])
        self.assertEqual(error.exception.status_code, 422)

    def test_status_shows_offline_unless_app_is_open(
        self, realtime: Any, notifications: Any
    ) -> None:
        realtime.online.return_value = {MANAGER.id}
        self.repo.status[MANAGER.id] = "BUSY"
        self.repo.status[EMPLOYEE.id] = "AVAILABLE"
        people = {p.id: p.status for p in self.service.people(context(ADMIN)).people}
        self.assertEqual(people[MANAGER.id], "BUSY")
        self.assertEqual(people[EMPLOYEE.id], "OFFLINE")

    def test_client_sees_only_admins_to_message(self, realtime: Any, notifications: Any) -> None:
        realtime.online.return_value = set()
        people = self.service.people(context(CLIENT)).people
        self.assertEqual({p.role for p in people}, {"ADMIN"})

    def test_reactions_toggle_and_show_who(self, realtime: Any, notifications: Any) -> None:
        realtime.online.return_value = set()
        chat = self.service.direct(context(MANAGER), DirectRequest(user_id=EMPLOYEE.id))
        message = self.service.send(context(MANAGER), chat.id, "Cut is ready", None, [])
        reacted = self.service.react(context(EMPLOYEE), message.id, "👍")
        self.assertEqual(
            [(r.emoji, r.user_ids) for r in reacted.reactions], [("👍", [EMPLOYEE.id])]
        )
        self.assertEqual(self.service.react(context(EMPLOYEE), message.id, "👍").reactions, [])
        with self.assertRaises(ValueError):
            ReactionRequest(emoji="💩")
        with self.assertRaises(AuthenticationError):
            self.service.react(context(CLIENT), message.id, "👍")  # not in that chat

    def test_new_message_notifies_the_others_only(self, realtime: Any, notifications: Any) -> None:
        realtime.online.return_value = set()
        room = self.service.room(
            context(ADMIN),
            RoomRequest(client_id=CLIENT_ID, title="Reels", member_ids=[EMPLOYEE.id]),
        )
        added = notifications.notify.call_args
        self.assertEqual(added.args[2], "chat.added")
        self.service.send(context(EMPLOYEE), room.id, "Draft ready", None, [])
        call = notifications.notify_chat.call_args
        self.assertEqual(set(call.args[1]), {ADMIN.id, CLIENT.id})
        self.assertEqual(call.args[3], "Reels")
        self.assertEqual(call.args[4], "Employee: Draft ready")

    def test_reading_a_chat_clears_its_notifications(
        self, realtime: Any, notifications: Any
    ) -> None:
        realtime.online.return_value = set()
        chat = self.service.direct(context(ADMIN), DirectRequest(user_id=CLIENT.id))
        self.service.read(context(CLIENT), chat.id)
        notifications.read_chat.assert_called_once_with(COMPANY, CLIENT.id, chat.id)


class ChatRoutesTest(unittest.TestCase):
    def test_every_chat_route_the_apps_call_exists(self) -> None:
        import main

        paths = set(main.app.openapi()["paths"])
        for path in (
            "/chat/unread",
            "/chat/people",
            "/chat/status",
            "/chat/conversations",
            "/chat/direct",
            "/chat/groups",
            "/chat/rooms",
            "/chat/search",
            "/chat/messages/{message_id}/reactions",
            "/chat/conversations/{conversation_id}/read",
        ):
            self.assertIn(path, paths)


if __name__ == "__main__":
    unittest.main()
