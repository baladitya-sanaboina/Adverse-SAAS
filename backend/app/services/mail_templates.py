"""One layout for every mail that leaves Adverse (owner request 2026-11-19: the old mails looked
generated, with a coloured stripe on the card, a pill label and a "did not request this" footer on
every mail). Plain and professional: the Adverse logo, a white card, a greeting, short lines,
detail rows, an optional item table, one button, a sign-off and a small footer. Email-client safe:
tables and inline styles only, light colours, no web fonts required.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from app.core.settings import settings

INK = "#1F2937"
TEXT = "#374151"
MUTED = "#6B7280"
LINE = "#E5E7EB"
BRAND = "#0876ED"
PAGE = "#F5F7FA"
FONT = "'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_MONEY_LABELS = ("amount", "total", "balance", "amount due", "balance due", "advance left now")


def logo_url() -> str:
    origins = settings.allowed_origins or ["http://localhost:3000"]
    return f"{origins[0].rstrip('/')}/logos/adverse-logo-blue.png"


def _paragraph(text: str) -> str:
    return (
        f'<p style="margin:0 0 14px;color:{TEXT};font-size:15px;line-height:1.65;">'
        f"{escape(text)}</p>"
    )


def _top(index: int) -> str:
    return f"border-top:1px solid {LINE};" if index else ""


def _rows(rows: Sequence[tuple[str, str]], monospace: bool) -> str:
    if not rows:
        return ""
    value_font = "Menlo,Consolas,'Courier New',monospace" if monospace else FONT
    filled = [(label, value) for label, value in rows if value]
    cells = "".join(
        "<tr>"
        f'<td style="padding:12px 0;{_top(index)}color:{MUTED};font-size:13px;'
        f'width:38%;vertical-align:top;">{escape(label)}</td>'
        f'<td style="padding:12px 0;{_top(index)}color:{INK};font-size:14px;'
        f"font-weight:600;font-family:{value_font};text-align:right;word-break:break-word;"
        f'">{escape(value)}</td>'
        "</tr>"
        for index, (label, value) in enumerate(filled)
    )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:6px 0 22px;padding:2px 18px;border:1px solid {LINE};border-radius:10px;">'
        f"{cells}</table>"
    )


def _table(table: Sequence[Sequence[str]]) -> str:
    if len(table) < 2:
        return ""
    head, *body = table

    def align(index: int) -> str:
        return "left" if index < 2 else "right"

    heads = "".join(
        f'<th style="padding:9px 8px;border-bottom:1px solid {LINE};color:{MUTED};font-size:11px;'
        f'font-weight:600;text-align:{align(i)};text-transform:uppercase;letter-spacing:.4px;">'
        f"{escape(cell)}</th>"
        for i, cell in enumerate(head)
    )
    rows = "".join(
        "<tr>"
        + "".join(
            f'<td style="padding:9px 8px;border-bottom:1px solid {LINE};color:{TEXT};font-size:13px;'
            f'text-align:{align(i)};">{escape(cell)}</td>'
            for i, cell in enumerate(row)
        )
        + "</tr>"
        for row in body
    )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:4px 0 22px;border-collapse:collapse;"><tr>{heads}</tr>{rows}</table>'
    )


def _button(label: str | None, url: str | None) -> str:
    if not label or not url:
        return ""
    safe = escape(url, quote=True)
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        'style="margin:6px 0 24px;"><tr>'
        f'<td style="border-radius:8px;background:{BRAND};">'
        f'<a href="{safe}" style="display:inline-block;padding:13px 26px;color:#ffffff;'
        f"font-family:{FONT};font-size:14px;font-weight:600;text-decoration:none;border-radius:8px;"
        f'">{escape(label)}</a></td></tr></table>'
    )


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
) -> str:
    """The HTML of one mail. `after` are lines below the button; `code` shows a one-time code;
    `show_link` prints the button's address for mail apps that block buttons."""
    greeting_html = (
        f'<p style="margin:0 0 16px;color:{INK};font-size:15px;font-weight:600;">'
        f"{escape(greeting)}</p>"
        if greeting
        else ""
    )
    code_html = (
        f'<div style="margin:4px 0 22px;padding:18px;border:1px solid {LINE};border-radius:10px;'
        f"background:{PAGE};text-align:center;color:{INK};font-family:Menlo,Consolas,monospace;"
        f'font-size:30px;font-weight:700;letter-spacing:8px;">{escape(code)}</div>'
        if code
        else ""
    )
    link_html = (
        f'<p style="margin:0 0 14px;color:{MUTED};font-size:12px;line-height:1.6;">'
        "If the button does not open, use this link: "
        f'<a href="{escape(action_url, quote=True)}" style="color:{BRAND};word-break:break-all;">'
        f"{escape(action_url)}</a></p>"
        if show_link and action_url
        else ""
    )
    sign_html = (
        f'<p style="margin:22px 0 0;color:{TEXT};font-size:15px;line-height:1.6;">Regards,<br>'
        f'<span style="color:{INK};font-weight:600;">{escape(sign_off)}</span></p>'
        if sign_off
        else ""
    )
    footer = escape(footnote) + "<br>" if footnote else ""
    sender = escape(company) if company != "Adverse" else "Adverse India"
    rows = [(label, value) for label, value in rows if value]
    if highlight is None:
        found = next((pair for pair in rows if pair[0].strip().lower() in _MONEY_LABELS), None)
        if found is not None:
            highlight = found
            rows = [pair for pair in rows if pair is not found]
    highlight_html = (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:4px 0 22px;"><tr><td style="padding:18px 20px;border:1px solid {LINE};'
        f'border-radius:10px;background:{PAGE};">'
        f'<div style="color:{MUTED};font-size:12px;font-weight:600;letter-spacing:.3px;">'
        f"{escape(highlight[0])}</div>"
        f'<div style="margin-top:4px;color:{INK};font-size:28px;line-height:1.2;font-weight:700;">'
        f"{escape(highlight[1])}</div></td></tr></table>"
        if highlight
        else ""
    )
    eyebrow_html = (
        f'<td align="right" style="color:{BRAND};font-size:11px;font-weight:700;'
        f'letter-spacing:1px;text-transform:uppercase;">{escape(eyebrow)}</td>'
        if eyebrow
        else "<td></td>"
    )
    body = "".join(_paragraph(line) for line in lines if line)
    tail = "".join(_paragraph(line) for line in after if line)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>{escape(title)}</title>
  </head>
  <body style="margin:0;padding:0;background:{PAGE};font-family:{FONT};color:{INK};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{PAGE};">
      <tr>
        <td align="center" style="padding:32px 14px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;">
            <tr>
              <td style="border:1px solid {LINE};border-radius:14px;background:#ffffff;overflow:hidden;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td style="padding:20px 36px;background:#F3F8FF;border-bottom:1px solid {LINE};border-radius:14px 14px 0 0;">
                      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
                        <td><img src="{escape(logo_url(), quote=True)}" width="118" alt="Adverse" style="display:block;width:118px;height:auto;border:0;color:{BRAND};font-size:20px;font-weight:700;"></td>
                        {eyebrow_html}
                      </tr></table>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:32px 36px 32px;">
                      <h1 style="margin:0 0 18px;color:{INK};font-size:22px;line-height:1.35;font-weight:700;">{escape(title)}</h1>
                      {greeting_html}{body}{highlight_html}{code_html}{_rows(rows, monospace_rows)}{_table(table)}{_button(action_label, action_url)}{link_html}{tail}{sign_html}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 8px 0;color:{MUTED};font-size:12px;line-height:1.7;text-align:center;">
                {footer}{sender} · <a href="https://adverseindia.com" style="color:{MUTED};text-decoration:underline;">adverseindia.com</a><br>You get this mail because you have an account with {sender}.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
