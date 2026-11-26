"""Chat (Phase 14, owner decisions 2026-11-14).

- Client rooms: the admin creates them by hand for a client, names them and picks the managers
  and employees in them; the client's login is always in. Admins see every client room.
- Direct chats: any two of the team (admin, managers, employees), and a client with the admin
  (managers and employees talk to clients only in rooms).
- Groups: the admin and managers create them and add any of the team; never clients.
- Everyone sets a status (Available, Busy, Away); people without the app open show as Offline.
Every rule is enforced here, on the server.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.repositories.chat_repository import (
    AttachmentRow,
    ChatRepository,
    ConversationRow,
    MemberRow,
    MessageRow,
    PersonRef,
)
from app.schemas.authentication import AuthContext
from app.schemas.chat import (
    ChatAttachmentResponse,
    ChatCallLine,
    ChatLastMessage,
    ChatMemberResponse,
    ChatMessageResponse,
    ChatMessagesResponse,
    ChatPerson,
    ChatReactionResponse,
    ChatReplyRef,
    ConversationListResponse,
    ConversationResponse,
    DirectRequest,
    GroupRequest,
    GroupUpdateRequest,
    PeopleResponse,
    ReadResponse,
    RoomRequest,
    StatusRequest,
)
from app.services import realtime
from app.services.authentication_service import AuthenticationError
from app.services.notification_service import notification_service
from app.services.task_file_storage import TaskFileStorage

logger = logging.getLogger(__name__)

# Owner request 2026-11-15: chat files must be under 1 MB.
MAX_CHAT_FILE_BYTES = 1024 * 1024
MAX_FILES = 10
ROLES = {
    "COMPANY_ADMIN": "ADMIN",
    "COMPANY_MANAGER": "MANAGER",
    "COMPANY_EMPLOYEE": "EMPLOYEE",
    "COMPANY_CLIENT": "CLIENT",
}
STAFF = ("ADMIN", "MANAGER", "EMPLOYEE")


def _utc(moment: datetime | None) -> datetime | None:
    """Database times are stored without a zone (UTC); send them with one."""
    if moment is None:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _preview(body: str, files: int, deleted: bool) -> str:
    if deleted:
        return "This message was deleted"
    text = " ".join(body.split())
    if text:
        return text[:120]
    return "Attachment" if files == 1 else f"{files} attachments"


class ChatService:
    def __init__(
        self, repository: ChatRepository | None = None, storage: TaskFileStorage | None = None
    ) -> None:
        self.repository = repository or ChatRepository()
        self.storage = storage or TaskFileStorage(
            Path("private-storage/chat-files"), MAX_CHAT_FILE_BYTES
        )

    # -- who is asking -------------------------------------------------------------------------

    @staticmethod
    def _me(context: AuthContext) -> tuple[UUID, str]:
        role = ROLES.get(context.role)
        if role is None or context.company_id is None:
            raise AuthenticationError(403, "CHAT_NOT_AVAILABLE", "Chat is not available here.")
        return context.company_id, role

    def _people(self, rows: list[PersonRef]) -> list[ChatPerson]:
        ids = [row.id for row in rows]
        online = realtime.online(ids)
        statuses = self.repository.statuses(ids)
        return [
            ChatPerson(
                id=row.id,
                name=row.name,
                role=ROLES.get(row.role, "EMPLOYEE"),
                image=row.image,
                online=row.id in online,
                status=statuses.get(row.id, "AVAILABLE") if row.id in online else "OFFLINE",
            )
            for row in rows
        ]

    def _visible(
        self, company_id: UUID, role: str, user_id: UUID, conversation_id: UUID
    ) -> ConversationRow:
        row = self.repository.get_conversation(company_id, conversation_id, user_id)
        if row is None or not (
            self.repository.is_member(conversation_id, user_id)
            or (row.type == "CLIENT" and role == "ADMIN")
        ):
            raise AuthenticationError(404, "CHAT_NOT_FOUND", "Chat not found.")
        return row

    def _audience(self, company_id: UUID, row: ConversationRow) -> list[UUID]:
        """Everyone who should get live events for a chat."""
        ids = [member.user_id for member in self.repository.members([row.id])]
        if row.type == "CLIENT":
            ids += self.repository.admin_ids(company_id)
        return list(dict.fromkeys(ids))

    # -- shaping -------------------------------------------------------------------------------

    def _conversations(
        self, rows: list[ConversationRow], user_id: UUID
    ) -> list[ConversationResponse]:
        members = self.repository.members([row.id for row in rows])
        people = {
            person.id: person
            for person in self._people(
                list(
                    {
                        m.user_id: PersonRef(m.user_id, m.name, m.role, m.image) for m in members
                    }.values()
                )
            )
        }
        by_chat: dict[UUID, list[MemberRow]] = {}
        for member in members:
            by_chat.setdefault(member.conversation_id, []).append(member)
        result = []
        for row in rows:
            chat_members = [
                ChatMemberResponse(
                    **people[m.user_id].model_dump(), last_read_at=_utc(m.last_read_at)
                )
                for m in by_chat.get(row.id, [])
                if m.user_id in people
            ]
            if row.type == "DIRECT":
                other = next((m for m in chat_members if m.id != user_id), None)
                title = other.name if other else "Direct chat"
            else:
                title = row.title or (row.client_name or "Chat")
            last = None
            if row.last_id is not None and row.last_sender_id is not None and row.last_created_at:
                last = ChatLastMessage(
                    id=row.last_id,
                    sender_id=row.last_sender_id,
                    sender_name=row.last_sender_name or "",
                    preview=_preview(row.last_body or "", row.last_files, row.last_deleted),
                    created_at=_utc(row.last_created_at),
                )
            result.append(
                ConversationResponse(
                    id=row.id,
                    type=row.type,
                    title=title,
                    client_id=row.client_id,
                    client_name=row.client_name,
                    created_by_id=row.created_by_id,
                    last_message=last,
                    unread=row.unread,
                    members=chat_members,
                    created_at=_utc(row.created_at),
                )
            )
        return result

    def _messages(self, rows: list[MessageRow]) -> list[ChatMessageResponse]:
        files: dict[UUID, list[AttachmentRow]] = {}
        for attachment in self.repository.attachments([row.id for row in rows]):
            files.setdefault(attachment.message_id, []).append(attachment)
        reacted: dict[UUID, dict[str, list[UUID]]] = {}
        for message_id, user_id, emoji in self.repository.reactions([row.id for row in rows]):
            reacted.setdefault(message_id, {}).setdefault(emoji, []).append(user_id)
        senders = {
            person.id: person
            for person in self._people(
                list(
                    {
                        r.sender_id: PersonRef(
                            r.sender_id, r.sender_name, r.sender_role, r.sender_image
                        )
                        for r in rows
                    }.values()
                )
            )
        }
        return [
            ChatMessageResponse(
                id=row.id,
                conversation_id=row.conversation_id,
                sender=senders[row.sender_id],
                body="" if row.deleted_at else row.body,
                reply_to=(
                    ChatReplyRef(
                        id=row.reply_to_id,
                        sender_name=row.reply_sender_name or "",
                        preview=_preview(row.reply_body or "", 1, row.reply_deleted),
                    )
                    if row.reply_to_id
                    else None
                ),
                attachments=[
                    ChatAttachmentResponse(
                        id=item.id,
                        file_name=item.file_name,
                        mime_type=item.mime_type,
                        size_bytes=item.size_bytes,
                    )
                    for item in files.get(row.id, [])
                ],
                reactions=(
                    []
                    if row.deleted_at
                    else [
                        ChatReactionResponse(emoji=emoji, user_ids=users)
                        for emoji, users in reacted.get(row.id, {}).items()
                    ]
                ),
                edited=row.edited_at is not None and row.deleted_at is None,
                deleted=row.deleted_at is not None,
                created_at=_utc(row.created_at),
                call=(
                    ChatCallLine(
                        id=row.call_id,
                        kind=row.call_kind or "VIDEO",
                        event="ENDED" if row.call_event == "ENDED" else "STARTED",
                        running=row.call_ended_at is None,
                        joined=[UUID(str(user)) for user in (row.call_joined or [])],
                    )
                    if row.call_id
                    else None
                ),
            )
            for row in rows
        ]

    def _unread_total(self, company_id: UUID, user_id: UUID, role: str) -> int:
        return sum(
            row.unread
            for row in self.repository.list_conversations(company_id, user_id, role == "ADMIN")
        )

    # -- people and status ---------------------------------------------------------------------

    def people(self, context: AuthContext) -> PeopleResponse:
        """Who this person may start a direct chat with (plus themselves, for the status)."""
        company_id, role = self._me(context)
        if role == "CLIENT":
            rows = self.repository.people(company_id, ("COMPANY_ADMIN",))
        elif role == "ADMIN":
            rows = self.repository.people(
                company_id,
                ("COMPANY_ADMIN", "COMPANY_MANAGER", "COMPANY_EMPLOYEE", "COMPANY_CLIENT"),
            )
        else:
            rows = self.repository.people(
                company_id, ("COMPANY_ADMIN", "COMPANY_MANAGER", "COMPANY_EMPLOYEE")
            )
        me = self.repository.person(company_id, context.user_id)
        if me is None:
            raise AuthenticationError(404, "USER_NOT_FOUND", "Your account was not found.")
        shaped = self._people([me, *[row for row in rows if row.id != context.user_id]])
        return PeopleResponse(me=shaped[0], people=shaped[1:])

    def unread(self, context: AuthContext) -> int:
        """Unread messages across all my chats (the floating chat button's badge)."""
        company_id, role = self._me(context)
        return self._unread_total(company_id, context.user_id, role)

    def set_status(self, context: AuthContext, request: StatusRequest) -> PeopleResponse:
        self._me(context)
        self.repository.set_status(context.user_id, request.status)
        return self.people(context)

    # -- conversations -------------------------------------------------------------------------

    def list_chats(self, context: AuthContext) -> ConversationListResponse:
        company_id, role = self._me(context)
        rows = self.repository.list_conversations(company_id, context.user_id, role == "ADMIN")
        return ConversationListResponse(
            items=self._conversations(rows, context.user_id),
            unread_total=sum(row.unread for row in rows),
        )

    def get(self, context: AuthContext, conversation_id: UUID) -> ConversationResponse:
        company_id, role = self._me(context)
        row = self._visible(company_id, role, context.user_id, conversation_id)
        return self._conversations([row], context.user_id)[0]

    def direct(self, context: AuthContext, request: DirectRequest) -> ConversationResponse:
        company_id, role = self._me(context)
        other = self.repository.person(company_id, request.user_id)
        if other is None or other.id == context.user_id:
            raise AuthenticationError(404, "PERSON_NOT_FOUND", "Person not found.")
        other_role = ROLES.get(other.role)
        allowed = (role in STAFF and other_role in STAFF) or {role, other_role} == {
            "ADMIN",
            "CLIENT",
        }
        if not allowed:
            raise AuthenticationError(
                403,
                "DIRECT_NOT_ALLOWED",
                "Clients chat with the team in their rooms; only the admin chats with them directly.",
            )
        key = ":".join(sorted([str(context.user_id), str(other.id)]))
        conversation_id = self.repository.direct(
            company_id, key, [context.user_id, other.id], context.user_id
        )
        return self.get(context, conversation_id)

    def _staff_ids(self, company_id: UUID, ids: list[UUID]) -> list[UUID]:
        staff = {
            person.id
            for person in self.repository.people(
                company_id, ("COMPANY_ADMIN", "COMPANY_MANAGER", "COMPANY_EMPLOYEE")
            )
        }
        wrong = [user_id for user_id in ids if user_id not in staff]
        if wrong:
            raise AuthenticationError(
                422, "MEMBER_NOT_STAFF", "Only admins, managers and employees can be added here."
            )
        return list(dict.fromkeys(ids))

    def _added(
        self,
        company_id: UUID,
        user_ids: list[UUID],
        actor_id: UUID,
        conversation_id: UUID,
        title: str,
    ) -> None:
        actor = self.repository.person(company_id, actor_id)
        notification_service.notify(
            company_id,
            user_ids,
            "chat.added",
            f"You were added to {title}",
            f"{actor.name if actor else 'Someone'} added you to this chat.",
            f"/chat?c={conversation_id}",
            {"conversation_id": str(conversation_id)},
            exclude=actor_id,
        )

    def sync_client_group(
        self, company_id: UUID, client_id: UUID, staff_ids: list[UUID], actor_id: UUID
    ) -> None:
        """The client's automatic group (owner request 2026-11-26): the client's login, every
        admin and the staff with access to the client. Made the first time; afterwards people
        who lost access leave it and new ones join."""
        client = self.repository.client_user(company_id, client_id)
        if client is None:
            return
        name, login = client
        title = f"{name} team"[:120]
        members = list(
            dict.fromkeys(
                [*self.repository.admin_ids(company_id), *staff_ids, *([login] if login else [])]
            )
        )
        conversation_id = self.repository.client_group_id(company_id, client_id)
        if conversation_id is None:
            conversation_id = self.repository.create_client_group(
                company_id, client_id, title, members, actor_id
            )
            before: set[UUID] = set()
        else:
            before = {member.user_id for member in self.repository.members([conversation_id])}
            self.repository.update_group(conversation_id, None, members)
        self._added(
            company_id,
            [user_id for user_id in members if user_id not in before],
            actor_id,
            conversation_id,
            title,
        )
        realtime.publish(
            list({*before, *members}),
            "chat.conversation",
            {"conversation_id": str(conversation_id)},
        )

    def react(self, context: AuthContext, message_id: UUID, emoji: str) -> ChatMessageResponse:
        company_id, _, _, row = self._own_message(context, message_id)
        self.repository.toggle_reaction(message_id, context.user_id, emoji)
        return self._changed(company_id, row, message_id)

    def group(self, context: AuthContext, request: GroupRequest) -> ConversationResponse:
        company_id, role = self._me(context)
        if role not in ("ADMIN", "MANAGER"):
            raise AuthenticationError(
                403, "GROUP_NOT_ALLOWED", "Only the admin and managers create groups."
            )
        members = self._staff_ids(company_id, [context.user_id, *request.member_ids])
        conversation_id = self.repository.create_group(
            company_id, request.title, members, context.user_id
        )
        created = self.get(context, conversation_id)
        realtime.publish(members, "chat.conversation", {"conversation_id": str(conversation_id)})
        self._added(company_id, members, context.user_id, conversation_id, request.title)
        return created

    def room(self, context: AuthContext, request: RoomRequest) -> ConversationResponse:
        company_id, role = self._me(context)
        if role != "ADMIN":
            raise AuthenticationError(
                403, "ROOM_ADMIN_ONLY", "Only the admin creates client rooms."
            )
        client = self.repository.client_user(company_id, request.client_id)
        if client is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client not found.")
        staff = self._staff_ids(company_id, [context.user_id, *request.member_ids])
        members = staff + ([client[1]] if client[1] else [])
        conversation_id = self.repository.create_group(
            company_id, request.title, members, context.user_id, client_id=request.client_id
        )
        created = self.get(context, conversation_id)
        realtime.publish(
            [*members, *self.repository.admin_ids(company_id)],
            "chat.conversation",
            {"conversation_id": str(conversation_id)},
        )
        self._added(company_id, members, context.user_id, conversation_id, request.title)
        return created

    def update(
        self, context: AuthContext, conversation_id: UUID, request: GroupUpdateRequest
    ) -> ConversationResponse:
        company_id, role = self._me(context)
        row = self._visible(company_id, role, context.user_id, conversation_id)
        if row.type == "DIRECT":
            raise AuthenticationError(422, "DIRECT_FIXED", "A direct chat has no name or members.")
        if row.type == "CLIENT" and role != "ADMIN":
            raise AuthenticationError(
                403, "ROOM_ADMIN_ONLY", "Only the admin changes client rooms."
            )
        if row.type == "GROUP" and role != "ADMIN" and row.created_by_id != context.user_id:
            raise AuthenticationError(
                403, "GROUP_OWNER_ONLY", "Only the person who made the group can change it."
            )
        before = self._audience(company_id, row)
        members = None
        if request.member_ids is not None:
            keep = [row.created_by_id]
            if row.type == "CLIENT" and row.client_id:
                client = self.repository.client_user(company_id, row.client_id)
                if client and client[1]:
                    keep.append(client[1])
            staff = self._staff_ids(
                company_id,
                [user_id for user_id in [*keep, *request.member_ids] if user_id not in keep[1:]],
            )
            members = list(dict.fromkeys([*staff, *keep]))
        title = request.title.strip() if request.title else None
        already = {member.user_id for member in self.repository.members([conversation_id])}
        self.repository.update_group(conversation_id, title, members)
        if members:
            self._added(
                company_id,
                [user_id for user_id in members if user_id not in already],
                context.user_id,
                conversation_id,
                title or row.title,
            )
        updated = self.get(context, conversation_id)
        realtime.publish(
            [*before, *self._audience(company_id, row)],
            "chat.conversation",
            {"conversation_id": str(conversation_id)},
        )
        return updated

    # -- messages ------------------------------------------------------------------------------

    def messages(
        self, context: AuthContext, conversation_id: UUID, before: datetime | None, limit: int
    ) -> ChatMessagesResponse:
        company_id, role = self._me(context)
        self._visible(company_id, role, context.user_id, conversation_id)
        naive = before.astimezone(timezone.utc).replace(tzinfo=None) if before else None
        rows = self.repository.messages(conversation_id, naive, limit + 1)
        more = len(rows) > limit
        return ChatMessagesResponse(items=self._messages(rows[-limit:]), has_more=more)

    def send(
        self,
        context: AuthContext,
        conversation_id: UUID,
        body: str,
        reply_to_id: UUID | None,
        uploads: list[UploadFile],
    ) -> ChatMessageResponse:
        company_id, role = self._me(context)
        row = self._visible(company_id, role, context.user_id, conversation_id)
        text = body.strip()
        uploads = [upload for upload in uploads if upload.filename]
        if not text and not uploads:
            raise AuthenticationError(422, "EMPTY_MESSAGE", "Write a message or attach a file.")
        if len(text) > 4000:
            raise AuthenticationError(422, "MESSAGE_TOO_LONG", "Messages can be 4,000 characters.")
        if len(uploads) > MAX_FILES:
            raise AuthenticationError(422, "TOO_MANY_FILES", f"Attach at most {MAX_FILES} files.")
        if reply_to_id is not None:
            original = self.repository.message(company_id, reply_to_id)
            if original is None or original.conversation_id != conversation_id:
                raise AuthenticationError(404, "MESSAGE_NOT_FOUND", "That message was not found.")
        stored = []
        try:
            for upload in uploads:
                saved = self.storage.save(company_id, conversation_id, upload)
                stored.append(
                    (saved.file_name, saved.storage_path, saved.mime_type, saved.size_bytes)
                )
        except Exception:
            for _, path, _, _ in stored:
                self._remove(path)
            raise
        message_id = self.repository.add_message(
            company_id, conversation_id, context.user_id, text, reply_to_id, stored
        )
        member = self.repository.is_member(conversation_id, context.user_id)
        self.repository.mark_read(conversation_id, context.user_id, member)
        saved_row = self.repository.message(company_id, message_id)
        assert saved_row is not None
        message = self._messages([saved_row])[0]
        event = {
            "conversation_id": str(conversation_id),
            "title": row.title or row.client_name or "",
            "type": row.type,
            "message": message.model_dump(mode="json"),
        }
        others = [u for u in self._audience(company_id, row) if u != context.user_id]
        realtime.publish(others, "chat.message", event)
        sender = message.sender.name
        preview = text[:120] or ("Sent a file" if len(stored) == 1 else f"Sent {len(stored)} files")
        notification_service.notify_chat(
            company_id,
            others,
            conversation_id,
            sender if row.type == "DIRECT" else (row.title or row.client_name or "Chat"),
            preview if row.type == "DIRECT" else f"{sender}: {preview}",
        )
        # The sender's other tabs update too, but must not chime.
        realtime.publish([context.user_id], "chat.message", {**event, "own": True})
        return message

    def _own_message(
        self, context: AuthContext, message_id: UUID
    ) -> tuple[UUID, str, MessageRow, ConversationRow]:
        company_id, role = self._me(context)
        message = self.repository.message(company_id, message_id)
        if message is None:
            raise AuthenticationError(404, "MESSAGE_NOT_FOUND", "Message not found.")
        row = self._visible(company_id, role, context.user_id, message.conversation_id)
        if message.deleted_at is not None:
            raise AuthenticationError(409, "MESSAGE_DELETED", "This message was deleted.")
        return company_id, role, message, row

    def edit(self, context: AuthContext, message_id: UUID, body: str) -> ChatMessageResponse:
        company_id, _, message, row = self._own_message(context, message_id)
        if message.sender_id != context.user_id:
            raise AuthenticationError(
                403, "NOT_YOUR_MESSAGE", "You can only edit your own messages."
            )
        text = body.strip()
        if not text:
            raise AuthenticationError(422, "EMPTY_MESSAGE", "A message cannot be empty.")
        self.repository.edit_message(message_id, text)
        return self._changed(company_id, row, message_id)

    def delete(self, context: AuthContext, message_id: UUID) -> ChatMessageResponse:
        company_id, role, message, row = self._own_message(context, message_id)
        if message.sender_id != context.user_id and role != "ADMIN":
            raise AuthenticationError(
                403, "NOT_YOUR_MESSAGE", "You can only delete your own messages."
            )
        for path in self.repository.delete_message(message_id):
            self._remove(path)
        return self._changed(company_id, row, message_id)

    def _changed(
        self, company_id: UUID, row: ConversationRow, message_id: UUID
    ) -> ChatMessageResponse:
        updated = self.repository.message(company_id, message_id)
        assert updated is not None
        message = self._messages([updated])[0]
        realtime.publish(
            self._audience(company_id, row),
            "chat.message.updated",
            {"conversation_id": str(row.id), "message": message.model_dump(mode="json")},
        )
        return message

    def read(self, context: AuthContext, conversation_id: UUID) -> ReadResponse:
        company_id, role = self._me(context)
        row = self._visible(company_id, role, context.user_id, conversation_id)
        member = self.repository.is_member(conversation_id, context.user_id)
        stamp = _utc(self.repository.mark_read(conversation_id, context.user_id, member))
        assert stamp is not None
        notification_service.read_chat(company_id, context.user_id, conversation_id)
        realtime.publish(
            [user_id for user_id in self._audience(company_id, row) if user_id != context.user_id],
            "chat.read",
            {
                "conversation_id": str(conversation_id),
                "user_id": str(context.user_id),
                "last_read_at": stamp.isoformat(),
            },
        )
        return ReadResponse(
            last_read_at=stamp, unread_total=self._unread_total(company_id, context.user_id, role)
        )

    def typing(self, context: AuthContext, conversation_id: UUID) -> None:
        company_id, role = self._me(context)
        row = self._visible(company_id, role, context.user_id, conversation_id)
        me = self.repository.person(company_id, context.user_id)
        realtime.publish(
            [user_id for user_id in self._audience(company_id, row) if user_id != context.user_id],
            "chat.typing",
            {
                "conversation_id": str(conversation_id),
                "user_id": str(context.user_id),
                "name": me.name if me else "",
            },
        )

    def attachment(self, context: AuthContext, attachment_id: UUID) -> tuple[Path, str, str]:
        company_id, role = self._me(context)
        found = self.repository.attachment(attachment_id)
        if found is None:
            raise AuthenticationError(404, "FILE_NOT_FOUND", "File not found.")
        attachment, conversation_id = found
        self._visible(company_id, role, context.user_id, conversation_id)
        return (
            self.storage.path_for(attachment.storage_path),
            attachment.file_name,
            attachment.mime_type,
        )

    def search(self, context: AuthContext, text: str) -> ChatMessagesResponse:
        company_id, role = self._me(context)
        text = text.strip()
        if len(text) < 2:
            return ChatMessagesResponse(items=[], has_more=False)
        rows = self.repository.search(company_id, context.user_id, role == "ADMIN", text, 30)
        return ChatMessagesResponse(items=self._messages(rows), has_more=False)

    def _remove(self, path: str) -> None:
        try:
            self.storage.path_for(path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001 - a missing file must not fail the request
            logger.warning("Could not remove a chat file", exc_info=True)


chat_service = ChatService()
