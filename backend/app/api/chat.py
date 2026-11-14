"""Chat (Phase 14). Every role uses the same routes; chat_service decides what each may do."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.middleware.authentication import AuthenticatedContext
from app.schemas.chat import (
    ChatMessageResponse,
    ChatMessagesResponse,
    ConversationListResponse,
    ConversationResponse,
    DirectRequest,
    GroupRequest,
    GroupUpdateRequest,
    MessageEditRequest,
    PeopleResponse,
    ReactionRequest,
    ReadResponse,
    RoomRequest,
    StatusRequest,
)
from app.schemas.registration import ErrorResponse
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in."},
    403: {"model": ErrorResponse, "description": "Not allowed."},
    404: {"model": ErrorResponse, "description": "Chat, message, person or file not found."},
    413: {"model": ErrorResponse, "description": "File too large."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "/people", response_model=PeopleResponse, summary="People I can chat with", responses=ERRORS
)
def people(context: AuthenticatedContext) -> PeopleResponse:
    return chat_service.people(context)


@router.put(
    "/status", response_model=PeopleResponse, summary="Set my chat status", responses=ERRORS
)
def set_status(request: StatusRequest, context: AuthenticatedContext) -> PeopleResponse:
    return chat_service.set_status(context, request)


@router.get(
    "/conversations", response_model=ConversationListResponse, summary="My chats", responses=ERRORS
)
def conversations(context: AuthenticatedContext) -> ConversationListResponse:
    return chat_service.list_chats(context)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="One chat",
    responses=ERRORS,
)
def conversation(conversation_id: UUID, context: AuthenticatedContext) -> ConversationResponse:
    return chat_service.get(context, conversation_id)


@router.post(
    "/direct", response_model=ConversationResponse, summary="Open a direct chat", responses=ERRORS
)
def direct(request: DirectRequest, context: AuthenticatedContext) -> ConversationResponse:
    return chat_service.direct(context, request)


@router.post(
    "/groups",
    response_model=ConversationResponse,
    status_code=201,
    summary="Create a staff group",
    responses=ERRORS,
)
def group(request: GroupRequest, context: AuthenticatedContext) -> ConversationResponse:
    return chat_service.group(context, request)


@router.post(
    "/rooms",
    response_model=ConversationResponse,
    status_code=201,
    summary="Create a client room (admin)",
    responses=ERRORS,
)
def room(request: RoomRequest, context: AuthenticatedContext) -> ConversationResponse:
    return chat_service.room(context, request)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Rename a group or room, or change its people",
    responses=ERRORS,
)
def update(
    conversation_id: UUID, request: GroupUpdateRequest, context: AuthenticatedContext
) -> ConversationResponse:
    return chat_service.update(context, conversation_id, request)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessagesResponse,
    summary="Messages, newest page first (pass before= for older)",
    responses=ERRORS,
)
def messages(
    conversation_id: UUID,
    context: AuthenticatedContext,
    before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> ChatMessagesResponse:
    return chat_service.messages(context, conversation_id, before, limit)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageResponse,
    status_code=201,
    summary="Send a message (text, a reply, files)",
    responses=ERRORS,
)
def send(
    conversation_id: UUID,
    context: AuthenticatedContext,
    body: str = Form(""),
    reply_to_id: UUID | None = Form(None),
    files: list[UploadFile] = File(default=[]),
) -> ChatMessageResponse:
    return chat_service.send(context, conversation_id, body, reply_to_id, files)


@router.patch(
    "/messages/{message_id}",
    response_model=ChatMessageResponse,
    summary="Edit my message",
    responses=ERRORS,
)
def edit(
    message_id: UUID, request: MessageEditRequest, context: AuthenticatedContext
) -> ChatMessageResponse:
    return chat_service.edit(context, message_id, request.body)


@router.delete(
    "/messages/{message_id}",
    response_model=ChatMessageResponse,
    summary="Delete a message",
    responses=ERRORS,
)
def delete(message_id: UUID, context: AuthenticatedContext) -> ChatMessageResponse:
    return chat_service.delete(context, message_id)


@router.post(
    "/messages/{message_id}/reactions",
    response_model=ChatMessageResponse,
    summary="Add or remove my reaction",
    responses=ERRORS,
)
def react(
    message_id: UUID, request: ReactionRequest, context: AuthenticatedContext
) -> ChatMessageResponse:
    return chat_service.react(context, message_id, request.emoji)


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=ReadResponse,
    summary="Mark the chat read",
    responses=ERRORS,
)
def read(conversation_id: UUID, context: AuthenticatedContext) -> ReadResponse:
    return chat_service.read(context, conversation_id)


@router.post(
    "/conversations/{conversation_id}/typing",
    status_code=204,
    summary="Tell the others I am typing",
    responses=ERRORS,
)
def typing(conversation_id: UUID, context: AuthenticatedContext) -> Response:
    chat_service.typing(context, conversation_id)
    return Response(status_code=204)


@router.get("/attachments/{attachment_id}", summary="Download a chat file", responses=ERRORS)
def attachment(attachment_id: UUID, context: AuthenticatedContext) -> FileResponse:
    path, name, mime = chat_service.attachment(context, attachment_id)
    return FileResponse(path, media_type=mime, filename=name)


@router.get(
    "/search", response_model=ChatMessagesResponse, summary="Search my chats", responses=ERRORS
)
def search(
    context: AuthenticatedContext, q: str = Query("", max_length=100)
) -> ChatMessagesResponse:
    return chat_service.search(context, q)
