# Loopless UI Standards

This document is the mandatory UI and typography contract for every Loopless frontend application and every new or modified screen. A page is not complete when it works but does not follow this contract.

## Scope and priority

- These rules apply to `PlatformOwner`, `Developer`, `CompanyAdmin`, `CompanyEmployee`, and `CompanyClient`.
- The approved Loopless UI already present in the repository is the visual source of truth. Do not create a new visual interpretation for each feature.
- A direct user instruction for a specific screen takes priority. Preserve the supplied or approved UI and change only the requested area.
- UI refactoring must not change API endpoints, payloads, validation, RBAC, tenant isolation, persistence, or other business behavior.
- Before adding a component or stylesheet, search for an approved reusable equivalent. Page-specific duplication is prohibited when a shared primitive can satisfy the requirement.

## Canonical implementation references

Use these files as the implementation contract for management screens:

| Concern | Approved reference |
| --- | --- |
| Management toolbar, editor, form, modal and responsive rules | `frontend/shared/styles/management-surfaces.css` |
| Short transactional modal | `frontend/CompanyAdmin/components/foundation/management-modal.tsx` |
| Directory row actions | `frontend/CompanyAdmin/components/foundation/crud-action-buttons.tsx` |
| Accessible custom dropdown | `frontend/CompanyAdmin/components/foundation/loopless-select.tsx` |
| Department and Branch list/create/edit flow | `frontend/CompanyAdmin/components/organization/organization-page.tsx` |
| Role list/create/edit and permission flow | `frontend/CompanyAdmin/components/roles/role-management-page.tsx` |
| Client list/view/create/edit/contact flow | `frontend/shared/clients/client-management-page.tsx` |
| Invite User modal | `frontend/CompanyAdmin/components/invitations/invitations-page.tsx` |
| User Assignment modal | `frontend/CompanyAdmin/components/users/company-users-page.tsx` |

Shared feature implementations under `frontend/shared` are canonical. Role applications must consume them through thin local wrappers so Docker and application-specific imports remain explicit; copying their complete markup or styling back into a role app is prohibited.

## One visual system

- Every role application must use the existing Loopless application shell, breadcrumb height, sidebar, topbar, Poppins typography, spacing scale, border radius, icons, light/dark tokens, and flat purple palette.
- Existing shared page patterns are the source of truth. Directory/list pages follow the Employee directory pattern; create/edit forms follow the existing registration/form pattern; confirmations use `ConfirmationDialog`; notifications use the shared toast/status treatment.
- Feature pages must reuse established components and CSS tokens before introducing any feature-specific styling.
- Do not introduce gradients, browser-default typography, unrelated palettes, duplicate page headings, or a second design system.
- Sidebar, topbar, breadcrumb, dashboard hero, and layout dimensions must not be changed while implementing a feature page unless the documentation explicitly changes the global shell.

## Typography — strict

- Poppins is the only product UI font. Load it through the application's existing `next/font` setup and expose it as `--font-poppins`.
- Every button, input, textarea, listbox, modal, table, toolbar, toast, label, and helper message must inherit `var(--font-poppins), Arial, Helvetica, sans-serif`.
- Do not allow a browser control, portal, or feature stylesheet to fall back to a different visible font.
- Reuse the typography already defined in `frontend/shared/styles/management-surfaces.css`; do not invent page-local font sizes or weights for equivalent elements.

| Element | Required baseline |
| --- | --- |
| Management title | `1.02rem`, weight `700` |
| Toolbar title/count | `0.94rem`, weight `700` |
| Field label | `0.70rem`, weight `700` |
| Input/control value | `0.72rem`, weight `500` or `600` |
| Primary/secondary action | `0.68rem`, weight `700` |
| Eyebrow | `0.62rem`, weight `800`, uppercase |
| Validation/helper copy | `0.61rem` to `0.68rem`, weight `500` or `600` |

These values are the management-screen baseline, not permission to shrink unrelated page copy. Equivalent controls across pages must look identical. Any deliberate global typography change must update the shared stylesheet and all affected applications together.

## CRUD workspace pattern — strict

- Directory modules must open Create, View, and Edit inside the same main content workspace, replacing the list while the editor is active and providing a clear Back/Cancel path. Do not open a full CRUD form in an overlay modal.
- Overlay dialogs are reserved for confirmations, destructive actions, and short bounded tasks. They must never become a parallel page layout.
- Row actions must reuse the shared outlined icon-button component and consistent order: View, Edit, Enable/Disable, Delete. Actions are permission-driven, include accessible labels/tooltips, and use semantic green/red states only where relevant.
- Create and update forms must reuse the same Poppins hierarchy, input height, validation placement, loading state, footer actions, theme tokens, and responsive stacking used by the established Employee and Role editors.
- When a list module is touched, its create/edit interaction, row actions, loading/empty/error states, typography, and mobile cards must be reviewed together; visually updating only one state is incomplete.

### Allowed modal usage

- Use `ManagementModal` only for a confirmation or a short, bounded task that does not replace a full directory workspace.
- Invite User and User Assignment are approved short modal flows.
- Department, Branch, Role, Employee, Client, Developer, Company, and Subscription create/edit forms must use the established in-content management workspace unless the user explicitly approves a different interaction.
- A modal must preserve the shared Poppins hierarchy, themed surface, bounded viewport height, internal scrolling, loading lock, Escape/close behavior, and mobile width.

## Actions and interaction — strict

- Use `CrudActionButtons` for directory rows. The order is View, Edit, Activate/Deactivate, Delete.
- Only render actions supported by the backend and allowed by the current user's permissions. Never show a decorative or non-functional action.
- Activate/deactivate uses the outlined power action with the semantic state treatment. Delete remains a separate destructive action.
- Destructive actions, activation changes, deactivation changes, resets, and other material saves require the shared confirmation dialog where the current workflow requires confirmation.
- Save buttons expose an in-button loader, remain disabled while submitting, prevent duplicate requests, and return the user to the correct list/detail state after success.
- Use the shared toast/status treatment for success and failure. Do not create a page-specific toast design.
- Icons must come from the existing Lucide icon system. Do not mix emoji, browser icons, or unrelated icon libraries into product controls.

## Forms and validation — strict

- Validate on blur and while the field changes after it has been touched; do not wait until submit to show every error.
- Render field-specific errors directly below the relevant control and apply the shared red invalid border.
- Map backend field conflicts, such as duplicate email or code, back to the correct field whenever possible.
- Keep required labels, placeholders, input heights, spacing, focus rings, password-eye controls, disabled states, and loading states consistent with the canonical management form.
- Do not replace inline validation with a generic banner when the error belongs to one field.

## Dropdown rule — strict

- Native browser dropdown UI is prohibited in new or modified product UI.
- CI runs `npm run ui:standards` and fails if a native `<select>` or `<option>` is introduced in any frontend app.
- Do not add raw HTML `<select>`, visible native `<datalist>`, or browser-styled dropdown controls.
- Use the approved reusable Loopless custom select/listbox component with the existing Poppins font, theme tokens, keyboard navigation, focus state, selected state, disabled state, validation state, outside-click close, and responsive positioning.
- A custom dropdown must support keyboard and screen-reader behavior: label association, `aria-expanded`, `aria-controls`, `role="listbox"`, `role="option"`, Arrow keys, Enter/Space selection, and Escape close.
- Light and dark modes must use semantic theme variables; hard-coded browser-default colors are not allowed.
- Existing native dropdowns are migration debt. Whenever a screen containing one is modified, all native dropdowns on that screen must be migrated before the screen is considered complete.
- No exception is allowed merely because a native `<select>` is faster to implement.

## Browser-native UI

- Do not rely on browser validation bubbles. Validation must be rendered inline using Loopless form styles and update when the field changes.
- Do not use `window.alert`, `window.confirm`, or `window.prompt`; use the shared Loopless dialog/toast primitives.
- Native file inputs may remain visually hidden only when controlled by the approved themed upload component.

## Theme and visual language — strict

- Use the existing semantic variables such as `--surface`, `--surface-muted`, `--foreground`, `--muted`, and `--border`; both light and dark modes are mandatory.
- Use the stable Loopless purple palette and existing accent behavior. Do not introduce gradients, neon treatments, random feature colors, or hard-coded white/black surfaces that break a theme.
- Semantic success, warning, information, and danger colors are reserved for their actual state meaning.
- Cards use the approved flat surface, border, radius, and restrained shadow. A feature must not introduce a parallel card language.
- Branding color customization marked as Coming Soon must not alter the stable product palette until the unified design-system implementation is explicitly resumed.

## Navigation and tab ownership — strict

- Before adding any sidebar item, page tab, or route label, audit the existing navigation and routes for the same or overlapping business concept.
- Do not create two top-level navigation entries with ambiguous ownership. Related views must use one clearly named parent entry and internal tabs.
- A new tab is allowed only after confirming that an equivalent tab or route does not already exist. If overlap exists, extend or consolidate the existing area instead of duplicating it.
- Labels must describe distinct responsibilities. In Company Admin, `Employees` owns employee lifecycle and operational records; `Users & Invitations` owns account invitations and role/department/branch assignments.
- Internal tabs must preserve the shared shell, breadcrumb, permissions, active state, responsive behavior, and direct-route access.
- Navigation review is a mandatory completion gate for every new frontend module. An ambiguous or duplicate sidebar/tab entry means the module is incomplete.

## Responsive and accessibility gate

- Verify desktop, tablet, and mobile widths. No page may introduce horizontal viewport overflow, clipped actions, inaccessible modal content, or overlapping controls.
- At narrow widths, forms stack to one column and action groups remain usable. Directory data must use the approved mobile-card or controlled table behavior.
- Interactive controls need visible focus, keyboard operation, accessible names, and adequate pointer targets.
- A custom listbox must preserve its required ARIA roles and keyboard behavior; visual matching alone is insufficient.
- Browser-console/runtime errors make the UI incomplete even when the page renders.

## Mandatory implementation sequence

1. Inspect the existing shell, route, navigation, and nearest approved feature page.
2. Search for an existing shared component before writing page-specific markup or CSS.
3. Preserve backend behavior and permission/tenant boundaries.
4. Implement list, create, view, edit, loading, empty, error, confirmation, and responsive states as applicable.
5. Compare typography, spacing, actions, dropdowns, and theme behavior with the canonical references above.
6. Run the application-specific format, lint, type-check, build, and UI standards checks.
7. Perform real browser checks at desktop, tablet, and mobile widths when browser access is available; inspect the browser console.
8. Run `git diff --check`. Git push is a separate action and requires explicit user approval.

## Completion gate

A frontend change is incomplete if it introduces a native dropdown, changes the shared shell without permission, uses a non-Poppins visual treatment, bypasses light/dark tokens, duplicates an existing reusable component, exposes a non-functional action, or adds an ambiguous/duplicate navigation entry. Formatting, lint, type-check, build, UI-standards validation, responsive review, browser-console review, and `git diff --check` remain mandatory. Do not report visual/browser verification as passed unless it was actually performed.
