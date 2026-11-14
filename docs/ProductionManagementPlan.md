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
| 6. Client app | ✅ Done (2026-11-13) | The existing dashboard (hero, stat cards, panels, sidebar unchanged) now shows live data from `GET /client-portal/summary` (new proxy `app/api/client/summary`) plus profile and rates from `/clients/me/dashboard`. Stat cards: Work delivered (with per-service counts), In progress, Budget remaining (red note when over budget), Pending payment. Panels: **Budget** (budget, used, remaining or over-budget, usage meter, warning at 80% and over-budget message: warn but allow), Your rates, **Work delivered** (counts and billed amount per service, no task list), Quick actions, Billing and payments (billed, paid, pending, this month, payment history), Client profile. The old "Work visibility" panel that could list individual tasks was removed, per the owner's rule. `StatCard` gained an optional `tone="warning"` (default look unchanged); new styles in `Client/styles/client-portal.css`. Fixed: Client `lib/auth/server.ts` now sends `X-Company-ID`. Verified: the client API returns no task titles, codes, commission or margin, and `/company/tasks` and `/workspace/tasks` return 403 for the client; browser-tested light, dark and mobile in normal, over-budget and empty states; `[QA]` data and its audit rows deleted. |
| 7. Final check | ✅ Done (2026-11-13) | **Backend:** 200 unit tests pass; the 62-check end-to-end run passes 61. The one failure is the existing `/storage` issue: the public `storage/` folder does not exist in the container, so any `/storage/...` request returns 500 instead of 404. Path-traversal attempts at a real private task file return 400 with no content, so private files are not exposed. black, ruff and mypy findings are all in files this project did not touch (13, 4 and 4 files, existing before Phase 0). **Frontend:** type-check and lint pass for all four apps and `shared`; `ui:standards` passes; production `next build` succeeds for Admin, Manager, Employee and Client. Prettier: 24 existing files were already unformatted; the only new ones are `shared/styles/organization.css` and `service-pricing-settings.css`, kept as exact copies of the Admin originals. **UI freeze:** 132 screenshots in `qa/ui-after/` compared pixel-by-pixel with `qa/ui-baseline/`. Outside the dashboards, every screen differs only in the sidebar (new logo, new entries) or the login logo, apart from data changes (currency USD→INR set by the owner, Admin permission count 52→70 from the new TASKS/FINANCE permissions, client rates the owner configured) and one fix: the Manager client page no longer shows a JSON error in the notes panel. Dashboards changed as agreed. `qa/capture-ui.mjs` gained `ONLY_APPS` and a longer login timeout because four dev servers in a 7.7 GB Docker VM are slow; raise Docker memory to 12 GB or more. All test data deleted. |
| 8. Dark mode + privacy eye | ✅ Done (2026-11-14) | Dark tokens in all four apps: page `#0A0A0B`, surface `#121214`, muted surface `#17171A`, border `#232327`, text `#F5F5F7`, muted text `#8E8E93`, primary `#4DA3FF` (text-safe) / `#0876ED`. 385 hard-coded navy, slate and old purple-grey colours inside `.dark` rules (46 stylesheets) converted to neutral near-blacks of matching brightness; semantic (green/red/amber), light-blue text and strong blue tints kept. Light mode untouched. Privacy eye: `shared/production/privacy.tsx` (`MoneyPrivacy`, `PrivacyToggle`, `usePrivateMoney`, `maskMoney`), hidden on every visit. Applied to the Admin dashboard (tiles, notes, margin %, chart axis, table and tooltip, team workload, budget watch) and the Manager **My Earnings** and Employee **My Salary** pages. Browser-checked: no amount visible while hidden; all amounts appear after pressing the eye. |
| 9. Dashboards (Manager, Employee, Client) | ✅ Done (2026-11-14) | All three rebuilt in the Admin dashboard style: greeting header with actions, four KPI tiles, month chart, status bars, lists. **Manager:** commission this month (privacy eye), open, waiting review, monitoring; commission per month (6 months); work by status (links to My Tasks filtered by `?status=`); due soon; recently approved with commission. **Employee:** same with salary this month (eye) and deliveries per month. **Client:** delivered, in progress, budget left (red when over), pending payment; work per month; budget ring with used/left and 80%/over-budget notes; latest deliveries (title, service, date, price); payments; rates; profile. Backend: `/client-portal/summary` gained `recent_deliveries` and `monthly` (6 months) from a new `client_deliveries` query that returns no codes, people or costs; helpers `last_month_starts` and `monthly_totals` with unit tests (202 pass). Shared UI `shared/dashboard/role-dashboard-ui.tsx` + `shared/styles/role-dashboard.css` (tile/panel rules copied from Admin); the Client app (no `shared` mount) has copies of these plus `styles/production.css`. Old hero dashboards and `WorkspaceDashboardBody` removed. Browser-checked light, dark and phone. |
| 10. Notifications | ✅ Done (2026-11-14) | Table `notifications` (migration `20261114100000_notifications`). Backend: `notification_service` (store + live publish, never fails the caller), `realtime` (Redis pub/sub channel `realtime:user:<id>`, `GET /realtime/stream` Server-Sent Events with heartbeat), `/notifications` list (`limit`, `before`, `unread`), `/unread-count`, `/{id}/read`, `/read-all`. Events: task assigned / monitoring, status changed (workers → admins; admin → assignee and monitor), comment, file uploaded, client budget first reaching 80% or going over (admins and the client), budget top-up and payment received (client), salary paid (employee), payout paid (manager). Nobody is notified of their own action. Frontend: `shared/realtime/realtime.ts` (one EventSource per tab, reconnects), `shared/notifications/notification-center.tsx` (bell with unread badge and dropdown, toasts, Web Audio chime, desktop notifications when the tab is hidden, Notifications page with All/Unread, mark read, sound and desktop toggles kept per device), proxy routes `/api/notifications` and `/api/realtime/stream` in all four apps (proxy now passes the stream headers and closes the backend request when the browser leaves). Client app has copies. Tests: 210 pass (threshold rule, notify rules). Verified live: a task created by the Admin shows on the employee's bell and toast instantly; clicking opens the task and clears the badge. |
| 11. Client billing + invoices | ✅ Done (2026-11-14) | Tables `invoices` + `invoice_lines` (migration `20261114120000_invoices`, with non-negative and period-order checks). Invoices snapshot every delivered item (date, title, service, amount) and the payments received in the period; number per company (`INV-0001`); statuses Draft, Sent, Paid, Void. PDF via `reportlab` (new backend dependency, image rebuilt) with the Adverse logo and bundled Poppins font (SIL OFL, `app/assets/fonts/OFL.txt`) so ₹ renders; Indian digit grouping. Sending emails the PDF to the client's login email (Mailpit in dev) and notifies the client. **Automatic draft:** when approved work first uses up a client's budget, a draft for the current top-up period is made once and the admins are notified (`task_events` → `invoice_service.create_for_used_up_budget`). Budget periods: one per INITIAL/TOP_UP date (same-day top-ups merge; earlier work counts in the first period; adjustments belong to their period) — `budget_cycles`, `running_budget_left`, `daily_summary` in `production_rules` with tests. API: `/company/invoices` (list, cycles/{client}, create, get, patch, delete draft, send, pdf) kept off `/company/finance/...` to avoid its generic DELETE route; client: `/client-portal/billing`, `/client-portal/invoices/{id}/pdf` (own Sent/Paid only). Admin: new **Invoices** page (sidebar, FINANCE) with status tabs, client filter, slide-in create (top-up period cards or custom dates) and detail (send, preview, PDF, mark paid, void, delete draft, notes). Client: new **Billing** page (sidebar) like the owner's Vikas/Kalpana sheets — budget/used/left/pending tiles, last-14-days chart, budget periods, selected-day work, day-by-day table, full delivered-work table with budget left after each item, search, period filter and CSV, invoices with PDF download, payments. 216 backend tests pass. Browser-checked light, dark and phone; no internal costs or people on the client page; `[QA]` data, notifications, audit rows and test emails removed. |
| 12. Manager top-ups | ✅ Done (2026-11-14) | Manager payouts are now **top-ups** (advance). `production_rules.wallet_timeline` (same-day top-up counts before commission) + `budget_cycles` give `ManagerEarningsResponse.wallet`: topped up, earned, balance (negative = due to the manager, the next top-up covers it first; work is never blocked), one period per top-up and a running timeline. Shared `AdvanceWallet` on the Manager's My Earnings page and the Admin's Payments → Manager top-ups view; Manager dashboard tile shows Advance left / Due to you. 80% and used-up notifications (`advance.near` / `advance.over`) to the Admin and manager. Tests in `ManagerWalletTest`. |
| 12b. Owner feedback round (2026-11-14) | ✅ Done (2026-11-14) | **Live updates:** `useLiveRefresh` (shared realtime) reloads task lists, the open task and the Manager/Employee dashboard when a `task.*` notification arrives, so assigned work shows without a reload. **Notifications:** new three-note chime; audio unlocked on the first click so sounds play later; desktop alert also when the window is not focused; in-style cards (portalled to `<body>`) asking for cookie consent and notification permission ("Not now" asks again after 3 days). **Sign-in:** the access cookie now lives 7 days like the refresh token, and expired tokens are renewed on the next request (people were logged out after 30 minutes). **Dark mode:** the blue #0876ED logo in both themes (`getBrandLogo`). **Fonts:** every page checked in the browser renders Poppins; the `latin-ext` subset is now loaded so the ₹ sign is Poppins too. **Privacy:** `MoneyPrivacy` takes a `password` (Admin dashboard: `NEXT_PUBLIC_MONEY_PASSWORD`, default 1234) and `AmountEye` puts the eye next to an amount. **Client Billing** simplified: one card with the budget left (or payment due) and the eye beside it, the sum *Added − Used = Left*, top-ups, payments, delivered work with budget left after each, invoices. **Invoices:** create flow is client → *A top-up / This month / Last month / Pick dates* → live preview of every video and the total (`GET /company/invoices/preview`, same calculation as create) → *Save draft* or *Create and email*. Browser-checked (17 checks); `[QA]` data, notifications and test email removed. |
| 12c. Admin client payment tracking (2026-11-14) | ✅ Done (2026-11-14) | Admin dashboard gets a **Client payments** panel under Budget watch (owner request): per client, all-time billed vs received, the amount due, a paid meter (green when paid up, red when a sent invoice is past its due date), the last payment date and sent/overdue invoice counts; title shows the total to collect. Data comes from `client_payments` on `GET /company/finance/dashboard` (Admin only, from `client_balances`), top 6 by amount due. Amounts follow the dashboard's password eye. Browser-checked in light, dark and phone width. |
| 12d. Client details: Client work (2026-11-14) | ✅ Done (2026-11-14) | Admin client details page gets a **Client work** section under the client info (owner request: "each client details anni clear ga ravali"): delivered / billed / paid / still to collect cards (with budget left), videos per service, every video with filters (Delivered, Waiting review, In progress, Cancelled) and search, showing code, service, who edited it, manager, status, delivered/due date and price (row opens the task), then budget top-ups, payments received and invoices (PDF). Admin app only, through the shared page's `renderWork` slot; data from the existing Admin-only endpoints (tasks by client, budget, client payments, invoices), refreshed live. Tasks page now accepts `?client=<id>` ("Open in Tasks"). Browser-checked in light, dark and phone width. |
| 12e. Payment sheets (2026-11-14) | ✅ Done (2026-11-14) | Owner decisions: **every payment opens a new sheet automatically** (a manager top-up or a client budget top-up); the previous sheet closes the day before and **whatever is left, plus or minus, is carried into the new sheet**; old sheets stay with their dates. `budget_cycles` now returns `carried_in`, `ran_out_on` (the day the money ran out) and the sheet's own dated lines (carried in, payment, adjustments, each task/video with the running balance; work before the first payment is listed first). Shown with the shared `PaymentSheets` component on Manager earnings, the Admin's manager view, Client billing and Admin client details. New sidebar entries **Payment Sheets** for Admin (`GET /company/finance/sheets`: every manager and client, current sheet status Needs top-up / Used up / Running low (80%+ used) / OK, most urgent first) and for Manager (own sheets). Admin dashboard gets a **Payment sheets** panel listing who is running low or needs a top-up. Tests for carry-over, ran-out date and status; browser-checked (10 checks), `[QA]` rows removed. |
| 12f. Payment sheets: client payments and statement design (2026-11-14) | ✅ Done (2026-11-14) | Owner feedback: the Admin tops a client up by recording a **client payment**, so client sheets now open on each payment received (Payments → Client payments), not on budget entries (`InvoiceService._client_sheets`, `GET /company/finance/sheets/clients/{id}`, `sheets` on client billing). A client or manager with work but no payment yet still gets an open sheet starting at zero ("No payment yet"), so they show up and are flagged. Payment lines carry the method and reference ("Payment received · UPI · ref", "Top-up · Bank transfer"). Sheets redesigned as a statement: sheet tabs (status dot), a summary with what is left and the usage bar, four figure cards, then a Date / Details / Paid in / Used / Balance table with totals. Browser-checked on Admin sheets, Admin client page, dashboard, Manager sheets, Client billing, phone width and dark mode. Note: budget entries no longer open client sheets (they still drive the budget checks). |
| 13. Content calendar | ✅ Done (2026-11-14) | Table `content_calendar_entries` (migrations `20261114180000_content_calendar`, `20261114200000_calendar_links`). API: Admin `/company/calendar` (list by client/dates, add for a client, edit anything, delete, link a task, script file), client `/client-portal/calendar` (own entries only; ticks Recorded, Script, Instagram, YouTube; cannot tick Edited; cannot move or rename a video once work has started). **Every entry except a no-post day becomes a ticket** (owner request): a Pending, unassigned task due on that date, with the client's most-used rated service and a priority from how soon the date is (≤2 days Urgent, ≤5 High, ≤14 Medium, else Low); the Tasks page already lists open work by due date. Until someone takes the ticket it follows the entry's title and date, and removing the entry cancels it. **Edited** is computed: ticked when the linked task is Approved/Completed (the Admin can also tick it). Admins are notified of each new ticket. UI (Admin and Client sidebar **Content Calendar**): default **Sheet** view with the same columns as the owner's "Path Of Aditya Content Calendar" sheet (Date, Week, Day, Video Topic, Reference Video, Recorded, Script, Edited, Insta-Posted, Youtube-Post, Script, PDF's LINKS; plus Client and Ticket for the Admin), cells edited in place, plain tick boxes (owner: the sheet's colours only marked status), a "No Reel" row for no-post days, Script and PDF's LINKS as links typed in the add/edit form or the cell; type a topic in the last row to add one. A **Month** view with a day agenda is the second view. "Create task" (for an entry without a ticket) opens the Tasks form pre-filled and links the new task. Manager/Employee have no access. Tests for access, tickets and priority; browser-checked (light, dark, phone); `[QA]` rows, tickets and notifications removed. |
| 14. Chat | ✅ Done (2026-11-14) | Tables `chat_conversations` (DIRECT / GROUP / CLIENT), `chat_members` (membership + read state), `chat_messages` (reply, edit, soft delete), `chat_attachments`, `chat_statuses` (migrations `20261114220000_chat`, `20261114230000_chat_rooms_status`). Owner decisions: **client rooms are created by the admin by hand** (client, room name, the managers/employees in it; the client's login is always in; admins see every room); **direct chats** between anyone in the team (admin, managers, employees) and **between a client and the admin** only; **groups** made by the admin and managers (team only, never clients); everyone sets a **status** (Available / Busy / Away), shown as Offline when the app is closed (presence = an open live stream, kept in Redis). API `/chat` (people, status, unread, conversations, direct, groups, rooms, messages with files up to 25 MB × 10, edit, delete, read, typing, attachments, search), every rule server-side. Live over the existing SSE channel: `chat.message` (sender's own tabs get `own`), `chat.message.updated`, `chat.read`, `chat.typing`, `chat.conversation`. UI in all four apps (sidebar **Chat** and a floating chat button bottom right with the unread count): three panes (folders Inbox / Clients / Team / Direct with unread counts and my status | chats with All / Unread / Mine and search over titles and messages | thread with day separators, replies, files and image previews, edit/delete, Seen ticks, typing). Chat is full screen: no hero or footer, the sidebar collapses on entry (and can be opened), and the top bar is hidden on screens wider than 720px (kept on phones). New messages chime and show a toast or desktop alert when that chat is not on screen; toasts moved above the chat button. 10 rule tests; 34 browser checks (Admin, Manager, Employee, Client; light, dark, phone); `[QA]` chats removed. |
| 14b. Chat round 2 (2026-11-14) | ✅ Done (2026-11-14) | Owner feedback. **Notifications:** chat messages now reach the bell as one notification per chat that counts up ("2 new messages · …"; `notification_service.notify_chat`, `upsert_chat`), with the chime and a browser notification when the app is in the background; being added to a room or group is a `chat.added` notification; opening a chat marks its notifications read. Fixed: a notification link (`/chat?c=…`) lost the chat id before it could open it. **Status:** an Available / Busy / Away menu that opens upwards with coloured dots (the select opened off-screen). **People picker:** avatars no longer stretch; chosen people show as removable chips. **More advanced:** emoji reactions (table `chat_reactions`, migration `20261115000000_chat_reactions`, 8 fixed emoji, live), a details panel (people with role and status, shared photos and files, room settings), a "New messages" line, a jump-to-latest button with the count of new messages, drag-and-drop and paste of files with photo previews, a search result opens the chat on that message and highlights it, a click on a quoted reply jumps to it, animated typing dots, the online count in the header. The floating chat button shows the unread count in red. Tests for reactions and notifications; browser-checked; `[QA]` rooms, notifications and files removed (the owner's own chat kept). |
| 14c. Calls, meetings and calendars for every role (2026-11-14) | ✅ Done (2026-11-14) | Owner request. **Calls** ("like Google Meet / Zoom"): voice and video calls in any chat (direct, group, client room), several people at once, mute, camera, screen share, minimise to a bar and keep working, an incoming-call card with a ring tone on every page, decline, the call written into the chat ("Video call started" / "ended · 12 min"), a Join banner while a call runs, missed-call notifications. Media goes browser to browser (WebRTC mesh, public STUN); the server keeps who is in the call (`chat_calls`, `chat_call_participants`, 45 s heartbeat) and relays offers/answers/candidates only between people in the same call (`CallService`, `/chat/calls/*`). **Meetings**: schedule in a chat (name, date, time, length, voice/video, agenda; `chat_meetings`), everyone in the chat is notified, it shows in the chat's details with Join (from 10 minutes before) and on calendars. **Calendars**: Managers and Employees get a **Calendar** page (their tasks by due date, the content plan behind those tasks, meetings; `GET /workspace/calendar`, no prices); Admin and Client calendars show meetings too. Migration `20261115010000_chat_calls_meetings`. Calls need a TURN relay for people behind strict networks (not set up). Tests for call and meeting rules; two-browser video call checked end to end; `[QA]` data removed. |
| 15. Final check (round 2) | ✅ Done (2026-11-14) | **Code:** backend 258 unit tests pass; ruff, black and mypy all clean (the 17 old mypy errors fixed: pricing scope types, a missing None check, signup variable reuse, untyped helpers); all four apps pass `tsc`, `eslint` and a production `next build`. **Privacy (48 API checks with each role's own token):** Manager, Employee and Client are refused every Admin money, task, invoice, sheet and calendar API; their workspace tasks, dashboard and calendar carry no client prices, margin or revenue; employees cannot read commission nor managers salary; clients see only their own billing, calendar and chats; staff cannot read the admin–client chat; no login gives 401 and another company's id is refused. **Pages:** every sidebar page of all four apps opened in light desktop and dark phone (80 checks): no page errors, console errors, 5xx responses or sideways scrolling. **Flow:** create task → assign → start → submit (employee cannot approve) → admin approves → client billing, payment sheet, invoice preview and admin revenue all include it (11 checks). **Fixed:** clients were never told a video was ready: approval now notifies them (`task.delivered`, no price); dev backend reloads hung on open live streams (uvicorn `--timeout-graceful-shutdown 3`). **UI freeze:** current screens pixel-compared with the Phase 0 baseline; the only differences on frozen screens are the new sidebar entries, the floating chat button and the blue logo (all approved). `[QA]` data removed. Open: Docker has 7.7 GB and the dev servers run out of memory (raise to 12 GB+); calls need a TURN relay for strict networks; TSK-0001 is priced in USD; `/storage` 500 (old). |
| 15b. Security audit | ✅ Done (2026-11-14) | Cloudflare security-audit skill, quick profile, one agent (report in `~/security-audit-skill/Adverse-SAAS/run-1/`). **Fixed (high):** the 6-digit password reset code could be guessed with no limit, which allowed account takeover; now 5 checks per code, a new code at most once a minute, the same limit on email verification codes (migration `20261115020000_otp_attempt_limit`, 4 tests). **Hardening:** all four apps send anti-framing, nosniff, referrer and camera/mic/screen-share-self headers (calls re-checked); dev Postgres and Redis no longer published and Mailpit only on this machine; shared `1234` test accounts created only when `ENVIRONMENT=development`. **Checked clean:** tenant scope from the token, SQL parameters and allowlists, chat/call/file membership checks, private file storage, stored links, sessions and login lockout. Backend 262 tests, ruff, black, mypy clean; four apps pass `tsc`. Not covered by this quick pass: billing state-machine abuse, dependency review, upload quotas. Also fixed: `/storage` 500 when no logo had been uploaded (now 404). **Follow-up checks:** client calendar writes, invoice status changes and money field limits are enforced on the server (clean); `npm audit` finds nothing in the four apps; `pip-audit` finds nothing in the backend container; backend Python packages are now pinned to the versions the container runs. Known and accepted: Prisma CLI 6.19 pulls `deepmerge-ts` with a stack-exhaustion advisory, but it only merges our own config at migration time; the fix needs the breaking Prisma 7 upgrade. |

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
- Fixed 2026-11-14: any request under `/storage/...` returned a 500 while the `backend/storage` folder didn't exist (no logo uploaded yet). The backend now creates the folder at start-up, so a missing image is a 404.
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

## 10. Round 2: owner requests of 2026-11-14 (Phases 8–15)

The owner asked for a second set of features after Phase 7. Their reference material: the "Path Of Aditya" content calendar (Google Sheet), the "Vikas" client video-editing dashboard sheet, the "Kalpana Ethnic Studio" tracking sheet (their current invoice format) and a chat layout screenshot (inbox folders | conversation list | message thread).

### 10.1 Decisions (owner, 2026-11-14)

| Topic | Decision |
|---|---|
| UI freeze | Lifted only for: the Manager, Employee and Client **dashboards** (redesign in the style of the new Admin dashboard) and **dark mode**. Everything else stays frozen. |
| Dark mode | Near-black with brand blue: page `#0A0A0B`, cards `#121214`, borders `#232327`, text `#F5F5F7`, muted `#8E8E93`, accent `#0876ED`. Replaces the navy tokens and every hard-coded navy shade in all four apps (about 57 stylesheets). Light mode unchanged. |
| Privacy eye | Money on dashboards (Admin's revenue/margin/costs, Manager's earnings, Employee's salary) is hidden as `••••` on **every visit**; an eye button shows it until the page is left. |
| Client sees delivered videos | Changes the old rule. Clients see their **delivered** (Approved/Completed) videos: title, service, date, price, running budget left. Never: work in progress details, editor names, comments, internal notes, commission or margin. |
| Content calendar | Client adds entries (date, title, reference link, notes, optional script file). Progress columns split by owner: **client** ticks Recorded, Script, Insta posted, YouTube posted; **Edited** ticks itself when the linked task is approved; **admin** can change anything. |
| Chat with clients | **One shared room per client.** The admin and every manager/employee the admin grants access to that client see and reply in it. Staff also have direct and group chats among themselves. Clients cannot see staff-only chats or other clients. |
| Client invoices | **No GST** for now (a tax line can be switched on later). Prepared automatically when a client's **top-up is fully used** (admin is notified), and the admin can also make one for **any date range**. Admin emails it and it appears in the client portal. |
| Manager top-ups | Admin pays managers an **advance**; commission earned draws it down. If it runs out, the balance goes negative ("owes ₹X"), **work is never blocked**, and the next top-up clears it first. Shown period by period (one period per top-up). |

### 10.2 Phases

| Phase | Scope |
|---|---|
| **8. Dark mode + privacy eye** | New dark tokens in all four apps and `shared`; replace hard-coded navy `.dark` colours; re-check charts (dataviz palette on the new dark surface). Eye toggle on every money figure of the Admin dashboard, Payments/Reports summary tiles and the Manager/Employee earnings pages. |
| **9. Dashboards (Manager, Employee, Client)** | Rebuild these three dashboards in the Admin dashboard style: compact header, KPI tiles, small charts, work lists. Manager: commission this month, advance balance, tasks by status, due soon, monitoring. Employee: tasks by status, due soon, recent deliveries, salary (eye). Client: budget ring, used/left, videos this month, recent deliveries, calendar preview. |
| **10. Notifications (real-time)** | `notifications` table + API (list, unread count, mark read/all). Live delivery over **Server-Sent Events** (backend stream + Redis pub/sub; proxied through each app's Next.js API so login cookies keep working). Topbar bell becomes live (unread badge, dropdown), plus a Notifications page. Browser (desktop) notifications with a sound when the tab is in the background; sound and desktop toggles in Profile → Settings. Events: task assigned / status changed / comment / file, calendar entry added, budget 80% and exceeded, top-up used up, invoice ready/sent, payment recorded, manager balance low/negative, new chat message. |
| **11. Client billing + invoices** | Client **Billing** page: budget cycle picker (each top-up is a cycle), budget/used/left, delivered-videos table with running balance (like the Vikas and Kalpana sheets), date picker for "selected day" work, daily summary, charts (used vs left, videos per day), payment history. Admin side: **Invoices** (list, create for a top-up cycle or a date range, preview, PDF download, email to client, mark paid). PDF: Adverse logo, invoice number, client details, table of every video (S.No, date, title, service, amount), total, payments received with dates, balance due. |
| **12. Manager top-ups** | Treat manager payouts as **advances**: per-manager balance = top-ups − commission earned; periods (one per top-up) showing videos done, commission used, balance. Admin: add top-up from the manager page/Payments, low/negative balance warnings. Manager: My Earnings shows current balance, periods and history. |
| **13. Content calendar** | `content_calendar_entries` (client, date, title, reference URL, notes, script file, recorded, script ready, posted Insta, posted YouTube, no-post day, linked task). Client: month/list calendar to add and tick entries. Admin: all clients' entries by date, filter by client, **Create task** from an entry (client, title, reference prefilled; assign to manager/employee in one step). Edited ticks itself on approval. |
| **14. Chat** | Conversations (direct, group, client room), members, messages (text, replies, attachments on the owner's server, edit/delete), read receipts, typing indicator, online presence, unread counts, search. Admin grants managers/employees access to clients (also gives client-room access). Three-pane layout like the owner's screenshot: folders (Inbox, Clients, Team, Direct) · conversation list with All / Unread / Mine tabs and search · thread. Real-time over the same SSE channel; desktop notification + sound for new messages. In all four apps. |
| **15. Final check** | Same as Phase 7: tests, lint, types, builds, privacy checks per role, screenshots compared with Phase 7's (only the agreed screens may change). |

### 10.3 New data (summary; exact schema per phase)

- `notifications` (company, user, type, title, body, link, data, read_at); user notification preferences (sound, desktop).
- `invoices` (number per company, client, period start/end, budget cycle or custom range, totals, status draft/sent/paid, sent_at, pdf path) and `invoice_lines` (task, date, title, service, amount).
- Manager advances: reuse `manager_payouts` as top-ups (add a `kind`: ADVANCE / SETTLEMENT); balances computed from payouts and commission.
- `content_calendar_entries` as above.
- Chat: `chat_conversations` (type, title, client), `chat_members` (user, last_read_at, muted), `chat_messages` (sender, body, reply_to, edited_at, deleted_at), `chat_attachments`, `client_access` (client, staff user: who may work and chat with which client).

### 10.4 Notes

- Real-time needs Redis (already in Docker) and long-lived connections; four dev servers in 7.7 GB of Docker memory are already slow, so raise Docker memory to 12 GB or more before Phase 10.
- Privacy stays server-side: every new endpoint filters by role (clients only their own data; staff only clients they have access to; money only to those allowed).
