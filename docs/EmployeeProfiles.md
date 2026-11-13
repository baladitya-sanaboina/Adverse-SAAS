# Employee Profile Foundation

## Boundary

`User` remains the authentication and account identity. `Employee` is the company business profile for that existing user. Passwords, login status, sessions, and permissions are not duplicated in the Employee model.

## Data model

Each Employee contains:

- tenant-owned `company_id`;
- globally one-to-one `user_id`;
- tenant-unique `employee_code`;
- required Department, Branch, and existing RBAC Role relationships;
- `PENDING`, `ACTIVE`, or `INACTIVE` lifecycle status;
- creation and update timestamps.

The database enforces foreign keys, one profile per User, and `UNIQUE(company_id, employee_code)`. Employee changes are recorded in `employee_audits` with actor, tenant, employee, action, details, and timestamp.

## API

All endpoints derive the company from the validated JWT and require the corresponding Company Admin `EMPLOYEES` permission.

| Method | Path | Permission | Purpose |
| --- | --- | --- | --- |
| `POST` | `/company/employees` | `EMPLOYEES.CREATE` | Create a profile for an existing company User. |
| `GET` | `/company/employees` | `EMPLOYEES.VIEW` | List only current-tenant profiles with search, pagination, and relationship/status filters. |
| `GET` | `/company/employees/{employeeId}` | `EMPLOYEES.VIEW` | Read one current-tenant profile. |
| `PATCH` | `/company/employees/{employeeId}` | `EMPLOYEES.EDIT` | Update permitted identity fields, code, organization relationships, role, or status. |

There is no hard-delete endpoint. Lifecycle preservation uses Employee status.

## Relationship validation

Creation and updates reject missing or cross-tenant Users, Departments, Branches, and Roles. System company roles are accepted only from the existing Company Admin, Company Employee, and Company Client role set. Department, Branch, and Role changes update the related User assignment in the same database transaction so Employee data cannot become a second independent RBAC system.

Cross-tenant profile identifiers return `404`, unauthenticated requests return `401`, and unauthorized roles or missing permissions return `403`.

## Migration workflow

Apply migrations through the existing Docker migration service:

```text
docker compose -f docker/docker-compose.yml run --rm migrations
```

Current Day-41 migration: `20260810170000_employee_profile_foundation`.

Day-43 compatibility migration: `20260815090000_employee_directory_backfill`. It makes Department
and Branch optional until the existing User Assignment flow is completed, backfills profiles for
existing tenant Employee accounts, and keeps future Employee registrations visible in the directory.

Day-43 (API version `0.33.0`) list query parameters are `search`, `page`, `page_size`, `status`, `department_id`,
`branch_id`, and `role_id`. Every filter is applied together with the company ID
derived from the authenticated session; no tenant identifier is accepted from the client.

## Deferred scope

HR lifecycle, attendance, leave, payroll, and employee self-service remain outside the Employee Directory scope.
