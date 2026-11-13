# CRM Checkpoint

## Day-50 scope

Day-50 closes the Employee, Client, and CRM checkpoint. It validates the existing implementation from Days 41-49; it does not introduce another business module.

## Validated workflow

```text
Company Admin
  -> Employee directory, profile, edit, and assignment
  -> Client list, detail, contacts, notes, feedback, and activity
  -> Lead: NEW -> CONTACTED -> QUALIFIED -> CONVERTED
  -> Opportunity: PROPOSAL -> NEGOTIATION -> WON or LOST
```

The converted Lead remains traceable from its Opportunity. Won and lost Opportunities persist with a closed status.

## Role boundaries

- Company Admin can use Employee, Client, and CRM actions allowed by the existing permission matrix.
- Company Employee sees only assigned modules and actions. Hidden controls are a convenience; backend permission checks remain authoritative.
- Company Client cannot access internal CRM pages, internal Client notes, or administrative Employee data.
- Direct routes and manipulated resource identifiers do not bypass authorization.

## Tenant boundary

Company identity is derived from the validated access token. Authenticated frontend proxy requests add the signed token's company claim as `X-Company-ID`; a caller-provided company header cannot override it. Repositories scope Employee, Client, Lead, Opportunity, contact, note, feedback, and activity queries to the authenticated company.

## API and health coverage

The existing OpenAPI document includes Employee, Client, contact, note, feedback, activity, Lead, Opportunity, and CRM option routes. Backend Health reports the Client Management and CRM Foundation service groups together with PostgreSQL and Redis connectivity.

## Verification requirements

- Exercise real API lifecycle, permission, tenant-isolation, logout, and persistence flows.
- Exercise browser clicks for directory/detail/edit actions, loading, error/retry, responsive layouts, and role-scoped navigation.
- Require zero unexpected browser console, failed-request, backend traceback, and HTTP 500 errors.
- Run backend tests and static checks plus all five frontend format, lint, type-check, and production builds.
- Remove checkpoint data and temporary permission grants after validation.
- Never commit or push this checkpoint without explicit approval.
