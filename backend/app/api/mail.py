"""Internal mailbox (owner request 2026-11-15). mail_service decides who may write to whom."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.middleware.authentication import AuthenticatedContext
from app.schemas.mail import (
    MailFolder,
    MailListResponse,
    MailPeopleResponse,
    MailThreadResponse,
    MailUnread,
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


@router.get("", response_model=MailListResponse, summary="My mail", responses=ERRORS)
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


@router.get("/attachments/{attachment_id}", summary="Download a mail file", responses=ERRORS)
def attachment(attachment_id: UUID, context: AuthenticatedContext) -> FileResponse:
    path, name, mime = mail_service.attachment(context, attachment_id)
    return FileResponse(path, media_type=mime, filename=name)


@router.get(
    "/{message_id}",
    response_model=MailThreadResponse,
    summary="Open a mail and its replies (marks them read)",
    responses=ERRORS,
)
def thread(message_id: UUID, context: AuthenticatedContext) -> MailThreadResponse:
    return mail_service.thread(context, message_id)


@router.post(
    "",
    response_model=MailThreadResponse,
    status_code=201,
    summary="Send a mail or a reply",
    responses=ERRORS,
)
def send(
    context: AuthenticatedContext,
    to: list[UUID] = Form(default=[]),
    subject: str = Form("", max_length=200),
    body: str = Form("", max_length=20000),
    reply_to_id: UUID | None = Form(None),
    files: list[UploadFile] = File(default=[]),
) -> MailThreadResponse:
    return mail_service.send(context, to, subject, body, reply_to_id, files)


@router.delete(
    "/{message_id}", status_code=204, summary="Remove a mail from my mailbox", responses=ERRORS
)
def hide(message_id: UUID, context: AuthenticatedContext) -> Response:
    mail_service.hide(context, message_id)
    return Response(status_code=204)
