# CRM Pipeline

## Day-47 scope

The Loopless CRM workspace is a reusable Company Admin and Company Employee frontend over the tenant-scoped Lead and Opportunity APIs introduced on Day-46.

### Routes

| Frontend route            | Purpose                                              |
| ------------------------- | ---------------------------------------------------- |
| `/crm`                    | Pipeline, Lead directory, and Opportunity directory. |
| `/crm/leads/{id}`         | Protected tenant-scoped Lead detail.                 |
| `/crm/opportunities/{id}` | Protected tenant-scoped Opportunity detail.          |

### API inventory

| Method      | Backend path          | Purpose                                          |
| ----------- | --------------------- | ------------------------------------------------ |
| `GET`       | `/crm/options`        | Active same-company Employee owners and Clients. |
| `GET/POST`  | `/leads`              | Search/list or create Leads.                     |
| `GET/PATCH` | `/leads/{id}`         | Read or update one tenant Lead.                  |
| `GET/POST`  | `/opportunities`      | Search/list or create Opportunities.             |
| `GET/PATCH` | `/opportunities/{id}` | Read or update one tenant Opportunity.           |

### Security boundary

- Company identity comes only from the validated JWT.
- CRM options, records, filters, and relationships are always scoped to that Company.
- UI actions use `/users/me` permissions; backend permissions remain authoritative.
- `CRM.VIEW` controls lists, details, and options; `CRM.CREATE` controls new Leads and Opportunities; `CRM.EDIT` controls edits and stage movement.
- Direct URLs do not bypass tenant checks.

### Conversion

A qualified Lead can open the Opportunity conversion editor. When the Lead is not linked to a Client yet, the editor requires the user to select an existing Client before submission. The Opportunity preserves the Lead, Client, and owner relationships, then the Lead moves to `CONVERTED`. Loopless never creates a duplicate Client automatically.

### Workspace interactions

- Pipeline supports Board and List views without creating separate CRM data sources.
- Authorized users can drag Lead and Opportunity cards between compatible columns. Every drop is persisted through the existing PATCH API; failed requests restore the previous card position.
- A qualified Lead dragged to Proposal opens the existing conversion editor. Its Client is prefilled when already associated; otherwise the user selects an existing Client in the editor before conversion.
- Custom status selectors remain available for keyboard, touch, and non-drag workflows. Native browser dropdowns are not used.
- Lead, Opportunity, and layout views preserve the existing Loopless Poppins typography, theme tokens, responsive behavior, and permission rules.

### Explicit exclusions

Client notes, Client feedback, activity timelines, forecasting, and advanced CRM analytics are not part of Day-47.
