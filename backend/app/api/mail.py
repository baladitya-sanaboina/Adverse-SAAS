"""Internal mailbox (owner requests 2026-11-15). mail_service decides who may write to whom."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.middleware.authentication import AuthenticatedContext
from app.schemas.mail import (
    MailActionRequest,
    MailActionResponse,
    MailDraftResponse,
    MailFolder,
    MailListResponse,
    MailPeopleResponse,
    MailThreadResponse,
    MailTicket,
    MailTicketListResponse,
    MailTicketUpdate,
    MailUnread,
    TicketStatus,
)
from app.schemas.registration import ErrorResponse
from app.services.mail_service import mail_service

router = APIRouter(prefix="/mail", tags=["mail"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Not allowed to write to that person."},
    404: {"model": ErrorResponse, "description": "The mail was not found."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "", response_model=MailListResponse, summary="Conversations in a folder", responses=ERRORS
)
def list_mail(
    context: AuthenticatedContext,
    folder: MailFolder = "INBOX",
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> MailListResponse:
    return mail_service.list(context, folder, q, page, page_size)


@router.get("/unread", response_model=MailUnread, summary="Unread mail counts", responses=ERRORS)
def unread(context: AuthenticatedContext) -> MailUnread:
    return mail_service.unread(context)


@router.get(
    "/people", response_model=MailPeopleResponse, summary="Who I can write to", responses=ERRORS
)
def people(context: AuthenticatedContext) -> MailPeopleResponse:
    return mail_service.people(context)


@router.post(
    "/actions",
    response_model=MailActionResponse,
    summary="Archive, trash, restore, star or mark conversations",
    responses=ERRORS,
)
def act(request: MailActionRequest, context: AuthenticatedContext) -> MailActionResponse:
    return mail_service.act(context, request.thread_ids, request.action)


@router.get("/tickets", response_model=MailTicketListResponse, summary="Tickets", responses=ERRORS)
def tickets(
    context: AuthenticatedContext, status: TicketStatus | None = None
) -> MailTicketListResponse:
    return mail_service.tickets(context, status)


@router.patch(
    "/tickets/{ticket_id}",
    response_model=MailTicket,
    summary="Change a ticket's status, priority or assignee",
    responses=ERRORS,
)
def update_ticket(
    ticket_id: UUID, request: MailTicketUpdate, context: AuthenticatedContext
) -> MailTicket:
    return mail_service.update_ticket(context, ticket_id, request)


@router.post("/drafts", response_model=MailDraftResponse, summary="Save a draft", responses=ERRORS)
def save_draft(
    context: AuthenticatedContext,
    draft_id: UUID | None = Form(None),
    to: list[UUID] = Form(default=[]),
    cc: list[UUID] = Form(default=[]),
    bcc: list[UUID] = Form(default=[]),
    subject: str = Form("", max_length=200),
    body: str = Form("", max_length=20000),
    reply_to_id: UUID | None = Form(None),
) -> MailDraftResponse:
    return mail_service.save_draft(context, draft_id, to, cc, bcc, subject, body, reply_to_id)


@router.delete("/drafts/{draft_id}", status_code=204, summary="Discard a draft", responses=ERRORS)
def discard_draft(draft_id: UUID, context: AuthenticatedContext) -> Response:
    mail_service.discard_draft(context, draft_id)
    return Response(status_code=204)


@router.post(
    "/{message_id}/unschedule",
    response_model=MailDraftResponse,
    summary="Cancel a scheduled send (the mail goes back to Drafts)",
    responses=ERRORS,
)
def unschedule(message_id: UUID, context: AuthenticatedContext) -> MailDraftResponse:
    return mail_service.unschedule(context, message_id)


@router.get("/attachments/{attachment_id}", summary="Download a mail file", responses=ERRORS)
def attachment(attachment_id: UUID, context: AuthenticatedContext) -> FileResponse:
    path, name, mime = mail_service.attachment(context, attachment_id)
    return FileResponse(path, media_type=mime, filename=name)


@router.get(
    "/{message_id}",
    response_model=MailThreadResponse,
    summary="Open a conversation (marks it read)",
    responses=ERRORS,
)
def thread(
    message_id: UUID, context: AuthenticatedContext, trash: bool = False
) -> MailThreadResponse:
    return mail_service.thread(context, message_id, trash)


@router.post(
    "",
    response_model=MailThreadResponse,
    status_code=201,
    summary="Send (or schedule) a mail, a reply, a forward or a ticket",
    responses=ERRORS,
)
def send(
    context: AuthenticatedContext,
    to: list[UUID] = Form(default=[]),
    cc: list[UUID] = Form(default=[]),
    bcc: list[UUID] = Form(default=[]),
    subject: str = Form("", max_length=200),
    body: str = Form("", max_length=20000),
    reply_to_id: UUID | None = Form(None),
    forward_of_id: UUID | None = Form(None),
    draft_id: UUID | None = Form(None),
    scheduled_at: datetime | None = Form(None),
    ticket_priority: str | None = Form(None, max_length=10),
    files: list[UploadFile] = File(default=[]),
) -> MailThreadResponse:
    return mail_service.send(
        context,
        to,
        subject,
        body,
        reply_to_id,
        files,
        cc=cc,
        bcc=bcc,
        forward_of=forward_of_id,
        draft_id=draft_id,
        scheduled_at=scheduled_at,
        ticket_priority=ticket_priority or None,
    )


@router.delete(
    "/{message_id}", status_code=204, summary="Move a mail to my trash", responses=ERRORS
)
def hide(message_id: UUID, context: AuthenticatedContext) -> Response:
    mail_service.hide(context, message_id)
    return Response(status_code=204)
