# CRM Foundation

## Day-46 foundation

Day-46 adds the secure data and API foundation for Leads and Opportunities. It does not add the Day-47 pipeline UI, Kanban interactions, drag-and-drop stages, forecasting, analytics, Client notes, feedback, or activity timelines.

CRM records belong to an existing Loopless Company. They never create another tenant.

```text
Company 1 --- * Lead
Company 1 --- * Opportunity
Employee 1 --- * owned Lead / Opportunity
Client 1 --- * Lead / Opportunity
Lead 0..1 --- * Opportunity
```

## Data model

### Lead

`leads` stores a potential customer, optional Client relationship, required active Employee owner, source, lifecycle status, contact details, notes, and timestamps.

- Sources: `WEBSITE`, `REFERRAL`, `EMAIL`, `PHONE`, `SOCIAL`, `OTHER`.
- Statuses: `NEW`, `CONTACTED`, `QUALIFIED`, `LOST`, `CONVERTED`.
- Email uniqueness is scoped to one Company. Multiple `NULL` email values remain allowed.
- The Client is optional; a new Lead can exist before Client conversion.

### Opportunity

`opportunities` stores a qualified business opportunity with a required Client, optional originating Lead, required active Employee owner, precise `DECIMAL(18,2)` value, ISO-style three-letter currency, stage, derived status, and optional expected close date.

- Stages: `NEW`, `QUALIFIED`, `PROPOSAL`, `NEGOTIATION`, `WON`, `LOST`.
- Status is derived: `WON`/`LOST` are `CLOSED`; every other stage is `OPEN`.
- Database checks prevent negative values, invalid currency format, and contradictory stage/status combinations.
- If an originating Lead is already linked to a Client, the Opportunity must use that same Client.

Migrations:

- `20260816160000_crm_leads_opportunities` creates the CRM tables, constraints, indexes, and relationships.
- `20260816161000_crm_company_admin_permissions` grants the existing Company Admin role `CRM.VIEW`, `CRM.CREATE`, and `CRM.EDIT` without introducing a second permission system.

## Tenant and permission boundary

The company comes only from the validated JWT. Request bodies and query strings do not accept `companyId` or `tenantId`. Every list, get, create, update, and relationship query includes the authenticated Company ID.

The existing `CRM` RBAC module is reused:

| Operation | Permission |
| --- | --- |
| List/get Leads or Opportunities | `CRM.VIEW` |
| Create Leads or Opportunities | `CRM.CREATE` |
| Update Leads or Opportunities | `CRM.EDIT` |

Owner, Client, and Lead identifiers are validated inside the same transaction. Cross-tenant or missing relationships return `404`; missing authentication returns `401`; insufficient permission returns `403`.

## API inventory

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/leads` | Create a current-tenant Lead. |
| `GET` | `/leads` | Search, filter, and paginate current-tenant Leads. |
| `GET` | `/leads/{leadId}` | Get one current-tenant Lead. |
| `PATCH` | `/leads/{leadId}` | Update allowed Lead fields and lifecycle status. |
| `POST` | `/opportunities` | Create an Opportunity after validating Client, Lead, and owner. |
| `GET` | `/opportunities` | Search, filter, and paginate current-tenant Opportunities. |
| `GET` | `/opportunities/{opportunityId}` | Get one current-tenant Opportunity. |
| `PATCH` | `/opportunities/{opportunityId}` | Update Opportunity fields and derive status from stage. |
| `GET` | `/crm/options` | List active same-tenant Employee owners and Clients for the CRM workspace. |

Swagger groups these operations under `crm-leads` and `crm-opportunities` and documents authentication, tenant scope, schemas, and `401`, `403`, `404`, `409`, and `422` responses.

## Audit and readiness

Create and update operations write `LEAD_CREATED`, `LEAD_UPDATED`, `OPPORTUNITY_CREATED`, and `OPPORTUNITY_UPDATED` events to `crm_audits` in the same database transaction. Platform Audit Logs exposes these as the `CRM` category.

Backend Health reports nine CRM operations plus tenant isolation, Employee ownership, Client/Lead/owner relationships, RBAC, pipeline UI, stage updates, conversion, and audit readiness.

## Verification

```text
Company Admin / authorized Employee
  -> Create Lead
  -> Qualify Lead
  -> Create Opportunity linked to Client and Lead
  -> Assign same-company Employee owner
  -> Retrieve and update both records
  -> Verify OPEN/CLOSED status follows stage
```

Cross-tenant Client, Lead, or Employee identifiers must be rejected. Temporary verification data must be removed before the checkpoint is closed.

## Day-47 pipeline

Day-47 exposes the existing Day-46 foundation through one reusable tenant workspace in both the Company Admin and authorized Company Employee frontends.

```text
Lead: NEW -> CONTACTED -> QUALIFIED -> CONVERTED / LOST
Opportunity: NEW -> QUALIFIED -> PROPOSAL -> NEGOTIATION -> WON / LOST
```

- `/crm` provides Pipeline, Leads, and Opportunities views.
- Create and edit flows use the existing full management workspace pattern, Poppins typography, theme variables, custom Loopless selectors, field-level validation, loading, empty, error, and success states.
- Stage movement always calls the authenticated backend `PATCH` operation. Opportunity `OPEN`/`CLOSED` status remains backend-derived.
- A qualified Lead can be converted only after it is associated with an existing same-tenant Client. The Opportunity reuses that Client and retains the originating Lead relationship; no duplicate Client is created.
- Search, owner, source, Lead status, Opportunity stage, Opportunity status, and backend pagination remain tenant-scoped.
- UI actions come from `/users/me` CRM permissions, while backend `CRM.VIEW`, `CRM.CREATE`, and `CRM.EDIT` enforcement remains authoritative.
- Direct Lead and Opportunity routes fetch through tenant-scoped APIs, so another company's identifier resolves as not found.
- Mobile uses full-width horizontally scrollable pipeline stages rather than compressed columns.

Day-47 intentionally excludes Client notes, feedback, activity timelines, forecasting, and CRM analytics.
