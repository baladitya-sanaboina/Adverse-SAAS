# Developer Management

## Scope

Day-22 gives the Platform Owner a complete Developer lifecycle. Company and subscription management remain outside this scope.

## Lifecycle

```text
Platform Owner -> Create Developer -> Assign permissions -> View/Edit -> Activate/Deactivate
```

All `/platform/developers` endpoints require a valid Platform Owner access token. Developer records remain platform users with no company tenant.

## APIs

- `POST /platform/developers` creates a Developer with a hashed password and permissions.
- `GET /platform/developers` supports page, page size, name/email search, status, created-date range, and newest/oldest/A–Z sorting.
- `GET /platform/developers/{id}` returns profile, permissions, last login, and audit history.
- `PUT /platform/developers/{id}` updates name, phone, status, and permissions. Email, role, company, password hash, and system identifiers are protected.
- `PATCH /platform/developers/{id}/status` activates or deactivates a Developer.

## Permissions

Developer permissions are stored in `user_permissions`, scoped to one Developer. If no explicit user permissions exist, the existing role permissions remain the fallback for compatibility. Permission module/action pairs must exist in the RBAC catalog.

## Status management

Supported management statuses are `ACTIVE` and `INACTIVE`. Deactivation revokes all active sessions, so an inactive Developer cannot continue using an existing token or log in again.

## Audit logging

`developer_audits` records Developer creation, updates, activation, deactivation, permission changes, Platform Owner actor, target Developer, details, and timestamp.

## Validation

- First and last name are required.
- Email must be valid and globally unique.
- Phone must use a supported international/numeric format.
- Password requires at least 12 characters with uppercase, lowercase, number, and symbol.
- Protected system fields are rejected by update request validation.
- Permission pairs must exist in the RBAC catalog.

## Frontend

The Platform Owner Developers page provides list/create/view/edit modes, responsive table rows, search debounce, status and created-date filters, sorting, pagination, permission selection, loading/empty/error states, and activation/deactivation controls while retaining the Loopless dashboard shell and theme.
