# Development Rules

## Frontend naming

- Components: `PascalCase`
- Variables and functions: `camelCase`
- Routes: `kebab-case`

## Backend naming

- Models and schemas: `PascalCase`
- Functions: `snake_case`
- Files: `snake_case`

## Foundation boundaries

- Do not implement authentication before the Authentication phase.
- Do not add ERP module business logic during foundation work.
- Keep tenant, RBAC, configuration, and database access centralized.
- Every change must pass formatting, linting, type checking, tests, and builds.
- Keep Swagger, backend health, and PlatformOwner backend inventory synchronized with backend changes.
- Commit environment templates only; never commit secrets

## Mandatory UI governance

- [`UIStandards.md`](UIStandards.md) is the mandatory source of truth for every new or modified screen in all five frontend applications.
- New or modified UI must reuse the existing Loopless page pattern, Poppins typography, theme tokens, dialogs, loaders, tables, and form controls.
- Raw native browser dropdowns (`<select>`) are strictly prohibited in new or modified UI. Existing native dropdowns on a touched screen must be migrated to the approved reusable custom listbox.
- The sidebar, topbar, breadcrumb, dashboard hero, and global shell must not change during feature work unless the user explicitly requests a shell change.
- Create/edit flows, short modals, directory actions, form validation, theme behavior, and responsive states must use the canonical references listed in `UIStandards.md`.
- UI work must preserve existing endpoints, payloads, business behavior, RBAC, tenant isolation, and persistence unless functionality changes are explicitly in scope.
- Visual/browser verification may be reported as passed only after it has actually been performed.
- Never push to Git without the user's explicit approval.
