from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.repositories.company_settings_repository import (
    CompanySettingsRecord,
    CompanySettingsRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.company_settings import (
    BrandingAssetResponse,
    BrandingSettings,
    CompanyBrandingResponse,
    CompanyPreferencesUpdate,
    CompanySettingsResponse,
    CompanySettingsUpdate,
    ContactSettings,
    GeneralSettings,
    NotificationSettings,
    PreferenceSettings,
    RegionalSettings,
)
from app.services.authentication_service import AuthenticationError


class CompanySettingsService:
    _upload_root = Path("storage/company-branding")
    _types = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    _adverse_primary = "#0876ED"
    _adverse_secondary = "#065EC1"
    _legacy_accents = frozenset({"#8B6AAF", "#715795", "#3D9BF5"})

    def __init__(self, repository: CompanySettingsRepository | None = None):
        self.repository = repository or CompanySettingsRepository()

    @staticmethod
    def _company(context: AuthContext) -> tuple[UUID, UUID]:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Only a Company Admin can manage company settings."
            )
        return context.user_id, context.company_id

    @classmethod
    def _normalize_color(cls, value: str | None, fallback: str) -> str:
        normalized = (value or fallback).strip().upper()
        return normalized if normalized.startswith("#") and len(normalized) == 7 else fallback

    @classmethod
    def _branding_palette(cls, record: CompanySettingsRecord) -> dict[str, str]:
        primary = cls._normalize_color(record.primary_color, cls._adverse_primary)
        secondary = cls._normalize_color(record.secondary_color, cls._adverse_secondary)
        accent = cls._normalize_color(record.accent_color, primary)
        if accent in cls._legacy_accents:
            accent = primary
        return {
            "primary_color": primary,
            "secondary_color": secondary,
            "accent_color": accent,
            "info_color": cls._normalize_color(record.info_color, "#2563A6"),
            "success_color": cls._normalize_color(record.success_color, "#16855B"),
            "warning_color": cls._normalize_color(record.warning_color, "#B7791F"),
            "danger_color": cls._normalize_color(record.danger_color, "#C2414F"),
        }

    @staticmethod
    def _response(record: CompanySettingsRecord) -> CompanySettingsResponse:
        palette = CompanySettingsService._branding_palette(record)
        return CompanySettingsResponse(
            company_id=record.company_id,
            company_code=record.company_code,
            general=GeneralSettings(
                company_name=record.company_name, description=record.description
            ),
            branding=BrandingSettings(
                logo_url=record.logo_url,
                favicon_url=record.favicon_url,
                primary_color=palette["primary_color"],
                secondary_color=palette["secondary_color"],
                accent_color=palette["accent_color"],
                info_color=palette["info_color"],
                success_color=palette["success_color"],
                warning_color=palette["warning_color"],
                danger_color=palette["danger_color"],
                email_footer=record.email_footer,
            ),
            contact=ContactSettings(
                business_email=record.business_email,
                support_email=record.support_email,
                phone=record.phone,
                support_phone=record.support_phone,
                website=record.website,
                address=record.address,
                gst_tax_id=record.gst_tax_id,
                registration_number=record.registration_number,
            ),
            regional=RegionalSettings(
                timezone=record.timezone,
                language=record.language,
                currency=record.currency,
                date_format=record.date_format,
                time_format=record.time_format,
            ),
            notifications=NotificationSettings(**record.notifications),
            preferences=PreferenceSettings(
                working_days=record.working_days,
                business_hours_start=record.business_hours["start"],
                business_hours_end=record.business_hours["end"],
                theme=record.theme,
            ),
            updated_at=record.updated_at,
        )

    def get(self, context: AuthContext) -> CompanySettingsResponse:
        _, company_id = self._company(context)
        record = self.repository.get(company_id)
        if record is None:
            raise AuthenticationError(
                404, "COMPANY_SETTINGS_NOT_FOUND", "Company settings are not initialized."
            )
        return self._response(record)

    def branding(self, context: AuthContext) -> CompanyBrandingResponse:
        if context.company_id is None or context.role not in {
            "COMPANY_ADMIN",
            "COMPANY_MANAGER",
            "COMPANY_EMPLOYEE",
            "COMPANY_CLIENT",
        }:
            raise AuthenticationError(
                403, "COMPANY_CONTEXT_REQUIRED", "Company workspace access is required."
            )
        record = self.repository.get(context.company_id)
        if record is None:
            raise AuthenticationError(
                404, "COMPANY_SETTINGS_NOT_FOUND", "Company settings are not initialized."
            )
        palette = self._branding_palette(record)
        return CompanyBrandingResponse(
            company_id=record.company_id,
            company_name=record.company_name,
            logo_url=record.logo_url,
            favicon_url=record.favicon_url,
            primary_color=palette["primary_color"],
            secondary_color=palette["secondary_color"],
            accent_color=palette["accent_color"],
            info_color=palette["info_color"],
            success_color=palette["success_color"],
            warning_color=palette["warning_color"],
            danger_color=palette["danger_color"],
            updated_at=record.updated_at,
        )

    def update(
        self, context: AuthContext, request: CompanySettingsUpdate
    ) -> CompanySettingsResponse:
        actor_id, company_id = self._company(context)
        company_values = {
            "name": request.general.company_name,
            "description": request.general.description,
            "contact_email": (
                str(request.contact.business_email) if request.contact.business_email else None
            ),
            "phone": request.contact.phone,
            "website": str(request.contact.website) if request.contact.website else None,
            "address": request.contact.address,
            "timezone": request.regional.timezone,
            "language": request.regional.language,
        }
        default_values = {
            "primary_color": request.branding.primary_color,
            "secondary_color": request.branding.secondary_color,
            "accent_color": request.branding.accent_color,
            "info_color": request.branding.info_color,
            "success_color": request.branding.success_color,
            "warning_color": request.branding.warning_color,
            "danger_color": request.branding.danger_color,
            "email_footer": request.branding.email_footer,
            "support_email": (
                str(request.contact.support_email) if request.contact.support_email else None
            ),
            "support_phone": request.contact.support_phone,
            "gst_tax_id": request.contact.gst_tax_id,
            "registration_number": request.contact.registration_number,
            "timezone": request.regional.timezone,
            "language": request.regional.language,
            "currency": request.regional.currency,
            "date_format": request.regional.date_format,
            "time_format": request.regional.time_format,
            "working_days": request.preferences.working_days,
            "business_hours": {
                "start": request.preferences.business_hours_start,
                "end": request.preferences.business_hours_end,
            },
            "theme": request.preferences.theme,
            "notification_preferences": request.notifications.model_dump(),
        }
        actions = [
            "COMPANY_SETTINGS_UPDATED",
            "COMPANY_BRANDING_UPDATED",
            "COMPANY_CONTACT_UPDATED",
            "COMPANY_REGIONAL_UPDATED",
            "COMPANY_NOTIFICATION_PREFERENCES_UPDATED",
            "COMPANY_PREFERENCES_UPDATED",
        ]
        try:
            record = self.repository.update(
                actor_id, company_id, company_values, default_values, actions
            )
        except ValueError as error:
            raise AuthenticationError(409, "COMPANY_SETTINGS_CONFLICT", str(error)) from error
        if record is None:
            raise AuthenticationError(
                404, "COMPANY_SETTINGS_NOT_FOUND", "Company settings are not initialized."
            )
        return self._response(record)

    def update_preferences(
        self, context: AuthContext, request: CompanyPreferencesUpdate
    ) -> CompanySettingsResponse:
        current = self.get(context)
        return self.update(
            context,
            CompanySettingsUpdate(
                general=current.general,
                branding=current.branding,
                contact=current.contact,
                regional=current.regional,
                notifications=request.notifications,
                preferences=request.preferences,
            ),
        )

    async def upload(
        self, context: AuthContext, asset: str, upload: UploadFile
    ) -> BrandingAssetResponse:
        actor_id, company_id = self._company(context)
        if asset not in {"logo", "favicon"}:
            raise AuthenticationError(422, "INVALID_ASSET", "Asset must be logo or favicon.")
        extension = self._types.get(upload.content_type or "")
        if extension is None:
            raise AuthenticationError(422, "INVALID_IMAGE", "Use PNG, JPEG, or WebP.")
        content = await upload.read(2 * 1024 * 1024 + 1)
        valid = (
            extension == ".png"
            and content.startswith(b"\x89PNG\r\n\x1a\n")
            or extension == ".jpg"
            and content.startswith(b"\xff\xd8\xff")
            or extension == ".webp"
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )
        if not content or len(content) > 2 * 1024 * 1024 or not valid:
            raise AuthenticationError(
                422, "INVALID_IMAGE", "Upload a valid image no larger than 2 MB."
            )
        directory = self._upload_root / str(company_id)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{asset}-{uuid4().hex}{extension}"
        (directory / filename).write_bytes(content)
        url = f"/storage/company-branding/{company_id}/{filename}"
        record = self.repository.update(
            actor_id,
            company_id,
            {},
            {"logo_url" if asset == "logo" else "favicon_url": url},
            ["COMPANY_LOGO_UPDATED" if asset == "logo" else "COMPANY_FAVICON_UPDATED"],
        )
        if record is None:
            raise AuthenticationError(
                404, "COMPANY_SETTINGS_NOT_FOUND", "Company settings are not initialized."
            )
        return BrandingAssetResponse(asset=cast(Literal["logo", "favicon"], asset), url=url)

    def remove(self, context: AuthContext, asset: str) -> BrandingAssetResponse:
        actor_id, company_id = self._company(context)
        if asset not in {"logo", "favicon"}:
            raise AuthenticationError(422, "INVALID_ASSET", "Asset must be logo or favicon.")
        current = self.repository.get(company_id)
        if current is None:
            raise AuthenticationError(
                404, "COMPANY_SETTINGS_NOT_FOUND", "Company settings are not initialized."
            )
        old_url = current.logo_url if asset == "logo" else current.favicon_url
        record = self.repository.update(
            actor_id,
            company_id,
            {},
            {"logo_url" if asset == "logo" else "favicon_url": None},
            ["COMPANY_LOGO_UPDATED" if asset == "logo" else "COMPANY_FAVICON_UPDATED"],
        )
        if record is None:
            raise AuthenticationError(
                404, "COMPANY_SETTINGS_NOT_FOUND", "Company settings are not initialized."
            )
        if old_url and old_url.startswith(f"/storage/company-branding/{company_id}/"):
            old_file = Path(old_url.lstrip("/"))
            try:
                old_file.unlink(missing_ok=True)
            except OSError:
                pass
        return BrandingAssetResponse(asset=cast(Literal["logo", "favicon"], asset), url=None)

    def is_ready(self) -> bool:
        return self.repository.is_ready()


company_settings_service = CompanySettingsService()
