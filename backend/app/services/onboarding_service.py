"""Onboarding documents (owner requests 2026-11-15).

Clients: as soon as a client with an email is added, they get a welcome email with a private link
to an onboarding form and the service agreement. The admin can send it again by hand, but only
within 60 hours of the client being added; after that the link stops working and nothing more
can be sent ("60 hrs lone matrame send cheyali lekapothe avvakudadhu").
Employees: the admin sends any of the offer letter, joining letter, welcome email and employment
agreement, filled with the job details; the link works for 7 days.
People accept online (typed name + "I agree"; time, IP and browser are kept) and get a signed
PDF. Everything here is Admin only, except the private link itself.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.repositories.finance_repository import FinanceRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.onboarding_repository import OnboardingRepository, PacketRow
from app.schemas.authentication import AuthContext
from app.schemas.onboarding import (
    ClientOnboardingRow,
    EmployeeDocumentsRequest,
    OnboardingOverview,
    PacketResponse,
    PublicDocument,
    PublicField,
    PublicPacket,
    PublicSubmit,
    StaffChoice,
    TemplateRequest,
    TemplateResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.document_templates import (
    BY_KIND,
    CLIENT_KINDS,
    DEFAULTS,
    PLACEHOLDERS,
    render,
)
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

CLIENT_WINDOW_HOURS = 60
EMPLOYEE_LINK_DAYS = 7

CLIENT_FORM: tuple[PublicField, ...] = (
    PublicField(key="contact_person", label="Main contact person", required=True),
    PublicField(key="contact_phone", label="Contact phone", required=True),
    PublicField(key="contact_email", label="Contact email", required=False),
    PublicField(key="business_name", label="Business name on invoices", required=False),
    PublicField(
        key="gstin",
        label="GSTIN (if you have one)",
        required=False,
        placeholder="e.g. 36ABCDE1234F1Z5",
    ),
    PublicField(key="billing_address", label="Billing address", required=False, multiline=True),
    PublicField(
        key="instagram", label="Instagram handle", required=False, placeholder="@yourbrand"
    ),
    PublicField(key="youtube", label="YouTube channel", required=False),
    PublicField(key="other_channels", label="Other channels (website, LinkedIn…)", required=False),
    PublicField(
        key="posting_days",
        label="Days you like to post",
        required=False,
        placeholder="e.g. Mon, Wed, Fri",
    ),
    PublicField(
        key="brand_notes",
        label="Brand style, colours, tone and things to avoid",
        required=False,
        multiline=True,
    ),
    PublicField(
        key="reference_links", label="Videos you like (links)", required=False, multiline=True
    ),
)
EMPLOYEE_FORM: tuple[PublicField, ...] = (
    PublicField(key="phone", label="Your phone number", required=True),
    PublicField(key="address", label="Your address", required=False, multiline=True),
    PublicField(key="emergency_contact", label="Emergency contact (name and phone)", required=True),
)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _rupees(amount: Decimal, currency: str) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, f"{currency} ")
    return f"{symbol}{amount:,.2f}"


class OnboardingService:
    def __init__(
        self,
        repository: OnboardingRepository | None = None,
        invoices: InvoiceRepository | None = None,
        finance: FinanceRepository | None = None,
    ) -> None:
        self.repository = repository or OnboardingRepository()
        self.invoices = invoices or InvoiceRepository()
        self.finance = finance or FinanceRepository()

    # -- helpers ------------------------------------------------------------------------------

    @staticmethod
    def _admin(context: AuthContext) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403,
                "COMPANY_ADMIN_REQUIRED",
                "Only the Company Admin manages onboarding documents.",
            )
        return context.company_id

    def _zone(self, company_id: UUID) -> ZoneInfo:
        try:
            return ZoneInfo(self.finance.company_timezone(company_id))
        except Exception:  # noqa: BLE001
            return ZoneInfo("UTC")

    def _local(self, company_id: UUID, moment: datetime) -> str:
        aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        return aware.astimezone(self._zone(company_id)).strftime("%d %b %Y, %I:%M %p")

    def _template(self, company_id: UUID, kind: str) -> tuple[str, str]:
        custom = self.repository.templates(company_id).get(kind)
        base = BY_KIND[kind]
        return (custom.subject, custom.body) if custom else (base.subject, base.body)

    def _company_values(self, company_id: UUID) -> dict[str, str]:
        company = self.invoices.company_profile(company_id)
        return {
            "company_name": company.name,
            "company_email": company.email or "",
            "company_phone": company.phone or "",
            "date": datetime.now(self._zone(company_id)).strftime("%d %B %Y"),
        }

    def _values(self, packet: PacketRow) -> dict[str, str]:
        values = self._company_values(packet.company_id)
        values["link_expires"] = self._local(packet.company_id, packet.expires_at)
        if packet.audience == "CLIENT":
            values["client_name"] = str(packet.fields.get("client_name") or packet.recipient_name)
            values["contact_name"] = packet.recipient_name
        else:
            fields = packet.fields
            currency = self.finance.company_currency(packet.company_id)
            joining = str(fields.get("joining_date") or "")
            values.update(
                employee_name=packet.recipient_name,
                job_title=str(fields.get("job_title", "")),
                monthly_salary=_rupees(Decimal(str(fields.get("monthly_salary", "0"))), currency),
                joining_date=(
                    datetime.fromisoformat(joining).strftime("%d %B %Y") if joining else ""
                ),
                reporting_to=str(fields.get("reporting_to") or "your manager"),
                work_location=str(fields.get("work_location") or "our office"),
                probation_months=str(fields.get("probation_months", 3)),
                notice_days=str(fields.get("notice_days", 30)),
            )
        return values

    @staticmethod
    def _status(packet: PacketRow) -> str:
        if packet.status in ("SENT", "OPENED") and packet.expires_at < _now():
            return "EXPIRED"
        return packet.status

    def _packet(self, packet: PacketRow) -> PacketResponse:
        return PacketResponse(
            id=packet.id,
            audience=packet.audience,
            client_id=packet.client_id,
            user_id=packet.user_id,
            recipient_name=packet.recipient_name,
            recipient_email=packet.recipient_email,
            documents=packet.documents,
            fields=packet.fields,
            status=self._status(packet),
            expires_at=packet.expires_at,
            opened_at=packet.opened_at,
            signed_name=packet.signed_name,
            signed_at=packet.signed_at,
            signed_ip=packet.signed_ip,
            form_data=packet.form_data,
            sent_count=packet.sent_count,
            created_by_name=packet.created_by_name,
            created_at=packet.created_at,
        )

    def _link(self, packet: PacketRow, token: str) -> str:
        from app.services.outbound_mail import app_url

        return app_url(
            "CLIENT" if packet.audience == "CLIENT" else "EMPLOYEE", f"/onboarding/{token}"
        )

    # -- documents as text and PDF ------------------------------------------------------------

    def _documents(self, packet: PacketRow) -> list[PublicDocument]:
        values = self._values(packet)
        out = []
        for kind in packet.documents:
            if kind not in BY_KIND:
                continue
            subject, body = self._template(packet.company_id, kind)
            out.append(
                PublicDocument(
                    kind=kind,
                    label=BY_KIND[kind].label,
                    signable=BY_KIND[kind].signable,
                    title=render(subject, values),
                    body=render(body, values),
                )
            )
        return out

    def _pdf(self, packet: PacketRow) -> bytes:
        """The documents as a formal PDF (owner request 2026-11-19): Adverse letterhead, the
        document title, real headings, numbered lists, a signature block on documents to accept,
        and a footer with page numbers."""
        from reportlab.lib import colors  # type: ignore[import-untyped]
        from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT  # type: ignore[import-untyped]
        from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
        from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
        from reportlab.lib.units import mm  # type: ignore[import-untyped]
        from reportlab.platypus import (  # type: ignore[import-untyped]
            Image,
            KeepTogether,
            ListFlowable,
            ListItem,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        from app.services.document_templates import blocks
        from app.services.invoice_pdf import ASSETS, _fonts

        _fonts()
        ink = colors.HexColor("#111827")
        muted = colors.HexColor("#6B7280")
        line = colors.HexColor("#E5E7EB")
        brand = colors.HexColor("#0876ED")
        body = ParagraphStyle(
            "b", fontName="Poppins", fontSize=9.6, leading=15.5, textColor=ink, alignment=TA_JUSTIFY
        )
        plain = ParagraphStyle("p", parent=body, alignment=0)
        title = ParagraphStyle(
            "t", fontName="Poppins-Bold", fontSize=17, leading=22, textColor=ink, spaceAfter=2
        )
        meta = ParagraphStyle("m", fontName="Poppins", fontSize=8.5, leading=12, textColor=muted)
        heading = ParagraphStyle(
            "h", fontName="Poppins-SemiBold", fontSize=10.5, leading=14, textColor=ink
        )
        right = ParagraphStyle("r", parent=meta, alignment=TA_RIGHT)
        right_name = ParagraphStyle(
            "rn", fontName="Poppins-SemiBold", fontSize=10, leading=13, alignment=TA_RIGHT
        )
        label = ParagraphStyle(
            "l", fontName="Poppins-SemiBold", fontSize=7.5, leading=10, textColor=muted
        )
        company = self.invoices.company_profile(packet.company_id)
        buffer = BytesIO()
        width = A4[0] - 40 * mm
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=16 * mm,
            bottomMargin=20 * mm,
            title=f"Documents for {packet.recipient_name}",
            author=company.name,
        )

        def letterhead() -> list[Any]:
            logo = Image(
                str(ASSETS / "adverse-logo.png"), width=40 * mm, height=40 * mm * 419 / 1600
            )
            contact = [Paragraph(escape(company.name), right_name)] + [
                Paragraph(escape(item), right)
                for item in (company.email, company.phone, company.address, company.website)
                if item
            ]
            head = Table([[logo, contact]], colWidths=[width * 0.5, width * 0.5])
            head.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.6, line),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                    ]
                )
            )
            return [head, Spacer(1, 9 * mm)]

        today = self._company_values(packet.company_id)["date"]
        party = "Client" if packet.audience == "CLIENT" else "Employee"
        story: list[Any] = []
        documents = [item for item in self._documents(packet) if item.kind != "CLIENT_ONBOARDING"]
        for index, item in enumerate(documents):
            if index:
                story.append(PageBreak())
            story += letterhead()
            story.append(Paragraph(escape(item.title), title))
            story.append(
                Paragraph(
                    f"{escape(item.label)} · Prepared for {escape(packet.recipient_name)} · {today}",
                    meta,
                )
            )
            story.append(Spacer(1, 7 * mm))
            for kind, parts in blocks(item.body):
                if kind == "heading":
                    story += [
                        Spacer(1, 2 * mm),
                        Paragraph(escape(parts[0]), heading),
                        Spacer(1, 1.5 * mm),
                    ]
                elif kind == "list":
                    story.append(
                        ListFlowable(
                            [
                                ListItem(Paragraph(escape(text), plain), leftIndent=14)
                                for text in parts
                            ],
                            bulletType="1",
                            bulletFontName="Poppins-SemiBold",
                            bulletFontSize=9,
                            leftIndent=14,
                        )
                    )
                    story.append(Spacer(1, 3 * mm))
                elif kind == "lines":
                    story += [
                        Paragraph("<br/>".join(escape(text) for text in parts), plain),
                        Spacer(1, 3 * mm),
                    ]
                else:
                    story += [Paragraph(escape(parts[0]), body), Spacer(1, 3 * mm)]
            if item.signable:
                accepted = (
                    f"Accepted online by <b>{escape(packet.signed_name or '')}</b><br/>"
                    f"{escape(self._local(packet.company_id, packet.signed_at))}"
                    f"<br/>IP {escape(packet.signed_ip or '-')}"
                    if packet.signed_at
                    else "Not accepted yet.<br/>Accept it online from the private link."
                )
                sign = Table(
                    [
                        [
                            Paragraph(f"FOR {escape(company.name.upper())}", label),
                            Paragraph(f"{party.upper()}", label),
                        ],
                        [
                            Paragraph(
                                f"<b>{escape(company.name)}</b><br/>Authorised signatory", plain
                            ),
                            Paragraph(
                                f"<b>{escape(packet.recipient_name)}</b><br/>{accepted}", plain
                            ),
                        ],
                    ],
                    colWidths=[width * 0.5, width * 0.5],
                )
                sign.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("LINEABOVE", (0, 0), (-1, 0), 0.6, line),
                            ("TOPPADDING", (0, 0), (-1, 0), 10),
                            ("TOPPADDING", (0, 1), (-1, 1), 4),
                        ]
                    )
                )
                story += [Spacer(1, 8 * mm), KeepTogether([sign])]
        if not story:
            story.append(Paragraph("No documents.", body))

        def footer(canvas: Any, document: Any) -> None:
            canvas.saveState()
            canvas.setFont("Poppins", 7.5)
            canvas.setFillColor(muted)
            canvas.drawString(
                20 * mm, 11 * mm, f"{company.name} · Prepared for {packet.recipient_name}"
            )
            canvas.drawRightString(A4[0] - 20 * mm, 11 * mm, f"Page {document.page}")
            canvas.setFillColor(brand)
            canvas.restoreState()

        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        return buffer.getvalue()

    # -- sending ------------------------------------------------------------------------------

    def _email(self, packet: PacketRow, token: str) -> None:
        from app.services.outbound_mail import deliver

        welcome_kind = "CLIENT_WELCOME" if packet.audience == "CLIENT" else "EMPLOYEE_WELCOME"
        subject, body = self._template(packet.company_id, welcome_kind)
        values = self._values(packet)
        has_signable = any(BY_KIND[kind].signable for kind in packet.documents if kind in BY_KIND)
        deliver(
            packet.company_id,
            to_email=packet.recipient_email,
            user_id=packet.user_id,
            subject=render(subject, values),
            title=render(subject, values),
            lines=[block for block in render(body, values).split("\n\n") if block.strip()],
            action_label="Open your documents",
            action_url=self._link(packet, token),
            company_name=values["company_name"],
            notify_type="onboarding.sent" if packet.user_id else None,
            notify_link="/dashboard",
            attachments=(
                [(self._pdf(packet), "documents.pdf", "application/pdf")] if has_signable else []
            ),
        )

    @staticmethod
    def _new_token() -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        return token, _hash(token)

    def send_client(self, context: AuthContext, client_id: UUID) -> PacketResponse:
        company_id = self._admin(context)
        return self._send_client(company_id, client_id, context.user_id)

    def _send_client(
        self, company_id: UUID, client_id: UUID, actor_id: UUID | None
    ) -> PacketResponse:
        client = next(
            (item for item in self.repository.clients(company_id) if item.id == client_id), None
        )
        if client is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        window_ends = client.created_at + timedelta(hours=CLIENT_WINDOW_HOURS)
        if _now() > window_ends:
            raise AuthenticationError(
                409,
                "ONBOARDING_WINDOW_CLOSED",
                f"Onboarding can only be sent within {CLIENT_WINDOW_HOURS} hours of adding "
                "the client.",
            )
        email = client.contact_email or client.email
        if not email:
            raise AuthenticationError(422, "NO_CLIENT_EMAIL", "Add the client's email first.")
        token, token_hash = self._new_token()
        existing = next(
            (
                packet
                for packet in self.repository.packets(company_id, "CLIENT")
                if packet.client_id == client_id and packet.status != "CANCELLED"
            ),
            None,
        )
        if existing and existing.status == "COMPLETED":
            raise AuthenticationError(
                409, "ONBOARDING_DONE", "This client has already completed onboarding."
            )
        if existing:
            self.repository.resend(existing.id, token_hash, window_ends)
            packet_id = existing.id
        else:
            packet_id = self.repository.create_packet(
                company_id,
                actor_id,
                "CLIENT",
                client_id,
                None,
                client.contact_name or client.name,
                email,
                list(CLIENT_KINDS),
                {"client_name": client.name},
                token_hash,
                window_ends,
            )
        packet = self.repository.packet(company_id, packet_id)
        assert packet is not None
        self._email(packet, token)
        return self._packet(packet)

    def auto_send_client(self, company_id: UUID, client_id: UUID, actor_id: UUID) -> None:
        """Called when a client is added: send right away if they have an email. Never raises."""
        try:
            self._send_client(company_id, client_id, actor_id)
        except AuthenticationError as error:
            logger.info("Client onboarding not sent automatically: %s", error.detail)
        except Exception:  # noqa: BLE001
            logger.warning("Client onboarding failed", exc_info=True)

    def send_employee(
        self, context: AuthContext, request: EmployeeDocumentsRequest
    ) -> PacketResponse:
        company_id = self._admin(context)
        user_id: UUID | None = None
        name, email = request.name.strip(), str(request.email or "")
        if request.user_id:
            person = next(
                (item for item in self.repository.staff(company_id) if item.id == request.user_id),
                None,
            )
            if person is None:
                raise AuthenticationError(404, "PERSON_NOT_FOUND", "That employee was not found.")
            user_id, name, email = person.id, name or person.name, email or person.email
        if not name or not email:
            raise AuthenticationError(
                422, "RECIPIENT_REQUIRED", "Choose an employee or enter a name and email."
            )
        token, token_hash = self._new_token()
        documents: list[str] = list(dict.fromkeys(request.documents))
        if "EMPLOYEE_WELCOME" not in documents:
            documents.insert(0, "EMPLOYEE_WELCOME")
        packet_id = self.repository.create_packet(
            company_id,
            context.user_id,
            "EMPLOYEE",
            None,
            user_id,
            name,
            email,
            documents,
            {
                "job_title": request.job_title,
                "monthly_salary": str(request.monthly_salary),
                "joining_date": request.joining_date.isoformat(),
                "reporting_to": request.reporting_to,
                "work_location": request.work_location,
                "probation_months": request.probation_months,
                "notice_days": request.notice_days,
            },
            token_hash,
            _now() + timedelta(days=EMPLOYEE_LINK_DAYS),
        )
        packet = self.repository.packet(company_id, packet_id)
        assert packet is not None
        self._email(packet, token)
        return self._packet(packet)

    def resend(self, context: AuthContext, packet_id: UUID) -> PacketResponse:
        company_id = self._admin(context)
        packet = self.repository.packet(company_id, packet_id)
        if packet is None:
            raise AuthenticationError(404, "PACKET_NOT_FOUND", "Those documents were not found.")
        if packet.audience == "CLIENT" and packet.client_id:
            return self._send_client(company_id, packet.client_id, context.user_id)
        if packet.status in ("COMPLETED", "CANCELLED"):
            raise AuthenticationError(409, "PACKET_CLOSED", "These documents are already closed.")
        token, token_hash = self._new_token()
        self.repository.resend(packet.id, token_hash, _now() + timedelta(days=EMPLOYEE_LINK_DAYS))
        fresh = self.repository.packet(company_id, packet_id)
        assert fresh is not None
        self._email(fresh, token)
        return self._packet(fresh)

    def cancel(self, context: AuthContext, packet_id: UUID) -> PacketResponse:
        company_id = self._admin(context)
        if not self.repository.cancel(company_id, packet_id):
            raise AuthenticationError(409, "PACKET_CLOSED", "These documents are already closed.")
        packet = self.repository.packet(company_id, packet_id)
        assert packet is not None
        return self._packet(packet)

    def admin_pdf(self, context: AuthContext, packet_id: UUID) -> tuple[bytes, str]:
        company_id = self._admin(context)
        packet = self.repository.packet(company_id, packet_id)
        if packet is None:
            raise AuthenticationError(404, "PACKET_NOT_FOUND", "Those documents were not found.")
        name = packet.recipient_name.replace(" ", "-").lower()
        return self._pdf(packet), f"documents-{name}.pdf"

    # -- admin overview and templates ---------------------------------------------------------

    def overview(self, context: AuthContext) -> OnboardingOverview:
        company_id = self._admin(context)
        client_packets: dict[UUID, PacketRow] = {}
        for packet in self.repository.packets(company_id, "CLIENT"):
            if (
                packet.client_id
                and packet.client_id not in client_packets
                and packet.status != "CANCELLED"
            ):
                client_packets[packet.client_id] = packet
        now = _now()
        clients = []
        for client in self.repository.clients(company_id):
            ends = client.created_at + timedelta(hours=CLIENT_WINDOW_HOURS)
            sent = client_packets.get(client.id)
            clients.append(
                ClientOnboardingRow(
                    client_id=client.id,
                    name=client.name,
                    email=client.contact_email or client.email,
                    created_at=client.created_at,
                    window_ends_at=ends,
                    can_send=now <= ends
                    and bool(client.contact_email or client.email)
                    and not (sent is not None and sent.status == "COMPLETED"),
                    packet=self._packet(sent) if sent else None,
                )
            )
        return OnboardingOverview(
            window_hours=CLIENT_WINDOW_HOURS,
            clients=clients,
            employees=[
                self._packet(item) for item in self.repository.packets(company_id, "EMPLOYEE")
            ],
            staff=[
                StaffChoice(
                    id=item.id,
                    name=item.name,
                    email=item.email,
                    role="MANAGER" if item.role == "COMPANY_MANAGER" else "EMPLOYEE",
                )
                for item in self.repository.staff(company_id)
            ],
            templates=self._templates(company_id),
        )

    def _templates(self, company_id: UUID) -> list[TemplateResponse]:
        custom = self.repository.templates(company_id)
        return [
            TemplateResponse(
                kind=item.kind,
                audience=item.audience,
                label=item.label,
                signable=item.signable,
                subject=custom[item.kind].subject if item.kind in custom else item.subject,
                body=custom[item.kind].body if item.kind in custom else item.body,
                customised=item.kind in custom,
                placeholders=PLACEHOLDERS[item.audience],
            )
            for item in DEFAULTS
        ]

    def save_template(
        self, context: AuthContext, kind: str, request: TemplateRequest
    ) -> list[TemplateResponse]:
        company_id = self._admin(context)
        if kind not in BY_KIND:
            raise AuthenticationError(404, "TEMPLATE_NOT_FOUND", "That template was not found.")
        self.repository.save_template(
            company_id, context.user_id, kind, request.subject.strip(), request.body
        )
        return self._templates(company_id)

    def reset_template(self, context: AuthContext, kind: str) -> list[TemplateResponse]:
        company_id = self._admin(context)
        if kind not in BY_KIND:
            raise AuthenticationError(404, "TEMPLATE_NOT_FOUND", "That template was not found.")
        self.repository.reset_template(company_id, kind)
        return self._templates(company_id)

    # -- the private link ---------------------------------------------------------------------

    def _by_token(self, token: str) -> PacketRow:
        packet = self.repository.by_token(_hash(token)) if 20 <= len(token) <= 100 else None
        if packet is None or packet.status == "CANCELLED":
            raise AuthenticationError(404, "LINK_NOT_FOUND", "This link is not valid.")
        return packet

    def public_view(self, token: str) -> PublicPacket:
        packet = self._by_token(token)
        status = self._status(packet)
        if status == "SENT":
            self.repository.mark_opened(packet.id)
            status = "OPENED"
        documents = self._documents(packet)
        intro = next((item for item in documents if item.kind == "CLIENT_ONBOARDING"), None)
        return PublicPacket(
            company_name=self._company_values(packet.company_id)["company_name"],
            company_email=self._company_values(packet.company_id)["company_email"],
            company_phone=self._company_values(packet.company_id)["company_phone"],
            audience=packet.audience,
            recipient_name=packet.recipient_name,
            status=status,
            expires_at=packet.expires_at,
            intro=intro.body if intro else "",
            documents=[item for item in documents if item.kind != "CLIENT_ONBOARDING"],
            form=list(CLIENT_FORM if packet.audience == "CLIENT" else EMPLOYEE_FORM),
            form_data=packet.form_data if status == "COMPLETED" else {},
            signed_name=packet.signed_name,
            signed_at=packet.signed_at,
        )

    def public_submit(self, token: str, request: PublicSubmit, ip: str, agent: str) -> PublicPacket:
        packet = self._by_token(token)
        status = self._status(packet)
        if status == "EXPIRED":
            raise AuthenticationError(
                410, "LINK_EXPIRED", "This link has expired. Ask us to send it again."
            )
        if status == "COMPLETED":
            raise AuthenticationError(409, "ALREADY_DONE", "These documents are already accepted.")
        if not request.accept:
            raise AuthenticationError(
                422, "ACCEPT_REQUIRED", "Tick the box to accept the documents."
            )
        fields = CLIENT_FORM if packet.audience == "CLIENT" else EMPLOYEE_FORM
        form = {item.key: request.form.get(item.key, "").strip()[:2000] for item in fields}
        missing = [item.label for item in fields if item.required and not form[item.key]]
        if missing:
            raise AuthenticationError(
                422, "FORM_INCOMPLETE", f"Please fill in: {', '.join(missing)}."
            )
        if not self.repository.complete(packet.id, form, request.signed_name.strip(), ip, agent):
            raise AuthenticationError(409, "ALREADY_DONE", "These documents are already accepted.")
        done = self.repository.by_token(_hash(token))
        assert done is not None
        self._after_accept(done)
        return self.public_view(token)

    def public_pdf(self, token: str) -> tuple[bytes, str]:
        packet = self._by_token(token)
        return self._pdf(packet), "documents.pdf"

    def _after_accept(self, packet: PacketRow) -> None:
        """Copy useful answers, tell the admins, and mail the signed copy to the person."""
        try:
            if packet.audience == "CLIENT" and packet.client_id and packet.form_data.get("gstin"):
                from app.repositories.package_repository import PackageRepository

                packages = PackageRepository()
                tax = packages.client_tax(packet.company_id, packet.client_id)
                if tax is not None and not tax.gstin:
                    packages.set_client_tax(
                        packet.company_id,
                        packet.client_id,
                        tax.gst_enabled,
                        Decimal(tax.gst_rate),
                        str(packet.form_data["gstin"]).upper()[:20],
                    )
            from app.services.mail_service import mail_service
            from app.services.outbound_mail import deliver

            who = "Client" if packet.audience == "CLIENT" else "New team member"
            answers = "\n".join(
                f"{key.replace('_', ' ').capitalize()}: {value}"
                for key, value in packet.form_data.items()
                if value
            )
            mail_service.system(
                packet.company_id,
                notification_service.admins(packet.company_id),
                f"{who} accepted the documents: {packet.recipient_name}",
                f'{packet.recipient_name} accepted online as "{packet.signed_name}".\n\n{answers}',
                "/documents",
                "ONBOARDING",
                notify=True,
            )
            company = self._company_values(packet.company_id)["company_name"]
            deliver(
                packet.company_id,
                to_email=packet.recipient_email,
                user_id=packet.user_id,
                subject=f"Your signed documents · {company}",
                title="Thank you, it's all done",
                lines=[
                    f"Hello {packet.recipient_name}, thank you for accepting the documents.",
                    "Your signed copy is attached for your records.",
                ],
                company_name=company,
                attachments=[(self._pdf(packet), "signed-documents.pdf", "application/pdf")],
            )
        except Exception:  # noqa: BLE001
            logger.warning("After-accept steps failed", exc_info=True)


onboarding_service = OnboardingService()
