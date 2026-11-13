# Authentication

Day-20 security hardening is documented in [AuthenticationSecurity.md](AuthenticationSecurity.md), including failed-login protection, temporary account locks, security audit events, and HTTP security headers.

Day-18 adds email verification and account activation. Newly registered users remain `PENDING_VERIFICATION` and receive no JWT session until a valid, single-use verification link activates the account. See [EmailVerification.md](EmailVerification.md) for the complete flow.

## Scope

Day-12 provides login, JWT access and refresh tokens, authentication middleware, one protected route, and database-backed session foundations. Forgot password, reset password, MFA, logout, revocation, and refresh-token rotation are outside this day's scope.

## Flow

1. `POST /auth/login` validates the email and securely verifies the stored scrypt password hash.
2. Active user and company status are required.
3. The backend creates an `auth_sessions` record and stores only a SHA-256 digest of the refresh token.
4. A short-lived access token and longer-lived refresh token are returned with user, role, and company information.
5. Protected routes read `Authorization: Bearer <access-token>`, validate the JWT and active session, and attach authentication context to the request.

## JWT claims

Both tokens contain user ID (`sub`), role, nullable company ID, user type, session ID, issued time, expiry time, and token type. Passwords and sensitive information are never included.

Access tokens expire according to `JWT_EXPIRY_MINUTES`. Refresh tokens expire according to `JWT_REFRESH_EXPIRY_DAYS`.

## APIs

- `POST /auth/login` — returns access token, refresh token, user, role, and company context.
- `POST /auth/refresh` — validates the stored active refresh token and returns a new access token. Rotation is reserved for Day-13.
- `GET /auth/me` — protected foundation endpoint returning the validated token context.

Swagger exposes bearer authorization for the protected endpoint.

## Errors

- Invalid email input: `422 VALIDATION_ERROR`.
- Unknown email or invalid password: `401 INVALID_CREDENTIALS`.
- Missing or malformed bearer credentials: `401 AUTHENTICATION_REQUIRED` or `401 INVALID_TOKEN`.
- Suspended/inactive user: `403 USER_INACTIVE`.
- Non-active company: `403 COMPANY_INACTIVE`.
- Expired/inactive session: `401 SESSION_INACTIVE`.

## Session foundation

`auth_sessions` tracks session ID, user, refresh-token digest, login time, last activity, expiry, optional device information, and status (`ACTIVE`, `REVOKED`, `EXPIRED`). Day-13 extends rotation, logout, revocation, and expiration management.
