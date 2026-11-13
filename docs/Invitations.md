# User Invitations

Day-33 adds tenant-scoped user invitations for Company Admin users. It does not add role, department, or branch assignment; those remain later milestones.

## Lifecycle

An invitation is created as `PENDING`, expires after 48 hours, and becomes `ACCEPTED`, `EXPIRED`, or `REVOKED`. The email contains the one-time raw token. PostgreSQL stores only its SHA-256 hash. Resending rotates the token and invalidates the previous link.

Invitation acceptance derives the company and email exclusively from the stored invitation. The public request cannot select or override a tenant. Day-33 provisions the accepted account with the fixed `COMPANY_EMPLOYEE` base role; role assignment starts in Day-34.

## APIs

- `POST /company/invitations` — create and email an invitation.
- `GET /company/invitations` — list invitations for the authenticated company.
- `GET /company/invitations/{invitationId}` — read a tenant-owned invitation.
- `POST /company/invitations/{invitationId}/resend` — rotate and resend an available invitation.
- `POST /company/invitations/{invitationId}/revoke` — revoke an invitation.
- `GET /company/invitations/validate?token=...` — validate the public link.
- `POST /company/invitations/accept` — create the invited account.

Management endpoints require a Company Admin JWT and the relevant `INVITATIONS` permission. Public validation and acceptance use the secure invitation token. Duplicate users and duplicate pending company invitations are rejected.

## UI and email

The Company Admin Invitations page provides loading, empty, error, list, create, resend, and revoke states. The public acceptance screen reuses the existing responsive Loopless login theme, Poppins typography, light/dark modes, inline validation, and password visibility controls. The branded SMTP email includes the company name, expiration notice, and secure setup link; it never includes a password.

## Audit and operations

`USER_INVITATION_CREATED`, `USER_INVITATION_RESENT`, `USER_INVITATION_REVOKED`, and `USER_INVITATION_ACCEPTED` are retained with tenant, actor, invitation, details, and timestamp. Swagger, Backend Health, and the Platform Owner API Inventory read the same seven endpoints and Invitation Service health state.
