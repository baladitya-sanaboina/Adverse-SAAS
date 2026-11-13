# Adverse SaaS

Video-production agency management app: four Next.js apps (`frontend/Admin`, `Manager`, `Employee`, `Client`) and one FastAPI backend (`backend/`, PostgreSQL via psycopg, Prisma for schema/migrations). See `README.md` for running it.

## Read first

- **`docs/ProductionManagementPlan.md`**: requirements, the owner's business decisions (pricing, salaries, commission, budgets, permissions), target data model, build phases and progress. Update its Progress section as work finishes.
- **`docs/UIStandards.md`** and **`docs/DevelopmentRules.md`**: mandatory UI and code rules.

## Hard rules

- The existing UI is frozen: never change existing screens, colors, fonts, theme, sidebar, topbar, hero or layouts. New pages reuse existing components and theme tokens only. New sidebar entries are allowed.
- Never use a native `<select>`; use the existing custom select component.
- Financial data (client prices, revenue, margin, other people's pay) must be filtered on the server per role, never only hidden in the UI.
- Plan with the owner before large builds. Never push to git without explicit approval.
