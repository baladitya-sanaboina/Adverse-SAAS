# Client Management

## Day-44 boundary

Day-44 establishes the tenant-owned Client business record, Client Contact relationship, and secure backend APIs. Day-45 adds the Client directory, detail workspace, create/edit forms, and contact management UI. Client Portal, projects, invoices, tickets, payments, Leads, Opportunities, and CRM pipelines remain outside this scope.

A Client is a business record owned by an existing Loopless Company. It is not a second platform tenant and it is separate from a `COMPANY_CLIENT` login User.

```text
Company 1 --- * Client 1 --- * ClientContact
```

## Data model

`clients` stores the company ID, tenant-unique code, business identity and contact details, lifecycle status, and timestamps. `client_contacts` stores one or more people under that Client.

- Client code is unique only inside its Company: `UNIQUE(company_id, code)`.
- A contact email is unique only inside its Client: `UNIQUE(client_id, email)`.
- Client and Contact status use the existing `ACTIVE` / `INACTIVE` convention.
- Creating or updating a primary contact locks the parent Client and atomically clears the previous primary contact.
- Deleting a Company cascades to its Client records; deleting a Client cascades to its contacts.

Migration: `20260816120000_client_domain_foundation`.

## Tenant and permission boundary

The API never accepts `companyId` or `tenantId` from a request body or query string. The service derives the Company from the validated JWT and every repository query includes that Company ID.

The existing `CLIENTS` module is reused:

| Operation | Permission |
| --- | --- |
| Create client | `CLIENTS.CREATE` |
| List/get client and contacts | `CLIENTS.VIEW` |
| Update client | `CLIENTS.EDIT` |
| Create/update contacts | `CLIENTS.MANAGE` |

Cross-tenant identifiers return `404`, missing authentication returns `401`, and insufficient permission returns `403`.

## API inventory

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/clients` | Create a current-tenant Client. |
| `GET` | `/clients` | Search, filter, and paginate current-tenant Clients. |
| `GET` | `/clients/{clientId}` | Return one Client with its contacts. |
| `PATCH` | `/clients/{clientId}` | Update allowed Client fields or status. |
| `POST` | `/clients/{clientId}/contacts` | Create a contact under an owned Client. |
| `GET` | `/clients/{clientId}/contacts` | List contacts for an owned Client. |
| `PATCH` | `/clients/{clientId}/contacts/{contactId}` | Update a contact under an owned Client. |

Swagger documents request/response models and `401`, `403`, `404`, `409`, and `422` responses. Backend Health reports the seven Client Management operations, tenant isolation, the one-to-many contact relationship, atomic primary-contact behavior, and request-time permission checks.

## Day-45 frontend

The Company Admin application and the authorized Company Employee application reuse one Client management implementation. Access is still decided by the backend and the current `/users/me` permissions; the frontend only uses those permissions to hide controls the user cannot operate.

- `/clients` provides tenant-scoped search, status filtering, pagination, loading, empty, retry, desktop table, and mobile card states.
- `/clients/{clientId}` provides a direct, refresh-safe Client detail route with business information and Contacts.
- Create and Edit replace the directory inside the existing Loopless content workspace; they do not use a full-form modal.
- `CLIENTS.CREATE` shows Create Client, `CLIENTS.EDIT` shows edit/status actions, and `CLIENTS.MANAGE` shows Add/Edit Contact and primary-contact controls.
- Contacts support add, edit, Active/Inactive status, and one primary contact. Saving a new primary contact uses the Day-44 atomic backend behavior.
- Both applications use the existing shell, breadcrumb, Poppins typography, `LooplessSelect`, `CrudActionButtons`, confirmation dialog, light/dark tokens, and shared management-surface styling.
- Native browser dropdowns, browser validation popups, decorative actions, and client-supplied tenant IDs are not used.

The Company Employee route appears only when both the `CLIENTS` module permission and the subscription's `CLIENT_MANAGEMENT` feature are available. Direct API calls continue to return `401` or `403` when authentication or permission checks fail.

## Migration and verification

```text
docker compose -f docker/docker-compose.yml run --rm migrations
docker compose -f docker/docker-compose.yml run --rm migrations npx prisma migrate status
```

Temporary Client and Contact records created for manual verification must be removed before completing the checkpoint.
