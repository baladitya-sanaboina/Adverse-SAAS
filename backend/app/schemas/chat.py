"""Chat shapes (Phase 14)."""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ConversationType = Literal["DIRECT", "GROUP", "CLIENT"]
ChatRole = Literal["ADMIN", "MANAGER", "EMPLOYEE", "CLIENT"]
ChatStatus = Literal["AVAILABLE", "BUSY", "AWAY"]
ShownStatus = Literal["AVAILABLE", "BUSY", "AWAY", "OFFLINE"]


class ChatPerson(BaseModel):
    id: UUID
    name: str
    role: ChatRole
    image: str | None
    online: bool
    # What the person set, or OFFLINE while they do not have the app open.
    status: ShownStatus


class ChatMemberResponse(ChatPerson):
    last_read_at: datetime | None


class ChatLastMessage(BaseModel):
    id: UUID
    sender_id: UUID
    sender_name: str
    preview: str
    created_at: datetime


class ConversationResponse(BaseModel):
    id: UUID
    type: ConversationType
    title: str
    client_id: UUID | None
    client_name: str | None
    created_by_id: UUID
    last_message: ChatLastMessage | None
    unread: int
    members: list[ChatMemberResponse]
    created_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    unread_total: int


class ChatAttachmentResponse(BaseModel):
    id: UUID
    file_name: str
    mime_type: str
    size_bytes: int


class ChatReplyRef(BaseModel):
    id: UUID
    sender_name: str
    preview: str


class ChatReactionResponse(BaseModel):
    emoji: str
    user_ids: list[UUID]


class ChatMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender: ChatPerson
    body: str
    reply_to: ChatReplyRef | None
    attachments: list[ChatAttachmentResponse]
    reactions: list[ChatReactionResponse] = []
    edited: bool
    deleted: bool
    created_at: datetime


class ChatMessagesResponse(BaseModel):
    items: list[ChatMessageResponse]
    has_more: bool


class DirectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class GroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    member_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Give the group a name.")
        return value


class GroupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    member_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=100)


class MessageEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=4000)


class ReadResponse(BaseModel):
    last_read_at: datetime
    unread_total: int


class RoomRequest(BaseModel):
    """A client room the admin creates: the client, the admin and the staff they pick."""

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    title: str = Field(min_length=1, max_length=120)
    member_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Give the room a name.")
        return value


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ChatStatus


class PeopleResponse(BaseModel):
    me: ChatPerson
    people: list[ChatPerson]


REACTIONS = ("👍", "❤️", "😂", "🎉", "✅", "👀", "🙏", "🔥")


class ReactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emoji: str

    @field_validator("emoji")
    @classmethod
    def known(cls, value: str) -> str:
        if value not in REACTIONS:
            raise ValueError("Pick one of the offered reactions.")
        return value


# -- calls and meetings (owner request 2026-11-14) -------------------------------------------

CallKind = Literal["AUDIO", "VIDEO"]


class CallParticipantResponse(BaseModel):
    id: UUID
    name: str
    role: ChatRole
    image: str | None
    joined_at: datetime


class CallResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    kind: CallKind
    started_by_id: UUID
    started_at: datetime
    ended_at: datetime | None
    participants: list[CallParticipantResponse]
    code: str | None = None


class ActiveCallResponse(BaseModel):
    call: CallResponse | None


class CallStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CallKind = "VIDEO"


class SignalRequest(BaseModel):
    """WebRTC offer, answer or ICE candidate for one other person in the call."""

    model_config = ConfigDict(extra="forbid")

    to_user_id: UUID
    kind: Literal["offer", "answer", "ice"]
    data: dict[str, object]

    @field_validator("data")
    @classmethod
    def small(cls, value: dict[str, object]) -> dict[str, object]:
        if len(json.dumps(value, default=str)) > 20_000:
            raise ValueError("Signal too large.")
        return value


class MeetingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    notes: str = Field(default="", max_length=1000)
    starts_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    kind: CallKind = "VIDEO"

    @field_validator("title", "notes")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("starts_at")
    @classmethod
    def with_zone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Send the start time with its time zone.")
        return value


class MeetingResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    conversation_type: ConversationType
    conversation_title: str
    title: str
    notes: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    kind: CallKind
    created_by_id: UUID
    created_by_name: str
    code: str | None = None


class MeetingListResponse(BaseModel):
    items: list[MeetingResponse]


# -- meet links and the lobby (owner request 2026-11-14) ---------------------------------------

AdmissionStatus = Literal["WAITING", "ADMITTED", "DENIED"]


class MeetLinkResponse(BaseModel):
    code: str


class WaitingPersonResponse(BaseModel):
    id: UUID
    name: str
    role: ChatRole
    image: str | None
    requested_at: datetime


class LobbyResponse(BaseModel):
    items: list[WaitingPersonResponse]


class MeetInfoResponse(BaseModel):
    """What a meet link page needs. People outside the chat only see the chat's name, who is in
    the call, and their own place in the lobby."""

    code: str
    title: str
    type: ConversationType
    member: bool
    conversation_id: UUID | None
    kind: CallKind
    live: bool
    in_call: list[str]
    host_name: str | None
    call: CallResponse | None
    admission: AdmissionStatus | None
    can_admit: bool


class AdmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admit: bool


class CallMessageRequest(BaseModel):
    """A line typed in the call's chat panel (text only)."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=4000)
