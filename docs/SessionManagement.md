# Session Management

## Scope

Day-13 completes session security with refresh-token rotation, logout, revocation, expiration handling, independent multi-device sessions, and authentication security events. Forgot Password, Email Verification, MFA, and the Day-14 `/users/me` API are not included.

## Login flow

Each successful `POST /auth/login` creates an independent database session. Laptop, mobile, and tablet logins therefore receive different session IDs and refresh tokens. The session stores its user, nullable company, login time, last activity, expiry, status, refresh-token digest, and optional device/user-agent information.

## Refresh flow

`POST /auth/refresh` validates the JWT signature, token type and expiry, then atomically matches the SHA-256 refresh-token digest against an active session. It returns a new access token and a rotated refresh token. The previous refresh token immediately becomes unusable; reuse returns `401 INVALID_REFRESH_TOKEN`.

## Logout and revocation

`POST /auth/logout` requires a valid bearer access token. It changes only the current session to `REVOKED`, replaces its refresh-token reference, and records logout and revocation events. Other device sessions remain active. Access and refresh tokens belonging to the logged-out session are rejected afterward.

## Expiration handling

Access-token expiry is enforced during JWT decoding and returns `401 INVALID_TOKEN`. Refresh-token expiry requires login again and returns `401 INVALID_REFRESH_TOKEN`. An expired database session is moved from `ACTIVE` to `EXPIRED` when encountered and cannot access protected routes.

## Session middleware

Protected routes validate the bearer token, active database session, current user status, current company status, and unchanged role/company context. Only then is authentication context attached to the request.

## Security events

`authentication_events` records `LOGIN_SUCCESS`, `LOGIN_FAILED`, `REFRESH_USED`, `LOGOUT`, `TOKEN_REVOKED`, and `SESSION_EXPIRED` with available user, session, email, details, and timestamp information.

## Token lifecycle

```text
Login -> Access + Refresh -> Protected API -> Rotate Refresh
      -> New Access + New Refresh -> Logout -> Session Revoked
```
