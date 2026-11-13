# Multi-Tenant Foundation

## Architecture

Loopless is a multi-tenant SaaS where each company is an isolated tenant. Company-owned records always carry a `company_id`; global platform records remain outside tenant ownership.

```text
Loopless
├── Company A data
├── Company B data
└── Company C data
```

The current company-specific model is `User`, whose company reference remains nullable only for platform-level users. Company, Role, Module, Permission, and RolePermission are foundation/global records. Future Projects, Tasks, Clients, and other business models must include a required company reference when they are introduced.

## Request Context

Tenant-scoped requests supply:

```http
X-Company-ID: <company UUID>
```

The header selects the request context but is never trusted as authorization. `/tenant/context` requires a valid access token and the header company must exactly match the JWT `company_id`. The middleware rejects missing and malformed identifiers, unknown companies, and companies that are not active; the authenticated route rejects anonymous, platform, and cross-tenant context requests.

Global infrastructure routes do not require tenant context:

- `/health`
- `/docs`
- `/redoc`
- `/openapi.json`

## Tenant Request Flow

```text
Request
  -> TenantContextMiddleware
  -> TenantService
  -> TenantRepository
  -> companies table
  -> request.state.tenant
  -> route/service/repository
```

`request.state.tenant` is available for the complete request lifecycle after validation. Company-owned repositories receive the validated JWT tenant and include `company_id` in every company-owned query.

## Company Statuses

- `ACTIVE`: tenant requests are allowed.
- `INACTIVE`: tenant requests are denied.
- `SUSPENDED`: tenant requests are denied.
- `PENDING`: tenant requests are denied until activation.

## Foundation Components

- `TenantRepository`: find, get, existence, and schema-readiness checks.
- `TenantService`: identifier validation, company lookup, and status validation.
- `TenantContextMiddleware`: context extraction, validation, error responses, and request attachment.
- `GET /tenant/context`: returns only the authenticated user's matching company context.
- JWT and active-session validation prevent a header from granting access to another company.

## Isolation Rules

1. Never query company-owned data without a validated tenant context.
2. Pass the current company identifier through service and repository layers.
3. Filter every company-owned read, update, and delete by `company_id`.
4. Never accept a target company identifier from a business payload when a validated context already exists.
5. Keep platform-global entities explicitly outside tenant filtering.

## Cross-Tenant Test Scenarios

| Scenario | Expected result |
| --- | --- |
| Missing `X-Company-ID` | Request denied with `400` |
| Invalid UUID | Request denied with `400` |
| Unknown company | Request denied with `404` |
| Inactive, suspended, or pending company | Request denied with `403` |
| Active Company A context | Company A attached to request |
| Company A JWT with Company B header | Request denied with `403 TENANT_CONTEXT_MISMATCH` |
| Platform JWT with a company header | Request denied with `403 TENANT_CONTEXT_MISMATCH` |
| Company A requests a Company B record | Repository company filter returns no record; access denied |
