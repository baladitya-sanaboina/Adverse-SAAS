# Email Verification and Account Activation

## Flow

New users created through the authorized registration APIs start with `PENDING_VERIFICATION`. Registration creates a secure verification link for the role-specific frontend. Login is denied with `EMAIL_NOT_VERIFIED` until verification activates the account.

## Token lifecycle

- Raw tokens are generated with a cryptographically secure random source and delivered only in the email link.
- PostgreSQL stores only a SHA-256 token hash, user ID, creation time, and expiry time.
- Tokens expire after `EMAIL_VERIFICATION_EXPIRY_MINUTES` (60 minutes by default).
- Verification deletes the token and activates the pending user in one transaction.
- A consumed token cannot be replayed.

## APIs

- `POST /auth/send-verification-email` accepts an email address and issues a link for a pending account.
- `GET /auth/verify-email?token=...` validates the link and activates the account.
- `POST /auth/resend-verification` replaces the previous token and is protected by `EMAIL_VERIFICATION_RESEND_SECONDS` (60 seconds by default).

Unknown addresses receive the same successful send response. Active, inactive, and suspended accounts are not issued verification tokens.

## Frontend states

All five role applications expose `/verify-email` with waiting, verifying, success, failure, and expired-link states. The page reuses the existing Loopless authentication theme, Poppins typography, responsive card, loading indicator, inline email validation, and resend flow.

## Development delivery

Docker development sends role-specific verification links through Mailpit and exposes captured messages at `http://localhost:8025`. Production requires a real SMTP provider and verified sender configuration. Never commit SMTP credentials.
