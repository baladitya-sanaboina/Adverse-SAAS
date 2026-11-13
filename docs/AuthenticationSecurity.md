# Authentication Security

Day-20 hardens the existing Loopless authentication flow. It does not add a new authentication feature or change the frontend login design.

## Login protection

- A known user account is temporarily locked after five consecutive failed password attempts.
- The default lock duration is 15 minutes.
- A successful login resets the failed-attempt counter.
- An expired lock is cleared automatically when the user next supplies valid credentials.
- Repeated attempts for an unknown email and source IP are rate limited without revealing whether an account exists.
- Login responses continue to use a generic invalid-credentials message to prevent account enumeration.

The limits are configured with `LOGIN_MAX_FAILED_ATTEMPTS` and `ACCOUNT_LOCK_MINUTES`.

## Token and session lifecycle

- Access and refresh tokens are signed JWTs with separate token types and expirations.
- Refresh-token digests, not plaintext refresh tokens, are stored in `auth_sessions`.
- Refresh rotates the refresh token and invalidates reuse of its previous value.
- Logout revokes the current session.
- Password reset and password change revoke active sessions so old tokens cannot continue to access protected routes.
- Protected routes validate both the JWT and its database-backed session.

## Password and verification security

- Passwords are stored only as salted scrypt hashes.
- Password-reset and email-verification tokens are random, single-use, expire automatically, and are stored only as SHA-256 digests.
- Resending email verification invalidates the previous verification token.
- Unverified accounts cannot log in.

## Security audit events

Authentication events record the action, user when known, company when known, email, source IP when available, timestamp, and structured details. Covered actions include:

- login success and failure;
- account lock;
- refresh-token use;
- logout, token revocation, and session expiration;
- password change and password reset;
- email verification.

Audit records must never contain plaintext passwords, JWTs, refresh tokens, reset tokens, or verification tokens.

## HTTP security headers

The API adds these headers to responses:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- a restrictive `Permissions-Policy`
- `Cache-Control: no-store` on authentication and profile responses
- `Strict-Transport-Security` in production

## Operations and monitoring

`GET /health` exposes only non-sensitive authentication-security status: rate limiter health, account-lock enablement, the maximum failed-attempt count, and lock duration. Swagger documents `401`, `403`, `422`, and `429` login outcomes. The Platform Owner Backend page reads the same health payload.

## Verification checklist

1. Confirm four invalid passwords return `401` and the fifth returns `429 ACCOUNT_LOCKED`.
2. Confirm a login during the lock remains blocked.
3. Confirm valid credentials work after the lock expires and reset the failure counter.
4. Confirm successful login, failed login, account lock, refresh, logout, verification, and password actions create the expected audit events.
5. Confirm protected responses include `Cache-Control: no-store` and all API responses include the common security headers.
6. Confirm the backend test suite, lint, formatting, and type checks pass.
