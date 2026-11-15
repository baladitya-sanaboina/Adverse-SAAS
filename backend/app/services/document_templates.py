"""Standard onboarding documents (owner request 2026-11-15: "nenu standard text rasta").

The admin can change any of them on the Documents page; the company's own version is stored in
document_templates and these defaults are used until then. Placeholders in {{double braces}} are
filled when a document is sent; anything unknown is left out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateDefault:
    kind: str
    audience: str  # CLIENT or EMPLOYEE
    label: str
    signable: bool  # the recipient accepts it online
    subject: str
    body: str


PLACEHOLDERS: dict[str, list[str]] = {
    "CLIENT": [
        "company_name",
        "company_email",
        "company_phone",
        "client_name",
        "contact_name",
        "date",
        "link_expires",
    ],
    "EMPLOYEE": [
        "company_name",
        "company_email",
        "company_phone",
        "employee_name",
        "job_title",
        "monthly_salary",
        "joining_date",
        "reporting_to",
        "work_location",
        "probation_months",
        "notice_days",
        "date",
        "link_expires",
    ],
}

DEFAULTS: tuple[TemplateDefault, ...] = (
    TemplateDefault(
        "CLIENT_WELCOME",
        "CLIENT",
        "Welcome email",
        False,
        "Welcome to {{company_name}}",
        """Hello {{contact_name}},

Welcome to {{company_name}}. We are glad to be making videos for {{client_name}}.

To get started, please open the link in this email. It has three short steps:
1. A quick onboarding form about your brand, channels and contacts.
2. Our service agreement to read and accept.
3. Nothing else: we will set up your content calendar and billing from your answers.

The link is private to you and works until {{link_expires}}.

If you have any questions, reply to {{company_email}} or call {{company_phone}}.

Warm regards,
{{company_name}}""",
    ),
    TemplateDefault(
        "CLIENT_ONBOARDING",
        "CLIENT",
        "Onboarding form",
        False,
        "Tell us about {{client_name}}",
        """These details help our team plan your content from day one: who to talk to, where you
post, what your brand looks like and when you like to publish. You can change anything later
by messaging us.""",
    ),
    TemplateDefault(
        "CLIENT_AGREEMENT",
        "CLIENT",
        "Service agreement",
        True,
        "Service agreement · {{company_name}} and {{client_name}}",
        """SERVICE AGREEMENT

This agreement is made on {{date}} between {{company_name}} ("the Agency") and {{client_name}}
("the Client").

1. Services
The Agency produces and edits short-form and long-form videos, carousels, thumbnails and related
content as agreed with the Client for each piece of work.

2. Pricing
Each piece of work is billed at the rate agreed for that type of work, or under the monthly
package agreed in writing. Rates for new types of work are agreed before the work starts.

3. Payment
The Client pays in advance by top-up. Work is drawn from the money paid in; a statement is shared
for every payment. Invoices are due within 7 days of the invoice date unless written otherwise.
Applicable taxes (such as GST) are added where they apply.

4. Revisions
Each piece of work includes up to two rounds of revisions on the agreed brief. Changes to the
brief after work starts may be billed as new work.

5. Content and ownership
The Client confirms it has the rights to all material it provides. Once paid for, the final
videos belong to the Client. The Agency may show the work in its portfolio unless the Client asks
it not to in writing.

6. Timelines
The Agency will meet the dates agreed for each piece of work, provided the Client shares
footage, scripts and feedback on time.

7. Confidentiality
Both sides keep each other's business information private, during this agreement and after it.

8. Ending the agreement
Either side may end this agreement with 15 days' written notice. Work approved until then is
billed, and any money left from top-ups is refunded or carried as agreed.

9. Liability
The Agency's total liability is limited to the amount paid for the work concerned.

10. Law
This agreement is governed by the laws of India.

By accepting online, the Client agrees to these terms.""",
    ),
    TemplateDefault(
        "EMPLOYEE_WELCOME",
        "EMPLOYEE",
        "Welcome email",
        False,
        "Welcome to {{company_name}}, {{employee_name}}",
        """Hello {{employee_name}},

Welcome to {{company_name}}! We are excited to have you join us as {{job_title}}.

Your documents are ready at the private link in this email. Please read them and accept them
online before {{link_expires}}.

On your first day ({{joining_date}}) you will meet {{reporting_to}}, get your Adverse account and
see your first tasks.

See you soon,
{{company_name}}""",
    ),
    TemplateDefault(
        "EMPLOYEE_OFFER",
        "EMPLOYEE",
        "Offer letter",
        True,
        "Offer letter · {{job_title}}",
        """OFFER LETTER

Date: {{date}}

Dear {{employee_name}},

We are pleased to offer you the position of {{job_title}} at {{company_name}}.

Monthly salary: {{monthly_salary}}
Date of joining: {{joining_date}}
Reporting to: {{reporting_to}}
Place of work: {{work_location}}
Probation: {{probation_months}} months

Your salary is paid monthly. After probation, either side may end the employment with
{{notice_days}} days' notice.

This offer is subject to the employment agreement that comes with it. Please accept it online
before {{link_expires}}.

We look forward to working with you.

{{company_name}}""",
    ),
    TemplateDefault(
        "EMPLOYEE_JOINING",
        "EMPLOYEE",
        "Joining letter",
        True,
        "Joining letter · {{employee_name}}",
        """JOINING LETTER

Date: {{date}}

Dear {{employee_name}},

This letter confirms that you join {{company_name}} as {{job_title}} on {{joining_date}}, reporting
to {{reporting_to}} at {{work_location}}.

On your first day please bring:
- A government photo ID (Aadhaar or PAN)
- Your bank account details for salary
- Recent passport-size photographs

Your Adverse account will be set up on your first day; your tasks, salary and documents are all
there.

Welcome aboard,
{{company_name}}""",
    ),
    TemplateDefault(
        "EMPLOYEE_AGREEMENT",
        "EMPLOYEE",
        "Employment agreement",
        True,
        "Employment agreement · {{company_name}}",
        """EMPLOYMENT AGREEMENT

This agreement is made on {{date}} between {{company_name}} ("the Company") and
{{employee_name}} ("the Employee").

1. Role
The Employee works as {{job_title}}, does the work assigned in Adverse to the agreed quality
and dates, and follows the Company's reasonable instructions.

2. Salary
The Company pays {{monthly_salary}} a month. Salary is reviewed once a year.

3. Probation and notice
The first {{probation_months}} months are probation. After that, either side gives
{{notice_days}} days' notice to end the employment.

4. Confidentiality
The Employee keeps the Company's and its clients' information, footage and plans private during
and after employment, and does not share client material outside the Company.

5. Work belongs to the Company
Everything the Employee makes for the Company or its clients belongs to the Company.

6. Clients
For 12 months after leaving, the Employee does not take on the Company's clients directly.

7. Conduct
The Employee treats colleagues and clients with respect and follows the Company's policies.

8. Law
This agreement is governed by the laws of India.

By accepting online, the Employee agrees to these terms.""",
    ),
)


def _unwrap(text: str) -> str:
    """Join the hard line breaks inside a paragraph (the source is wrapped at ~95 characters);
    keep list items, numbered headings and short lines on their own lines."""
    blocks = []
    for block in text.split("\n\n"):
        lines = block.split("\n")
        out = [lines[0]]
        for line in lines[1:]:
            previous = out[-1]
            starts_item = line.startswith(
                ("- ", "Monthly salary", "Date of", "Reporting", "Place", "Probation")
            )
            if len(previous) >= 60 and not starts_item and not re.match(r"^\d+\.", line):
                out[-1] = f"{previous} {line}"
            else:
                out.append(line)
        blocks.append("\n".join(out))
    return "\n\n".join(blocks)


DEFAULTS = tuple(
    TemplateDefault(
        item.kind, item.audience, item.label, item.signable, item.subject, _unwrap(item.body)
    )
    for item in DEFAULTS
)
BY_KIND = {item.kind: item for item in DEFAULTS}
CLIENT_KINDS = ["CLIENT_WELCOME", "CLIENT_ONBOARDING", "CLIENT_AGREEMENT"]
EMPLOYEE_KINDS = ["EMPLOYEE_WELCOME", "EMPLOYEE_OFFER", "EMPLOYEE_JOINING", "EMPLOYEE_AGREEMENT"]

_TOKEN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def render(text: str, values: dict[str, str]) -> str:
    """Fill {{placeholders}}; unknown ones become empty."""
    return _TOKEN.sub(lambda match: values.get(match.group(1), ""), text)
