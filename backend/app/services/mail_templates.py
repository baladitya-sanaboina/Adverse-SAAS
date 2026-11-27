"""One layout for every mail that leaves Adverse.

The design follows the owner's own templates in "Email templates/" (owner request 2026-11-27:
"mail templates asal nachaledhu anni marchali"): the Adverse logo on a white card with a soft blue
border, a large heading with the person's name in brand blue, light-blue cards for details, one
full-width blue button, a "Warm regards" sign-off and a blue footer with the white logo, phone,
website and a confidentiality line. Email-client safe: tables and inline styles only, with an
Outlook (VML) button.

`render_mail` serves every mail; `render_onboarding_mail` and `render_welcome_mail` are the two
account mails written to the owner's templates almost word for word.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from html import escape

from app.core.settings import settings

INK = "#0b1b2e"
TEXT = "#4a5b72"
MUTED = "#6b7b90"
BORDER = "#e4edf8"
CARD = "#f3f8ff"
CARD_LINE = "#d9e9fc"
NOTE = "#eaf3fe"
NOTE_TEXT = "#244463"
BRAND = "#0876ed"
FOOT_TEXT = "#cfe3fb"
HEAD_FONT = "Poppins,'Segoe UI',Helvetica,Arial,sans-serif"
FONT = "'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'Courier New',Consolas,monospace"
DEFAULT_PHONE = "+91 9392513422"
_MONEY_LABELS = ("amount", "total", "balance", "amount due", "balance due", "advance left now")


def _origin() -> str:
    origins = settings.allowed_origins or ["http://localhost:3000"]
    return origins[0].rstrip("/")


def logo_url(white: bool = False) -> str:
    """The logo images are served by the Admin app (frontend/Admin/public/email)."""
    name = "adverse-email-logo-white.png" if white else "adverse-email-logo.png"
    return f"{_origin()}/email/{name}"


def website() -> str:
    return settings.internal_email_domain.strip().lower().lstrip("@") or "adverseindia.com"


# -- building blocks ----------------------------------------------------------------------------


def _p(
    text: str, *, size: int = 16, line: int = 26, color: str = TEXT, margin: str = "0 0 16px 0"
) -> str:
    return (
        f'<p style="margin:{margin};font-family:{FONT};font-size:{size}px;line-height:{line}px;'
        f'color:{color};">{escape(text)}</p>'
    )


def _section(inner: str, top: int = 28) -> str:
    return f'<tr><td class="px" style="padding:{top}px 40px 0 40px;">{inner}</td></tr>'


def _card(inner: str, padding: str = "26px 26px 14px 26px") -> str:
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{CARD};border:1px solid {CARD_LINE};border-radius:16px;">'
        f'<tr><td style="padding:{padding};font-family:{FONT};">{inner}</td></tr></table>'
    )


def _card_title(title: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="margin-bottom:18px;"><tr>'
        '<td align="center" valign="middle" width="40" height="40" style="width:40px;height:40px;'
        f"background-color:{BRAND};border-radius:20px;color:#ffffff;font-size:18px;line-height:40px;"
        'font-weight:700;font-family:Arial,sans-serif;">&#10003;</td>'
        f'<td style="padding-left:14px;font-family:{HEAD_FONT};font-size:19px;line-height:26px;'
        f'font-weight:700;color:{INK};">{escape(title)}</td></tr></table>'
    )


def _field(label: str, value: str, link: str | None = None) -> str:
    """A labelled value in a white box (the owner's credentials style)."""
    shown = (
        f'<a href="{escape(link, quote=True)}" target="_blank" style="color:{BRAND};'
        f'text-decoration:none;">{escape(value)}</a>'
        if link
        else escape(value)
    )
    return (
        '<tr><td style="padding:0 0 12px 0;">'
        f'<p style="margin:0 0 6px 0;font-size:11px;line-height:14px;font-weight:700;'
        f'letter-spacing:1px;text-transform:uppercase;color:{MUTED};">{escape(label)}</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:#ffffff;border:1px solid {CARD_LINE};border-radius:10px;"><tr>'
        f'<td style="padding:13px 16px;font-family:{MONO};font-size:15px;line-height:22px;'
        f'font-weight:700;color:{INK};word-break:break-all;">{shown}</td></tr></table>'
        "</td></tr>"
    )


def _fields(rows: Sequence[tuple[str, str]]) -> str:
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        + "".join(_field(label, value) for label, value in rows)
        + "</table>"
    )


def _detail_rows(rows: Sequence[tuple[str, str]]) -> str:
    def top(index: int) -> str:
        return f"border-top:1px solid {CARD_LINE};" if index else ""

    cells = "".join(
        "<tr>"
        f'<td style="padding:11px 0;{top(index)}color:{MUTED};font-size:14px;line-height:20px;'
        f'width:42%;vertical-align:top;">{escape(label)}</td>'
        f'<td style="padding:11px 0;{top(index)}color:{INK};font-size:14px;line-height:20px;'
        f'font-weight:700;text-align:right;word-break:break-word;">{escape(value)}</td></tr>'
        for index, (label, value) in enumerate(rows)
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f"{cells}</table>"
    )


def _table(table: Sequence[Sequence[str]]) -> str:
    if len(table) < 2:
        return ""
    head, *body = table

    def align(index: int) -> str:
        return "left" if index < 2 else "right"

    heads = "".join(
        f'<th style="padding:9px 6px;border-bottom:1px solid {CARD_LINE};color:{MUTED};'
        f"font-size:11px;font-weight:700;text-align:{align(i)};text-transform:uppercase;"
        f'letter-spacing:.6px;">{escape(cell)}</th>'
        for i, cell in enumerate(head)
    )
    rows = "".join(
        "<tr>"
        + "".join(
            f'<td style="padding:9px 6px;border-bottom:1px solid {CARD_LINE};color:{INK};'
            f'font-size:13px;line-height:19px;text-align:{align(i)};">{escape(cell)}</td>'
            for i, cell in enumerate(row)
        )
        + "</tr>"
        for row in body
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;"><tr>{heads}</tr>{rows}</table>'
    )


def _button(label: str, url: str) -> str:
    safe = escape(url, quote=True)
    text = escape(label)
    return (
        '<table role="presentation" class="btn" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0"><tr><td align="center" bgcolor="{BRAND}" style="border-radius:12px;'
        f'background-color:{BRAND};">'
        f'<!--[if mso]><v:roundrect href="{safe}" style="height:54px;v-text-anchor:middle;'
        f'width:490px;" arcsize="22%" stroke="f" fillcolor="{BRAND}"><w:anchorlock/>'
        f'<center style="color:#ffffff;font-family:Arial,sans-serif;font-size:16px;'
        f'font-weight:bold;">{text}</center></v:roundrect><![endif]-->'
        f'<!--[if !mso]><!-- --><a href="{safe}" target="_blank" style="display:inline-block;'
        "width:100%;box-sizing:border-box;padding:17px 28px;"
        f"font-family:{HEAD_FONT};font-size:16px;line-height:20px;font-weight:700;color:#ffffff;"
        f'text-decoration:none;border-radius:12px;text-align:center;">{text} &nbsp;&rarr;</a>'
        "<!--<![endif]--></td></tr></table>"
    )


def _note(text: str) -> str:
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{NOTE};border-radius:12px;"><tr>'
        f'<td style="padding:16px 20px;font-family:{FONT};font-size:14px;line-height:22px;'
        f'color:{NOTE_TEXT};"><strong style="color:{BRAND};">&#9679;</strong>&nbsp; '
        f"{escape(text)}</td></tr></table>"
    )


def _sign_off(name: str | None, title: str | None, closing: Sequence[str]) -> str:
    lines = "".join(_p(line, margin="0 0 18px 0") for line in closing if line)
    if not name:
        return (
            f'<tr><td class="px" style="padding:30px 40px 24px 40px;">{lines}</td></tr>'
            if lines
            else ""
        )
    role = (
        f'<br><span style="font-size:14px;color:{MUTED};">{escape(title)} &middot; Adverse</span>'
        if title
        else ""
    )
    return (
        f'<tr><td class="px" style="padding:30px 40px 40px 40px;font-family:{FONT};'
        f'font-size:16px;line-height:26px;color:{TEXT};">{lines}'
        f'<p style="margin:0;">Warm regards,<br><strong style="color:{INK};">{escape(name)}</strong>'
        f"{role}</p></td></tr>"
    )


def _footer(phone: str | None, attachments: bool) -> str:
    number = (phone or DEFAULT_PHONE).strip()
    dial = "".join(ch for ch in number if ch.isdigit() or ch == "+")
    site = website()
    scope = "This email and its attachments are" if attachments else "This email is"
    return (
        f'<tr><td class="px" bgcolor="{BRAND}" style="padding:30px 40px;background-color:{BRAND};'
        f'font-family:{FONT};">'
        f'<img src="{escape(logo_url(white=True), quote=True)}" width="130" alt="adverse" '
        "style=\"display:block;width:130px;height:auto;font-family:Poppins,'Segoe UI',Arial,"
        'sans-serif;font-size:22px;font-weight:700;color:#ffffff;">'
        '<p style="margin:18px 0 0 0;font-size:14px;line-height:22px;color:#ffffff;">'
        f'<a href="tel:{escape(dial, quote=True)}" style="color:#ffffff;text-decoration:none;">'
        f"{escape(number)}</a>&nbsp;&nbsp;|&nbsp;&nbsp;"
        f'<a href="https://{escape(site, quote=True)}" style="color:#ffffff;text-decoration:none;">'
        f"{escape(site)}</a></p>"
        f'<p style="margin:16px 0 0 0;font-size:12px;line-height:18px;color:{FOOT_TEXT};">'
        f"{scope} confidential and intended only for the named recipient. If you received it by "
        "mistake, please notify us and delete it.</p>"
        f'<p style="margin:12px 0 0 0;font-size:12px;line-height:18px;color:{FOOT_TEXT};">'
        f"&copy; {datetime.now(UTC).year} Adverse. All rights reserved.</p></td></tr>"
    )


def _document(title: str, preheader: str, rows_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" \
xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light only">
<title>{escape(title)}</title>
<style>
  body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
  table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
  img {{ -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }}
  body {{ margin: 0 !important; padding: 0 !important; width: 100% !important; \
background-color: #ffffff; }}
  a {{ color: {BRAND}; }}
  @media only screen and (max-width: 620px) {{
    .container {{ width: 100% !important; }}
    .px {{ padding-left: 24px !important; padding-right: 24px !important; }}
    .h1 {{ font-size: 28px !important; line-height: 36px !important; }}
    .btn a {{ display: block !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background-color:#ffffff;">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;\
overflow:hidden;mso-hide:all;">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" \
style="background-color:#ffffff;">
  <tr>
    <td align="center" style="padding:24px 12px 40px 12px;">
      <table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" \
border="0" style="width:600px;max-width:600px;background-color:#ffffff;border:1px solid {BORDER};\
border-radius:20px;overflow:hidden;">
        <tr>
          <td class="px" style="padding:30px 40px 0 40px;">
            <img src="{escape(logo_url(), quote=True)}" width="170" alt="adverse" \
style="display:block;width:170px;max-width:100%;height:auto;font-family:Poppins,'Segoe UI',Arial,\
sans-serif;font-size:26px;font-weight:700;color:{BRAND};">
          </td>
        </tr>
{rows_html}
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def _hero(
    title: str, highlight: str | None, intro: str | None, eyebrow: str | None, big: bool
) -> str:
    size, line = (38, 46) if big else (30, 38)
    name = f'<br><span style="color:{BRAND};">{escape(highlight)}</span>' if highlight else ""
    kicker = (
        f'<p style="margin:0 0 12px 0;font-family:{FONT};font-size:12px;line-height:16px;'
        f'font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:{BRAND};">'
        f"{escape(eyebrow)}</p>"
        if eyebrow
        else ""
    )
    lead = _p(intro, size=17, line=28, margin="18px 0 0 0") if intro else ""
    return (
        f'<tr><td class="px" style="padding:44px 40px 0 40px;font-family:{HEAD_FONT};">{kicker}'
        f'<h1 class="h1" style="margin:0;font-size:{size}px;line-height:{line}px;font-weight:700;'
        f'letter-spacing:-0.8px;color:{INK};">{escape(title)}{name}</h1>{lead}</td></tr>'
    )


# -- every mail ---------------------------------------------------------------------------------


def render_mail(
    *,
    title: str,
    lines: Sequence[str] = (),
    greeting: str | None = None,
    rows: Sequence[tuple[str, str]] = (),
    table: Sequence[Sequence[str]] = (),
    action_label: str | None = None,
    action_url: str | None = None,
    after: Sequence[str] = (),
    sign_off: str | None = "Team Adverse",
    footnote: str | None = None,
    company: str = "Adverse",
    monospace_rows: bool = False,
    code: str | None = None,
    show_link: bool = False,
    eyebrow: str | None = None,
    highlight: tuple[str, str] | None = None,
    name_highlight: str | None = None,
    signer_title: str | None = None,
    phone: str | None = None,
    preheader: str | None = None,
    attachments: bool = False,
) -> str:
    """The HTML of one mail. `lines[0]` is the lead under the heading; `after` are lines above
    the sign-off; `code` shows a one-time code; `show_link` prints the button's address for mail
    apps that block buttons; `name_highlight` puts a name on its own line in brand blue."""
    texts = [line for line in lines if line]
    intro, rest = (texts[0], texts[1:]) if texts else (None, [])
    detail = [(label, value) for label, value in rows if value]
    if highlight is None:
        found = next((pair for pair in detail if pair[0].strip().lower() in _MONEY_LABELS), None)
        if found is not None:
            highlight = found
            detail = [pair for pair in detail if pair is not found]
    parts = [_hero(title, name_highlight, intro, eyebrow, big=bool(name_highlight))]
    if greeting:
        parts.append(_section(_p(greeting, color=INK, margin="0"), 24))
    if rest:
        parts.append(_section("".join(_p(line) for line in rest), 20))
    if highlight:
        parts.append(
            _section(
                _card(
                    f'<p style="margin:0;font-size:12px;line-height:16px;font-weight:700;'
                    f'letter-spacing:1px;text-transform:uppercase;color:{MUTED};">'
                    f"{escape(highlight[0])}</p>"
                    f'<p style="margin:6px 0 0 0;font-family:{HEAD_FONT};font-size:30px;'
                    f'line-height:38px;font-weight:700;color:{INK};">{escape(highlight[1])}</p>',
                    "22px 26px",
                )
            )
        )
    if code:
        parts.append(
            _section(
                _card(
                    f'<p style="margin:0;text-align:center;font-family:{MONO};font-size:32px;'
                    f'line-height:40px;font-weight:700;letter-spacing:10px;color:{INK};">'
                    f"{escape(code)}</p>",
                    "22px 26px",
                )
            )
        )
    if detail:
        inner = _fields(detail) if monospace_rows else _detail_rows(detail)
        parts.append(_section(_card(inner, "18px 26px 8px 26px" if monospace_rows else "8px 24px")))
    if len(table) >= 2:
        parts.append(_section(_card(_table(table), "12px 18px 16px 18px")))
    if action_label and action_url:
        parts.append(_section(_button(action_label, action_url), 30))
        if show_link:
            parts.append(
                _section(
                    f'<p style="margin:0;font-family:{FONT};font-size:13px;line-height:20px;'
                    f'color:{MUTED};">If the button does not open, use this link: '
                    f'<a href="{escape(action_url, quote=True)}" style="color:{BRAND};'
                    f'word-break:break-all;">{escape(action_url)}</a></p>',
                    16,
                )
            )
    if footnote:
        parts.append(_section(_note(footnote)))
    signer = sign_off or None
    parts.append(_sign_off(signer, signer_title, after))
    if not signer and not after:
        parts.append('<tr><td style="padding:0 0 40px 0;"></td></tr>')
    parts.append(_footer(phone, attachments))
    return _document(title, preheader or intro or title, "\n".join(parts))


# -- the two account mails (owner templates) ----------------------------------------------------


def render_onboarding_mail(
    *,
    name: str,
    audience: str,
    company: str,
    username: str,
    agreement_url: str,
    respond_by: str,
    signer_name: str,
    signer_title: str | None,
    phone: str | None = None,
    has_attachments: bool = True,
) -> str:
    """The first mail to a new client, employee or manager (owner request 2026-11-27): an
    onboarding mail, not a welcome. Their username, the role's documents attached, and one button
    to the agreement and form, where they also set their password."""
    if audience == "CLIENT":
        intro = (
            f"We are excited to start working with {company}. Before we begin, there is a short "
            "onboarding: your documents are attached to this email. Review the agreement, fill in "
            "the onboarding form and set your password, and we will get started right away."
        )
        card_text = (
            "It covers our scope of work, deliverables and payment terms. Take your time to read "
            "it, then accept it, add a few details about your brand and set your password."
        )
        deadline = f"Please complete this by {respond_by} so we can schedule your kickoff call."
    else:
        role = "a manager" if audience == "MANAGER" else "a member of the team"
        intro = (
            f"We are onboarding you as {role} at Adverse. Your offer letter, joining letter and "
            "agreement are attached to this email. Review them, accept the agreement, fill in the "
            "onboarding form and set your password to finish."
        )
        card_text = (
            "Read the documents and our rules, then accept them and add your personal details, "
            "ID proof and bank details. You will set your password at the end."
        )
        deadline = f"Please complete your onboarding by {respond_by}; the link stops working then."
    card = (
        _card_title("Your agreement is ready")
        + _p(card_text, size=15, line=24, margin="0 0 20px 0")
        + _fields([("Your username", username)])
        + '<div style="height:8px;line-height:8px;">&nbsp;</div>'
        + _button("Review & Accept Agreement", agreement_url)
        + _p(
            "Use this username to sign in once your onboarding is complete.",
            size=13,
            line=20,
            color=MUTED,
            margin="16px 0 0 0",
        )
    )
    parts = [
        _hero("Let's get you onboarded,", name, intro, None, big=True),
        _section(_card(card, "28px 28px 26px 28px"), 32),
        _section(_note(deadline)),
        _sign_off(
            signer_name,
            signer_title,
            ["Have a question? Just reply to this email, we are happy to help."],
        ),
        _footer(phone, has_attachments),
    ]
    return _document(
        f"Onboarding at {company}",
        "Your onboarding documents are attached. Review and accept the agreement to get started.",
        "\n".join(parts),
    )


def render_welcome_mail(
    *,
    name: str,
    audience: str,
    company: str,
    login_url: str,
    username: str,
    password: str | None,
    signer_name: str,
    signer_title: str | None,
    phone: str | None = None,
    has_attachments: bool = False,
) -> str:
    """After onboarding (owner request 2026-11-27): their login link, username and the password
    they chose. `password=None` leaves it out (the copy in their own Adverse mailbox)."""
    if audience == "CLIENT":
        intro = (
            f"Thank you for choosing Adverse. We are excited to be part of {company}'s growth "
            "story, and your account is now ready. Your login details are below."
        )
    else:
        intro = (
            "Your onboarding is complete and your Adverse account is ready. Your login details "
            "are below; your tasks, mail and documents are all inside."
        )
    rows = [("Login link", login_url), ("Username", username)]
    if password:
        rows.append(("Password", password))
    fields = "".join(
        _field(label, value, link=value if label == "Login link" else None) for label, value in rows
    )
    card = (
        _card_title("Your login details")
        + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        + fields
        + "</table>"
        + _p(
            (
                "For your security, please do not share these login details with anyone."
                if password
                else "Your password is the one you chose during onboarding; it is never shown here."
            ),
            size=13,
            line=20,
            color=MUTED,
            margin="6px 0 12px 0",
        )
    )
    if has_attachments:
        card += _p(
            "Your signed documents are attached for your records.",
            size=13,
            line=20,
            color=MUTED,
            margin="0 0 12px 0",
        )
    parts = [
        _hero("Welcome to Adverse,", name, intro, None, big=True),
        _section(_card(card), 32),
        _sign_off(
            signer_name,
            signer_title,
            [
                "We are so glad to have you with us. If you need anything at all, just reply to "
                "this email and we will be right there."
            ],
        ),
        _footer(phone, has_attachments),
    ]
    return _document(
        f"Welcome to {company}",
        "Your account is ready. Your login details are inside.",
        "\n".join(parts),
    )
