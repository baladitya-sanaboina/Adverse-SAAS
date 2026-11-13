# Frontend Authentication

## Scope

Day-15 integrates authentication into the existing, unchanged login and dashboard UI for PlatformOwner, Developer, CompanyAdmin, CompanyEmployee, and CompanyClient. Registration, Forgot Password, and onboarding are outside this scope.

## Login flow

Each login form validates required email/password fields, email format through the existing email input, and an eight-character minimum password. Duplicate submissions are disabled while `Loading...` is shown.

```text
Login form -> Next.js BFF -> POST /auth/login -> GET /users/me
           -> validate workspace role -> secure cookies -> dashboard
```

Each frontend accepts only its assigned role. A valid account used in the wrong workspace is logged out and receives `403 ROLE_NOT_ALLOWED`.

## Secure token storage

Access and refresh tokens are stored only in app-specific `HttpOnly`, `SameSite=Lax` cookies. Production cookies are also `Secure`. Tokens are never written to local storage or exposed in the UI. Local storage is used only for the optional remembered email and existing theme preference.

## Protected routes

Every application's `proxy.ts` protects its dashboard and module routes. Missing session cookies redirect to `/login`. The dashboard shell then calls the local `/api/auth/me` BFF endpoint, which verifies the backend session and expected role before rendering.

## Refresh flow

When `/users/me` returns `401`, the BFF uses the HttpOnly refresh cookie with `POST /auth/refresh`, stores the rotated access and refresh tokens, and retries `/users/me`. If refresh fails, both cookies are cleared and the user returns to login.

## Permission navigation

The dashboard shell loads permissions from `/users/me`. Business-module sidebar links are filtered by the backend module grants. Dashboard and non-business shell utilities remain available. Icons, breadcrumbs, Poppins typography, layout, and responsive styling are unchanged.

## Logout

The existing sidebar action calls the local logout BFF, which invokes `POST /auth/logout`, clears both HttpOnly cookies, clears the in-memory user context, and redirects to `/login`. Other device sessions remain independent.

## Errors

- Invalid credentials are displayed using the backend-safe message.
- Inactive users/companies and wrong-workspace roles show clear errors.
- Invalid, expired, or revoked sessions clear cookies and redirect to login.
- Backend connectivity failures use a generic authentication error without exposing tokens or internal details.

## App role mapping

| Frontend | Required role |
| --- | --- |
| PlatformOwner | `PLATFORM_OWNER` |
| Developer | `DEVELOPER` |
| CompanyAdmin | `COMPANY_ADMIN` |
| CompanyEmployee | `COMPANY_EMPLOYEE` |
| CompanyClient | `COMPANY_CLIENT` |
