# Day-35 Role Management

## Boundary

Day-35 manages company-scoped roles and the permissions attached to each role. It reuses the existing `roles`, `modules`, `permissions`, and `role_permissions` foundation. Permission review and editing remain embedded in the Role create/edit workflow; no separate matrix page or permission system is introduced.

The five platform/system roles remain protected and have no tenant owner. Company Admin, Company Employee, and Company Client are visible for assignment context but cannot be edited or deleted. New custom roles belong to exactly one company and use Company Employee workspace semantics.

## APIs

- `GET /company/roles` lists current-company custom roles and the protected company system roles.
- `POST /company/roles` creates a current-company role.
- `GET /company/roles/permissions` returns the reusable module/action selector catalog.
- `GET /company/roles/{role_id}` returns role details and permission keys.
- `PATCH /company/roles/{role_id}` updates name, description, status, or permission mappings atomically.
- `DELETE /company/roles/{role_id}` deletes only an unassigned custom role.

All routes derive the company from the authenticated JWT. They never accept a client-selected company ID. Cross-tenant and protected-system-role mutations return a tenant-scoped not-found response. Employees and Clients receive `403`; unauthenticated requests receive `401`.

## Validation and safety

- Names are trimmed, 2–80 characters, begin with a letter, and allow the documented business-name character set.
- A case-insensitive database index prevents duplicate names inside one company while allowing the same name in different companies.
- Permission keys must resolve to existing Loopless module/action pairs.
- Permission replacement and role changes run in one transaction.
- Assigned custom roles cannot be deleted; users must first be reassigned.
- Disabled roles are rejected during login and authenticated requests.
- System roles are read-only.

## Day-34 integration

The user assignment options endpoint returns active protected company roles plus active custom roles owned by the authenticated company. Assignment validates the same boundary. Custom-role users inherit updated role permissions on the next request because effective permissions are resolved from `role_permissions` at request time.

The assignment API validates the selected role against the authenticated company, so changing an identifier cannot assign another tenant's role.

## Audit events

- `ROLE_CREATED`
- `ROLE_UPDATED`
- `ROLE_ACTIVATED`
- `ROLE_DISABLED`
- `ROLE_DELETED`
- `ROLE_PERMISSIONS_UPDATED`

Each event is stored in the organization audit stream with actor, company, role, timestamp, and change details.

## Frontend

Company Admin `/company/roles` uses the established Loopless directory/table, custom listbox, confirmation dialog, loading/error/empty states, light/dark tokens, and Poppins typography. `PermissionSelector` is reusable by the later Day-36 matrix without embedding a second permission model.
