# Employee Directory

Day-43 provides the tenant-scoped employee directory and employee profile experience.

## Frontend flow

- `/employees` lists employee profiles with name, code, department, branch, role, and status.
- Existing Employee accounts are backfilled into the directory; newly registered Employees receive
  a minimal profile automatically and may remain unassigned until the organization assignment flow.
- Search covers employee name, email, and employee code.
- Department, branch, role, and status filters use existing tenant assignment APIs.
- Directory state is retained in URL query parameters and search/filter changes reset pagination.
- `/employees/{employeeId}` displays personal, organization, and account information.
- Users with `EMPLOYEES:EDIT` can update permitted identity, organization, and lifecycle fields.
- Loading, empty, error, pagination, desktop, tablet, and mobile-card states are implemented.

## API mapping

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/company/employees` | Tenant-scoped search, filtering, and pagination |
| `GET` | `/company/employees/{employeeId}` | Tenant-scoped employee profile |
| `PATCH` | `/company/employees/{employeeId}` | Permission-protected profile update |

Authentication, tenant context, and `EMPLOYEES` permissions are enforced by the backend. The
frontend never sends or selects a company identifier. Passwords, hashes, tokens, and secrets are
not returned by the employee schemas.

## Search and filters

`search` matches user name, user email, or employee code. `department_id`, `branch_id`, `role_id`,
`status`, `page`, and `page_size` can be combined. Every repository query includes the authenticated
company identifier before search or filter clauses are applied.

## Identity ownership

First name, last name, phone number, email, and account status remain owned by the existing User
record. Employee update writes permitted identity values back to User while keeping the Employee
record focused on employee code, organization relationships, and employee lifecycle status.
