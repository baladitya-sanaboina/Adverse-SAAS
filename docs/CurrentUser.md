# Current Authenticated User

## Scope

Day-14 adds `GET /users/me` as the primary authenticated identity endpoint for all five frontend applications. Dashboard APIs, profile editing, and frontend login integration are not included.

## Flow

```text
Bearer JWT -> Authentication middleware -> Active session
           -> Active user/company -> Role -> Permissions -> Response
```

The request must include `Authorization: Bearer <access-token>`. Authentication middleware validates the JWT expiry, database session, current user status, company status, and unchanged token context before the Current User service loads the profile.

## Response

The response consistently contains:

- `user`: ID, name, email, status, and created date.
- `company`: tenant ID, name, code, subscription plan, and status; `null` for platform users without a company.
- `role`: ID, name, and code.
- `permissions`: ordered module/action grants with both codes and display names.

Passwords, password hashes, refresh tokens, session secrets, and internal configuration are never returned.

## Permission loading

Permissions are loaded from the authenticated user's role through `role_permissions`, `modules`, and `permissions`. Frontends can use the returned module/action pairs later to decide sidebar items, pages, buttons, and widgets. The backend remains the authorization authority.

## Errors

- Missing, invalid, expired, or revoked authentication returns `401`.
- Suspended/inactive users or companies return `403`.
- A role or company context changed after token issuance returns `401 TOKEN_CONTEXT_CHANGED`.

## Swagger

`GET /users/me` is documented under the `users` group with bearer authorization, its complete response model, and `401`/`403` responses.
