"""Chat (Phase 14). Every role uses the same routes; chat_service decides what each may do."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.middleware.authentication import AuthenticatedContext
from app.schemas.chat import (
    ActiveCallResponse,
    CallResponse,
    CallStartRequest,
    ChatMessageResponse,
    ChatMessagesResponse,
    ConversationListResponse,
    ConversationResponse,
    DirectRequest,
    GroupRequest,
    GroupUpdateRequest,
    MeetingListResponse,
    MeetingRequest,
    MeetingResponse,
    MessageEditRequest,
    PeopleResponse,
    ReactionRequest,
    ReadResponse,
    RoomRequest,
    SignalRequest,
    StatusRequest,
)
from app.schemas.registration import ErrorResponse
from app.services.call_service import call_service
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


@router.get("/unread", summary="My unread chat messages", responses=ERRORS)
def unread(context: AuthenticatedContext) -> dict[str, int]:
    """For the red count on the floating chat button."""
    return {"unread_total": chat_service.unread(context)}


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


# -- calls (owner request 2026-11-14) --------------------------------------------------------


@router.post(
    "/conversations/{conversation_id}/calls",
    response_model=CallResponse,
    summary="Start a call in the chat, or join the one running",
    responses=ERRORS,
)
def start_call(
    conversation_id: UUID, request: CallStartRequest, context: AuthenticatedContext
) -> CallResponse:
    return call_service.start(context, conversation_id, request)


@router.get(
    "/conversations/{conversation_id}/call",
    response_model=ActiveCallResponse,
    summary="The call running in the chat, if any",
    responses=ERRORS,
)
def active_call(conversation_id: UUID, context: AuthenticatedContext) -> ActiveCallResponse:
    return call_service.active(context, conversation_id)


@router.post(
    "/calls/{call_id}/join", response_model=CallResponse, summary="Join a call", responses=ERRORS
)
def join_call(call_id: UUID, context: AuthenticatedContext) -> CallResponse:
    return call_service.join(context, call_id)


@router.post(
    "/calls/{call_id}/leave",
    response_model=ActiveCallResponse,
    summary="Leave a call (it ends when the last person leaves)",
    responses=ERRORS,
)
def leave_call(call_id: UUID, context: AuthenticatedContext) -> ActiveCallResponse:
    return call_service.leave(context, call_id)


@router.post(
    "/calls/{call_id}/ping",
    response_model=CallResponse,
    summary="Still here (every few seconds while in a call)",
    responses=ERRORS,
)
def ping_call(call_id: UUID, context: AuthenticatedContext) -> CallResponse:
    return call_service.ping(context, call_id)


@router.post(
    "/calls/{call_id}/decline", status_code=204, summary="Decline a ringing call", responses=ERRORS
)
def decline_call(call_id: UUID, context: AuthenticatedContext) -> Response:
    call_service.decline(context, call_id)
    return Response(status_code=204)


@router.post(
    "/calls/{call_id}/signal",
    status_code=204,
    summary="Pass a WebRTC offer, answer or candidate to someone in the call",
    responses=ERRORS,
)
def signal_call(call_id: UUID, request: SignalRequest, context: AuthenticatedContext) -> Response:
    call_service.signal(context, call_id, request)
    return Response(status_code=204)


# -- meetings --------------------------------------------------------------------------------


@router.get(
    "/meetings",
    response_model=MeetingListResponse,
    summary="Meetings in my chats (for calendars)",
    responses=ERRORS,
)
def meetings(
    context: AuthenticatedContext,
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    conversation_id: UUID | None = Query(None),
) -> MeetingListResponse:
    return call_service.meetings(context, start, end, conversation_id)


@router.post(
    "/conversations/{conversation_id}/meetings",
    response_model=MeetingResponse,
    status_code=201,
    summary="Schedule a meeting in the chat",
    responses=ERRORS,
)
def schedule_meeting(
    conversation_id: UUID, request: MeetingRequest, context: AuthenticatedContext
) -> MeetingResponse:
    return call_service.schedule(context, conversation_id, request)


@router.delete(
    "/meetings/{meeting_id}", status_code=204, summary="Cancel a meeting", responses=ERRORS
)
def cancel_meeting(meeting_id: UUID, context: AuthenticatedContext) -> Response:
    call_service.cancel(context, meeting_id)
    return Response(status_code=204)
