# Password Recovery

## Flow

All five Loopless user types use the same recovery mechanism:

1. Open **Forgot password** from the role application's login page.
2. Submit the account email to `POST /auth/forgot-password`.
3. The backend returns the same generic response whether the account exists or not.
4. An eligible active user receives a role-specific `/reset-password?token=...` link.
5. Submit the token and matching strong passwords to `POST /auth/reset-password`.
6. The password hash is updated, the token becomes unusable, all active sessions are revoked, and the user signs in again.

No email verification or MFA is included in Day-17.

## Token lifecycle

- Tokens are generated with a cryptographically secure random generator.
- Only the SHA-256 token hash is persisted in `password_reset_tokens`; the raw token is never stored in the database.
- Tokens expire after `PASSWORD_RESET_EXPIRY_MINUTES` (30 minutes by default).
- Requesting another link replaces the user's previous unused token.
- Used, expired, malformed and unknown tokens are rejected.
- A consumed token cannot be reused.

## Email delivery

Local Docker development sends reset links through Mailpit; captured messages are available at `http://localhost:8025`. Production must configure a trusted SMTP provider, credentials, TLS, and a verified sender address.

## Password rules

Passwords require at least 12 characters, including uppercase and lowercase letters, a number and a special character. Confirmation must match. Frontend inline validation and backend validation enforce the same rules.

## Security and errors

- Forgot Password never reveals whether an email exists.
- Reset tokens are single-use, time-limited and compared by hash.
- Successful reset revokes all active access/refresh sessions.
- Invalid, expired, used and inactive-account cases return consistent error codes.
- The emailed 6-digit code can be checked at most 5 times. After that the code is refused with `RESET_ATTEMPTS_EXCEEDED` (429) until a new code is requested, and a new code is sent at most once a minute. Email verification codes have the same 5-check limit (`VERIFICATION_ATTEMPTS_EXCEEDED`).
- The UI provides loading, success, network error, password visibility and strength states.
