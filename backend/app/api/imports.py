"""Spreadsheet import for one client (owner request 2026-11-19). Admin only.

POST .../preview reads the file and shows what would be added; POST .../apply saves it. The same
file can be sent again safely: rows already in Adverse are skipped.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from app.middleware.authentication import AuthenticatedContext
from app.schemas.imports import ImportPreview, ImportResult
from app.schemas.registration import ErrorResponse
from app.services.import_service import import_service
from app.services.xlsx_reader import MAX_FILE_BYTES

router = APIRouter(prefix="/company/imports", tags=["imports"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Only the Company Admin."},
    404: {"model": ErrorResponse, "description": "The client was not found."},
    422: {"model": ErrorResponse, "description": "The file could not be read."},
}


async def _content(file: UploadFile) -> bytes:
    return await file.read(MAX_FILE_BYTES + 1)


@router.post(
    "/clients/{client_id}/preview",
    response_model=ImportPreview,
    summary="Read a client's spreadsheet and show what would be imported",
    responses=ERRORS,
)
async def preview_import(
    client_id: UUID, context: AuthenticatedContext, file: UploadFile = File(...)
) -> ImportPreview:
    return import_service.preview(context, client_id, await _content(file), file.filename or "")


@router.post(
    "/clients/{client_id}/apply",
    response_model=ImportResult,
    summary="Import a client's spreadsheet (calendar tabs and/or payments and work)",
    responses=ERRORS,
)
async def apply_import(
    client_id: UUID,
    context: AuthenticatedContext,
    file: UploadFile = File(...),
    tabs: str = Form(default=""),
    money: bool = Form(default=False),
) -> ImportResult:
    # Browsers send line breaks in form fields as \r\n.
    names = [name.strip() for name in tabs.splitlines() if name.strip()]
    return import_service.apply(
        context, client_id, await _content(file), file.filename or "", names, money
    )
