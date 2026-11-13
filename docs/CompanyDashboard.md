# Company Admin Dashboard

Day-31 introduces the tenant-scoped Company Admin dashboard at `GET /company/dashboard`. Day-39 completes its clean KPI vertical slice for Employees, Projects, Clients, and supported Finance data.

## Boundary and authorization

- The authenticated JWT is the only source of the company identifier.
- The endpoint accepts no `companyId` or tenant query/header override.
- Access requires the `COMPANY_ADMIN` role and `DASHBOARD_VIEW` permission.
- The Day-31 migration seeds that permission for the Company Admin role; request-time RBAC checks remain authoritative.
- Repository queries always filter users and activities by the JWT company identifier.

## Response

The response includes the current company and administrator, real Employee and Client counts, the existing tenant `projects_used` usage metric, recent tenant activity, and permission-aware quick actions. Finance remains `null` until its roadmap module creates an authoritative financial data model; the dashboard never invents a monetary value.

KPI order is Employees, Projects, Clients, and Finance. A valid new company receives zero counts rather than an error. Unsupported Finance data is explicitly presented as unavailable.

## Frontend states

The Company Admin app provides skeleton loading, retryable error, useful zero-data messaging, activity and quick-action empty states, and responsive four/two/one-column KPI layouts. It reuses the existing Poppins typography, theme variables, hero grid, breadcrumb, topbar, and sidebar.

## Verification

Service tests cover separate Company A and Company B counts, tenant isolation, Company Admin enforcement, missing company context, missing Dashboard permission, and a valid empty company. Swagger exposes authentication/error contracts, Backend Health reports Company Dashboard readiness, and the Platform Owner Backend Inventory discovers the endpoint from OpenAPI.
