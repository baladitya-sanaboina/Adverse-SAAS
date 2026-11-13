# User Assignments

Day-34 allows an authorized Company Admin to assign an existing company-safe role, active department, and active branch to a user in the same tenant. Role creation and permission editing remain Day-35/Day-36 scope.

## API

- `GET /company/users` lists current-tenant users and organization context.
- `GET /company/users/assignment-options` returns company roles plus active departments and branches for the authenticated tenant.
- `PATCH /company/users/{user_id}/organization` validates and updates role, department, and branch in one transaction.

The API derives the company from the authenticated JWT. It never accepts a client-provided company ID. A user or organizational record outside that company returns the same tenant-scoped not-found response, and an unauthorized user receives `403`.

Department and branch may be unassigned. Roles are limited to Company Admin, Company Employee, and Company Client until tenant role CRUD is introduced on Day-35.

Changes emit `USER_ROLE_ASSIGNED/CHANGED`, `USER_DEPARTMENT_ASSIGNED/CHANGED`, and `USER_BRANCH_ASSIGNED/CHANGED` organization audit events.
