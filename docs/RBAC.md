# RBAC Foundation

## Architecture

Loopless authorization flows only through role assignments:

```text
User -> Role -> RolePermission -> Module + Permission
```

- A user has one role.
- A role has module-specific permission grants.
- A module identifies the protected product area.
- A permission identifies one reusable action.
- `role_permissions` uses the role, module, and permission identifiers as its composite primary key, preventing duplicate grants.

Authentication, JWT extraction, login, and request-time user resolution are not implemented on Day-5.

## Roles

The seeded roles are:

1. Platform Owner
2. Developer
3. Company Admin
4. Company Employee
5. Company Client

These names describe product boundaries; they do not imply role inheritance. A role receives only grants explicitly stored in `role_permissions`.

## Modules

The seeded modules are Dashboard, Users, Companies, Employees, Clients, Projects, Tasks, CRM, Finance, Invoices, Attendance, Documents, Notifications, Reports, Settings, Subscriptions, Developers, and Tickets.

## Permissions

Permissions represent reusable single actions: View, Create, Edit, Delete, Approve, Assign, Export, Import, and Manage. “Full Access” is not stored as a special permission; it means all nine actions are granted for that module.

## Default Permission Matrix

| Role | Module | Actions |
| --- | --- | --- |
| Platform Owner | Dashboard | View, Manage |
| Platform Owner | Companies | View, Create, Edit, Delete |
| Platform Owner | Developers | All nine actions |
| Developer | Companies | View |
| Developer | Subscriptions | Manage |
| Company Admin | Employees | All nine actions |
| Company Admin | Clients | All nine actions |
| Company Admin | CRM | View, Create, Edit |
| Company Admin | Projects | All nine actions |
| Company Admin | Reports | View |
| Company Employee | Projects | View |
| Company Employee | Tasks | View, Edit |
| Company Employee | Attendance | View |
| Company Client | Projects | View |
| Company Client | Invoices | View |
| Company Client | Tickets | View |

The seed is idempotent and creates 76 default role-module-permission grants, including the Day-46 Company Admin CRM grants. It creates no demo users.

## Authorization Service

`app/services/permission_service.py` provides the foundation to:

- load a user's role;
- load all grants for a role;
- validate module access;
- validate a specific module action;
- validate RBAC seed initialization for health reporting.

`app/middleware/permissions.py` prepares reusable permission requirements such as `require_permission("PROJECTS", "VIEW")`. It is intentionally not connected to authentication or JWT middleware yet.

## Authorization Flow

```text
Future authenticated user
        |
        v
Load role code
        |
        v
Find RolePermission(module, action)
        |
   yes  |  no
 allow  |  deny (403)
```

The `/health` response reports RBAC initialization, available roles, modules, permissions, and the mapping count. Swagger documents this response, and the Platform Owner Backend APIs page renders the same inventory.

## Day-49 CRM Role Scope

Day-49 verifies the existing catalogue; it does not introduce a new role or permission.

| Area | Company Admin | Company Employee (default seed) | Company Client (default seed) |
| --- | --- | --- | --- |
| Client list/detail/contacts | Allowed by `CLIENTS:VIEW` | Denied | Denied |
| Create client | Allowed by `CLIENTS:CREATE` | Denied | Denied |
| Update client | Allowed by `CLIENTS:EDIT` | Denied | Denied |
| Manage contacts | Allowed by `CLIENTS:MANAGE` | Denied | Denied |
| Internal notes/activity | Allowed by the matching Clients action | Denied | Always blocked, including if a grant is added |
| Feedback | Allowed by `CLIENTS:VIEW/EDIT` | Denied by default; follows an assigned company role | Denied by default |
| Leads/opportunities/pipeline | `CRM:VIEW/CREATE/EDIT` | Denied by default; follows an assigned company role | Denied |
| Role management | Allowed by the existing Roles grants | Denied | Denied |
| Company settings | Allowed by the existing Settings grants | Denied | Denied |

Company Employee access remains permission-based: a company-specific role may grant the existing `CLIENTS` or `CRM` actions without creating a parallel RBAC system. Company Client accounts do not receive these grants in the default seed. Client internal notes and activity have an additional service-level role boundary.

Every protected request is resolved from the authenticated user and company context. Missing authentication returns `401`, a missing action grant returns `403`, and a resource owned by another tenant is returned as `404` to avoid disclosing that it exists. List queries are filtered by the authenticated company identifier; request payloads cannot select a different tenant.

### Day-49 Decisions and Blockers

- No new role, module, permission, or parallel authorization path was introduced.
- Company Employee access continues to use the existing company-role permission grants.
- Company Client access to internal client notes and activity remains blocked at the service boundary even if a role is misconfigured.
- Cross-tenant object lookups return `404`; missing authentication and missing permissions remain `401` and `403` respectively.
- Verification found no unresolved role-scoping blocker.
