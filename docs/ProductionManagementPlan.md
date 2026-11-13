# Production Management Plan

The single source of truth for turning the Adverse UI into a fully functional video-production agency application. It records the requirements, the owner's business decisions, the target design, and build progress. Update the **Progress** section as phases finish.

- Source requirements: *"Video Production & Client Management Web Application"* PDF (supplied by the owner, summarized in section 9).
- Where the owner's decisions below differ from the PDF, **the owner's decisions win**.
- Last updated: 2026-11-13

---

## 1. Ground rules

| Rule | Detail |
|---|---|
| **Existing UI is frozen** | Do not change existing screens, colors, fonts (Poppins), purple theme, sidebar, topbar, dashboard hero, layouts or templates. |
| **New UI reuses existing pieces** | New pages are built only from the existing components and theme tokens, per [`UIStandards.md`](UIStandards.md): management tables, in-page create/edit workspace, `LooplessSelect` (no native `<select>`), `ManagementModal`, `ConfirmationDialog`, `CrudActionButtons`, loaders, toasts. |
| **Allowed visible changes** | New sidebar entries for new modules. Real data in place of the hard-coded sample numbers on the existing Manager and Employee dashboard cards (same cards, same layout). |
| **Security is enforced on the server** | Data a role must not see is never sent to that role by the API. Hiding it in the UI alone is not enough. |
| **Price history is never overwritten** | Every task stores its own price snapshot. Changing a rate later never changes old tasks. |
| **Plan first** | Agree on the design with the owner before large builds. Never push to git without explicit approval. |

---

## 2. Roles

| Role | App (port) | Summary |
|---|---|---|
| **Admin** | `frontend/Admin` (3000) | Full control. The only role that creates or assigns tasks, sets prices, approves work, and sees money. |
| **Manager** | `frontend/Manager` (3001) | Commission-based worker. Does the tasks assigned to them, and can be set as **monitor** on other tasks (status changes only). Nobody reports to a Manager. Existing Team/Clients/CRM pages stay; access to them is controlled through the Admin's **Roles** screen. |
| **Employee** | `frontend/Employee` (3002) | Salaried worker. Does the tasks assigned to them. |
| **Client** | `frontend/Client` (3003) | Sees summary counts, budget and billing for their own account only. **No task or ticket list.** |

---

## 3. Owner's business decisions

### 3.1 Money

| Who | Model | Where it's configured | Per-task change |
|---|---|---|---|
| **Client** (income) | Rate **per item** (video, carousel, thumbnail, …), different for each client. | Existing: Admin → Settings → Services & Pricing → Client pricing | Default fills in automatically; the Admin can change it manually while creating or assigning (e.g. long videos) and gives a reason. |
| **Manager** (cost) | **Commission per item**, a fixed rate for each manager (e.g. ₹300/video). | Existing: Manager pricing on the same settings screen | Default fills in automatically; the Admin can change it manually. |
| **Employee** (cost) | **Fixed monthly salary**. | New: salary on the employee profile, with history | Not applicable |

Example client rates from the owner:

| Client | Per video | Per carousel | Per thumbnail |
|---|---:|---:|---:|
| Client A | ₹200 | ₹300 | ₹500 |
| Client B | ₹400 | ₹200 | ₹600 |
| Client C | ₹300 | ₹500 | ₹900 |
| Client D | ₹900 | ₹400 | ₹300 |

Worked example: a normal Client B video is ₹400 and Manager X's commission is ₹300, so the margin is **₹100**. For a long Client B video the Admin sets ₹900 and commission ₹500 on that task only, so the margin is **₹400**. Client B's default rate stays ₹400.

**Not wanted:** automatic pricing by video length. The Admin changes prices manually.
**Postponed:** monthly client packages (e.g. ₹30,000 for 20 reels). Per-item billing comes first.

### 3.2 Tasks ("tickets")

- "Tickets" and "tasks" are **the same thing**: one module, labeled **Tasks** in the sidebar (renaming it to "Tickets" is a label change only).
- **Only the Admin** creates and assigns tasks, to either a Manager or an Employee.
- The Admin can optionally set a **Manager as monitor** on a task. A monitor can **only change the task's status**, nothing else, and earns **no** commission on it.
- Status flow: `Pending → Assigned → In Progress → Submitted → Review → Approved → Completed`, with a "changes requested" path from Review back to In Progress.
- **Approved** and **Completed** are **Admin-only**, because approval makes the task billable and counts against the client's budget. Assignees and monitors can move tasks up to Submitted or Review, and monitors can send work back to In Progress.

### 3.3 Client budget

| Item | Rule |
|---|---|
| Type | **One-time amount** (e.g. ₹12,000). It does not reset monthly. The Admin adds **top-ups**, and every top-up is kept in history. |
| Used | Total of the **final client price** of the client's **approved/completed** tasks. |
| Committed (Admin only) | Total of tasks assigned but not yet approved. |
| Remaining | Budget minus used. |
| When exceeded | **Warn, but allow.** When assigning, the Admin sees e.g. *"This task will exceed Client A's budget by ₹1,000"* and can continue. The overage is tracked. |
| Client sees | Budget, used, remaining (and any overage), plus counts per service, e.g. "Videos edited: 8 · Thumbnails: 5". |

Example: a budget of ₹12,000 at ₹1,000 per video is exceeded after 12 videos.

### 3.4 Files

Task files (reference files from the Admin, final outputs from the assignee) are stored on the **owner's own server** under `backend/private-storage/task-files/` (git-ignored). This is deliberately not `backend/storage/`, which is served publicly for logos. Files are only reachable through the permission-checked download endpoints, and the maximum size is 2 GB per file. There is no Google Drive or S3 integration.

---

## 4. Who sees what (server-enforced)

| Data / action | Admin | Manager | Employee | Client |
|---|:-:|:-:|:-:|:-:|
| Create or assign tasks, set prices | ✅ | ❌ | ❌ | ❌ |
| Change task status | ✅ any | own tasks + tasks they monitor, up to Review | own tasks, up to Review | ❌ |
| Approve or complete tasks | ✅ | ❌ | ❌ | ❌ |
| Task list | all | own + monitored | own | ❌ (counts only) |
| Client prices, revenue, margin | ✅ | ❌ | ❌ | own charges only |
| Manager commission | ✅ all | own only | ❌ | ❌ |
| Employee salary | ✅ all | ❌ | own only | ❌ |
| Payments received / paid out | ✅ | own commission payouts | own salary payments | own payments |
| Client budget | ✅ (with committed) | ❌ | ❌ | own (budget, used, remaining) |
| Team member names on work | ✅ | ✅ (own tasks) | ✅ (own tasks) | ❌ |

---

## 5. Current state of the codebase (2026-11-13)

| Area | Status | Where |
|---|---|---|
| Stack | Next.js + TypeScript (4 apps), FastAPI + psycopg (no ORM at runtime), PostgreSQL, Redis, Prisma for schema and migrations, Docker Compose | `README.md` |
| Services catalog (not hard-coded) | ✅ Done; 6 defaults seeded per company | `backend/app/repositories/service_pricing_repository.py` |
| Client and Manager pricing, effective-dated | ✅ Done | `ServicePricing` model (`scope`: `CLIENT`, `MANAGER`); Admin UI `frontend/Admin/components/settings/services-pricing-settings.tsx` |
| Pricing models | Enum: `PER_VIDEO`, `PER_PIECE`, `MONTHLY_FIXED`, `MONTHLY_PACKAGE`, `COMMISSION_PER_DELIVERABLE` | `backend/prisma/schema.prisma` |
| Clients (CRUD, contacts, notes, feedback, activity, portal login link) | ✅ Done | `clients` API; `client-management-page.tsx` |
| Employees directory and profiles | ✅ Done | `employees` API; `employee-directory-page.tsx` |
| Roles and permissions (4 company roles) | ✅ Done | `RoleCode` in `backend/app/core/constants.py`; seed in `backend/prisma/seed.ts` |
| Admin dashboard | Real data (counts) | `frontend/Admin/components/dashboard/dashboard-page.tsx` |
| Client dashboard | Real data (profile + pricing) | `frontend/Client/components/dashboard/dashboard-page.tsx` |
| Manager and Employee dashboards | ⚠️ Hard-coded sample numbers | `frontend/{Manager,Employee}/components/dashboard/dashboard-page.tsx` |
| Tasks, files, comments, payments, salaries, budgets, reports | ❌ Not built | — |
| Version control | ❌ Project is not a git repository yet | — |

New sidebar items are added in each app's `lib/navigation.ts`, and section routing lives in `app/(dashboard)/[section]/page.tsx`.

---

## 6. Target data model (new tables)

All tables are tenant-scoped with `company_id`, UUID ids and `created_at`/`updated_at`, following existing conventions. Money uses `Decimal(12,2)` plus a `currency` column (default `INR`).

| Table | Key fields | Purpose |
|---|---|---|
| `tasks` | `code` (e.g. TSK-0001, per company), `client_id`, `service_id`, `title`, `description`, `priority`, `status`, `assignee_user_id`, `assignee_type` (MANAGER/EMPLOYEE), `monitor_user_id` (Manager, optional), `due_date`, `client_price_default`, `client_price_final`, `client_price_reason`, `commission_default`, `commission_final`, `commission_reason`, `pricing_model`, `currency`, `created_by_id`, `assigned_at`, `submitted_at`, `approved_at`, `completed_at` | The unit of work, with its price snapshot. |
| `task_status_history` | `task_id`, `from_status`, `to_status`, `actor_id`, `note` | Audit trail of status changes. |
| `task_price_changes` | `task_id`, `field`, `old_amount`, `new_amount`, `reason`, `actor_id` | Audit trail of manual price changes. |
| `task_comments` | `task_id`, `author_id`, `content` | Discussion on a task (internal; never shown to clients). |
| `task_files` | `task_id`, `kind` (REFERENCE/DELIVERABLE), `file_name`, `storage_path`, `mime_type`, `size_bytes`, `uploaded_by_id` | Files stored in `backend/private-storage/task-files/` (not publicly served). |
| `client_budget_entries` | `client_id`, `type` (INITIAL/TOP_UP/ADJUSTMENT), `amount`, `note`, `created_by_id` | Budget = the sum of the entries; history is kept. |
| `client_payments` | `client_id`, `amount`, `received_on`, `method`, `reference`, `note` | Money received from clients. |
| `employee_salaries` | `employee_id`, `monthly_amount`, `effective_from`, `effective_to` | Salary with history. |
| `salary_payments` | `employee_id`, `period_month`, `amount`, `paid_on`, `method`, `reference` | Salary paid out. |
| `manager_payouts` | `manager_user_id`, `amount`, `paid_on`, `method`, `reference`, `note` | Commission paid out. |

**Derived figures** (calculated, not stored):

- Task margin = `client_price_final` − `commission_final` (a task done by a salaried Employee has no per-task cost).
- Revenue = sum of `client_price_final` for approved/completed tasks.
- Cost = manager commissions on approved/completed tasks + employee salaries for the period.
- Gross margin = revenue − cost.
- Client pending = billed − payments received.
- Manager pending = commission earned − payouts.
- Employee pending = salary due − salary paid.

---

## 7. Build phases

| Phase | Scope | Outcome |
|---|---|---|
| **0. Backup** | `git init` and a baseline commit (secrets excluded by `.gitignore`). Playwright "before" screenshots of every existing screen in all 4 apps, at desktop and mobile widths. | A safe restore point and proof that the UI hasn't changed. |
| **1. Database** | Prisma models and a migration for section 6. | |
| **2. Backend** | Task CRUD and status workflow with role rules; price lookup, snapshot and manual change with audit; file upload/download; budget calculation and the exceed warning; payments, salaries, payouts; earnings; reports (by client, person and service; date filters: today, this week, this month, previous month, custom); per-role dashboard endpoints. Tests for money calculations and privacy rules. | |
| **3. Admin app** | New **Tasks**, **Payments** and **Reports** pages. Work, Billing and **Budget** tabs on the client page; Work and salary/commission tabs on the employee and manager pages; budget warning when assigning; real revenue, cost, margin, pending and overdue figures on the dashboard. | **Owner reviews before continuing.** |
| **4. Manager app** | My Tasks, Monitoring (status only), **My Earnings** (commission per task: earned, paid, pending). | |
| **5. Employee app** | My Tasks (download references, upload output, comment, submit), My Salary, real dashboard numbers. | |
| **6. Client app** | Summary dashboard: counts per service, budget, used, remaining, overage, payments. No task list. | |
| **7. Final check** | Backend tests; frontend format, lint, type-check, build and `ui:standards` for all apps; compare against the Phase 0 screenshots. | |

---

## 8. Progress

| Phase | Status | Notes |
|---|---|---|
| 0. Backup | ✅ Done (2026-11-13) | Git baseline commit `e810dee`. 132 "before" screenshots in `qa/ui-baseline/` (git-ignored, local only), captured with `qa/capture-ui.mjs`: 44 screens across the 4 apps, each at desktop-light, desktop-dark and mobile-dark. The script sets the theme through localStorage `loopless-theme` and waits until no "Loading…" text remains. |
| 1. Database | ✅ Done (2026-11-13) | Models added to `backend/prisma/schema.prisma` (purely additive; no existing table changed). Migration `20261113150000_production_management` creates 10 tables and 7 enums, plus check constraints: no negative money, commission only for manager assignees, one open salary per person, salary periods on the 1st of the month. Dry-run in a rolled-back transaction first, then applied via `docker compose run --rm migrations`; backend health reports the new version. |
| 2. Backend | ✅ Done (2026-11-13) | 33 endpoints (see "Backend API" below). Rules in `app/services/production_rules.py`; services `task_service.py` and `finance_service.py`; repositories `task_repository.py` and `finance_repository.py`; per-role response shapes in `app/schemas/production.py`. Seed gives COMPANY_ADMIN the `TASKS` and `FINANCE` permissions. 27 new unit tests (200 total pass), plus a 62-check end-to-end run against the live stack covering every role, privacy, workflow, files and money maths. Test data was deleted afterwards. |
| 3. Admin app | ✅ Done (2026-11-13), awaiting owner review | Sidebar: **Tasks** (permission + plan feature `TASKS`), **Payments** (`FINANCE` permission only), **Reports** (`REPORTS` permission only; the Starter plan lacks those features). Tasks: Board (Kanban, drag to change status, billing moves confirmed) and List views, create/edit form with automatic rates and live budget message, detail page (status, prices/margin, assignment, files, comments, history). Payments: tabs for client payments, budgets, salaries, manager payouts, with full create/view/edit/delete (owner request, 2026-11-13): payments and payouts can be edited (the employee or manager cannot change; delete and re-record instead), salary rates can be corrected (amount and note) or deleted (the previous rate then runs until the next one), and Salaries/Payouts show a payment history table. Backend: `PATCH` client-payments, salary-payments, manager-payouts, salary-records and `DELETE` salary-records, all audited. Reports: period presets plus custom range, summary cards, client/team/service tables. Dashboard **redesigned at the owner's request (2026-11-13)**: compact header (greeting, date, period selector, Record payment / Create task) instead of the large hero; revenue (with change vs the previous period), team cost, gross margin and pending tiles; 6-month revenue vs team cost bar chart (hover tooltip, table view; colours validated for colour-blind readers and contrast in both themes); work by status; overdue and due-this-week list; team workload; client budget watch. Backed by `GET /company/finance/dashboard`. The old recent-activity feed and quick-actions panel were removed at the owner's choice. Code: `components/{tasks,payments,reports,production}`, `lib/production/*`, `lib/backend-proxy.ts`, `styles/production.css` (reuses organization/service-pricing/management styles; every rule is scoped to the new pages). Browser-tested in light, dark and mobile with no console errors; demo data deleted afterwards. |
| 4. Manager app | ✅ Done (2026-11-13) | Sidebar: My Tasks, My Earnings. Shared screens in `frontend/shared/workspace/` (board/list, task detail with allowed status moves only, deliverable upload, comments, history; commission earnings; `EmployeeSalaryPage` ready for Phase 5) behind thin wrappers in `Manager/components/workspace/`. Dashboard keeps its hero and cards with live numbers. Fixed: Manager's `lib/auth/server.ts` did not send `X-Company-ID`, so company/workspace calls returned 400; Employee and Client have the same bug (fix in Phases 5–6). Browser-tested light and dark; no price or margin fields reach the Manager. |
| 5. Employee app | ✅ Done (2026-11-13) | Sidebar: My Tasks, My Salary (shared `frontend/shared/workspace` screens; no monitor filter for employees). Dashboard keeps its hero with live numbers. `lib/auth/server.ts` now sends `X-Company-ID`. Browser-tested: drag-and-drop, deliverable upload, salary page; commission API refused (403); no price or margin fields reach the Employee. |
| Tasks page redesign | ✅ Done (2026-11-13) | Built as agreed below for the Admin **Tasks** page and the shared Manager/Employee **My Tasks** page. Shared pieces in `frontend/shared/production/task-board-ui.tsx` + `shared/styles/task-board.css` (compact header with live counts, quick filter chips, priority-striped cards with assignee initials, due chip, file/comment counts, slide-in task sheet, status progress bar). The sheet keeps `?task=<id>` (and `?mode=create` for the Admin form) in the URL, closes on Escape, the close button or a click outside, and is full-screen on phones; the board behind it refreshes after every change. Create/edit forms also open in the sheet. Backend: `files_count`/`comments_count` on Admin and worker task lists; list `page_size` cap raised from 100 to 500 so the board and counts cover more work (open work sorts first). Browser-tested Admin (light, dark, mobile) and Manager (light, mobile); `[QA]` tasks deleted afterwards. Restyled the same day at the owner's request ("colours clumsy"): flat header, underline tabs for quick filters, soft lanes with a status dot instead of bordered columns and pills, plain white cards (priority shown only for Urgent/High), and a single flat task panel with thin dividers instead of stacked cards. |
| 6. Client app | ⏳ Not started | |
| 7. Final check | ⏳ Not started | |

Approve/Complete stay Admin-only (confirmed by the owner's "go", 2026-11-13).

### Tasks page redesign (owner request, 2026-11-13) — agreed and built

Applies to the Admin **Tasks** page (`frontend/Admin/components/tasks/task-management-page.tsx`) and the shared **My Tasks** page (`frontend/shared/workspace/workspace-tasks-page.tsx`). Keep the colours, Poppins type, sidebar and topbar; only modernise this page.

| Area | Agreed design |
|---|---|
| Top | Drop the large hero. A compact header card like the new dashboard: title, live counts ("12 open · 2 overdue · 3 to review"), search, view toggle, **+ New task** (Admin only). |
| Quick filters | One-click chips with live counts: All, Overdue, Due this week, To review (Submitted + Review), Unassigned (Admin only). Status and client dropdowns stay for detail filtering. |
| Board cards | Priority colour stripe on the left edge (Urgent/High/Medium/Low), assignee avatar initials, due-date chip (red when overdue), client and service, price (Admin) or own commission (Manager), file and comment counts. Requires adding `files_count` and `comments_count` to the task list responses (`AdminTaskResponse`, `WorkerTaskResponse`). |
| Opening a task | A **side panel that slides in from the right** over the board (the board stays visible behind it), not a full-page view. Escape and the close button dismiss it; the URL keeps `?task=<id>` so links still work. |
| Task detail | Cleaner header with a **status progress bar** (Assigned → In Progress → Submitted → Review → Approved → Completed), then tidy sections: overview, money (Admin), assignment (Admin), status change, files, comments, history. On phones the panel is full-screen. |

### Backend API (Phase 2)

Every request needs `Authorization: Bearer <token>` and `X-Company-ID` (the tenant middleware requires it; the frontend's `authenticatedBackend` already sends it). The company used for data access always comes from the login token, never from the header.

| Who | Prefix | Endpoints |
|---|---|---|
| Admin | `/company/tasks` | `GET ""` (list, filters: status, client, service, assignee, overdue, search) · `POST ""` (create, optional assign; returns `{task, budget}`) · `GET /assignee-options` · `GET /pricing-preview?client_id&service_id&assignee_user_id&client_price` · `GET/PATCH /{id}` · `POST /{id}/assign` · `PUT /{id}/monitor` · `POST /{id}/prices` · `POST /{id}/status` · `POST /{id}/comments` · `POST /{id}/files` (multipart `file`, `kind`) · `GET/DELETE /{id}/files/{file_id}` |
| Admin | `/company/finance` | `GET /summary?period` · `GET /reports/clients\|team\|services?period` · `GET /budgets/{client_id}` · `POST /budgets/{client_id}/entries` · `GET/POST /client-payments` · `GET /people/{user_id}` · `PUT /people/{user_id}/salary` · `GET/POST /salary-payments` · `GET/POST /manager-payouts` · `DELETE /{client\|salary\|payout}/{id}` |
| Manager / Employee | `/workspace` | `GET /dashboard` · `GET /tasks?role=ASSIGNEE\|MONITOR` · `GET /tasks/{id}` · `POST /tasks/{id}/status` · `POST /tasks/{id}/comments` · `POST /tasks/{id}/files` · `GET/DELETE /tasks/{id}/files/{file_id}` · `GET /earnings/commission` (manager) · `GET /earnings/salary` (employee) |
| Client | `/client-portal` | `GET /summary` (counts per service, budget, charges, payments; no task list) |

`period` is one of `all`, `today`, `this_week`, `this_month`, `previous_month` or `custom` (with `start` and `end`), resolved in the company timezone. Each task response includes `allowed_statuses`, so the UI only offers moves the backend will accept.

Working notes for later phases:

- Task files are stored in `backend/private-storage/task-files/` (git-ignored), **not** `backend/storage/`: `main.py` serves `/storage` publicly for logos.
- Pre-existing issue, not fixed: any request under `/storage/...` returns a 500 while the `backend/storage` folder doesn't exist (no logo uploaded yet). This is in the existing branding setup.
- The test company's currency is set to **USD** (Settings → Regional). Prices and reports display in that currency until it is changed to INR.
- The seed still gives `COMPANY_MANAGER` a `TASKS: ASSIGN` permission. It has no effect, because assignment endpoints require the Admin role.
- Backend timestamps are UTC but sent without a `Z`. The new pages parse them as UTC (`lib/production/client.ts`). Pre-existing, not fixed: the dashboard's "Recent activity" shows times 5½ hours off for India because it parses them as local time.
- The Docker VM has about 7.7 GB of RAM. Four Next.js dev servers use roughly 1.3–1.5 GB each, and the Admin container was once killed for running out of memory (`OOMKilled`) after many page compiles. Fix with `docker start loopless-admin-1`, or give Docker more memory.
- The ECC plugin's GateGuard hook asks for facts before the first edit of each file and before destructive commands. Answer it and retry.

- On the host, port 5432 is a separate Homebrew Postgres. Reach the Docker database with `docker exec loopless-postgres-1 psql -U loopless -d loopless_dev`.
- To re-capture screenshots for the Phase 7 comparison: install `playwright` in any scratch folder, then run `PLAYWRIGHT_FROM=<that folder> CHROMIUM_PATH=<chromium binary> node qa/capture-ui.mjs qa/ui-after`.
- Development test accounts (password `1234`): `adverseadmin@`, `adversemanager@`, `adverseemployee@`, `adverseclient@` (all `gmail.com`).

---

## 9. Requirements from the PDF (summary)

1. **Services** are configurable, not hard-coded: add, edit, disable, delete, plus a pricing model per service. Initial services: Reel, Thumbnail, Carousel, Long Video, SPLS Reel, Social Media Marketing.
2. **Separate dashboards and permissions per role.** (The PDF lists Admin, Client and Team Member; this project has Admin, Manager, Employee and Client.)
3. **Admin manages** clients, team, services, pricing, projects, tasks, assignments, payments, earnings, reports and settings.
4. **Client management:** add, edit, activate/deactivate, history, work, payments, pending, completed, service-wise billing. Each client has its own pricing.
5. **Team management:** add, edit, activate/deactivate, assign, view completed/pending work, earnings, payment history. Each member has their own rates.
6. **Pricing:** no global price. Client price minus team cost equals business gross margin.
7. **Pricing models:** monthly package, per-service/per-video, team monthly fixed, team commission.
8. **Workflow:** create service → client → client pricing → team member → team pricing → task (client + service) → client price determined → assign → team payment determined → complete → admin approves → billable → billing, earnings and margin updated.
9. **Task fields:** ID, client, service, assignee, title, description, reference files, due date, priority, status, client price, team payment, revenue, margin, created/completed dates, approval status.
10. **Client dashboard:** totals, active/completed/pending work, billing, payments. Must never show team pay, margin or internal costs.
11. **Team dashboard:** own tasks and earnings only. Must never show others' pay, client pricing, profit or other clients.
12. **Admin finance:** revenue, team cost, gross margin, pending client payments, pending team payments.
13. **Reports** by client, team member, service and date range.
14. **Pricing history:** a price change must never alter past tasks; store a snapshot on each task.
15. **Scalability:** normalized design that can later add packages, discounts, taxes, bonuses, currencies, invoices, payment gateways, subscriptions, bundles and recurring contracts.
16. **Dashboard questions the Admin must be able to answer:** pending videos, client with most work, billing per client this month, pay per team member, revenue, gross margin, top services, overdue tasks, money pending from clients.
