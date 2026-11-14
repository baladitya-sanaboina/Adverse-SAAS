"""Chat shapes (Phase 14)."""

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
