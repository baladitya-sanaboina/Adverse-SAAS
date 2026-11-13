// Captures full-page screenshots of every existing screen in the four role apps.
// Used to prove the existing UI is unchanged (docs/ProductionManagementPlan.md, Phase 0 and Phase 7).
//
// Usage: PLAYWRIGHT_FROM=<folder where `npm i playwright` was run> node qa/capture-ui.mjs <output-dir>
// Requires the Docker stack running (apps on 3000-3003).
// Optional: CHROMIUM_PATH=/path/to/chromium to use an already-downloaded browser.

import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(
  process.env.PLAYWRIGHT_FROM ? join(process.env.PLAYWRIGHT_FROM, "resolve-from-here.js") : import.meta.url,
);
const { chromium } = require("playwright");

const outDir = process.argv[2];
if (!outDir) {
  console.error("Usage: node qa/capture-ui.mjs <output-dir>");
  process.exit(1);
}

const PASSWORD = "1234"; // development-only test accounts (development_test_credentials_service.py)
const SETTINGS_TABS = [
  "Profile",
  "Branding",
  "Contact",
  "Regional",
  "Notifications",
  "Preferences",
  "Services & Pricing",
  "Integrations",
  "Workflows",
];

const apps = [
  {
    name: "admin",
    base: "http://localhost:3000",
    email: "adverseadmin@gmail.com",
    routes: [
      "/dashboard",
      "/dashboard/about",
      "/employees",
      "/clients",
      "/crm",
      "/profile",
      "/company/departments",
      "/company/branches",
      "/company/invitations",
      "/company/users",
      "/company/roles",
    ],
    settingsTabs: true,
    details: [
      { api: "/api/company/clients", path: (id) => `/clients/${id}`, label: "client-detail" },
      { api: "/api/company/employees", path: (id) => `/employees/${id}`, label: "employee-detail" },
    ],
  },
  {
    name: "manager",
    base: "http://localhost:3001",
    email: "adversemanager@gmail.com",
    routes: ["/dashboard", "/dashboard/about", "/employees", "/clients", "/crm", "/profile", "/settings"],
    details: [{ api: "/api/company/clients", path: (id) => `/clients/${id}`, label: "client-detail" }],
  },
  {
    name: "employee",
    base: "http://localhost:3002",
    email: "adverseemployee@gmail.com",
    routes: ["/dashboard", "/dashboard/about", "/clients", "/crm", "/profile", "/settings"],
    details: [],
  },
  {
    name: "client",
    base: "http://localhost:3003",
    email: "adverseclient@gmail.com",
    routes: ["/dashboard", "/dashboard/about", "/profile", "/settings"],
    details: [],
  },
];

const variants = [
  { label: "desktop-light", viewport: { width: 1440, height: 900 }, colorScheme: "light" },
  { label: "desktop-dark", viewport: { width: 1440, height: 900 }, colorScheme: "dark" },
  { label: "mobile-light", viewport: { width: 390, height: 844 }, colorScheme: "light", isMobile: true },
];

const slug = (value) => value.replace(/^\//, "").replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "root";

async function settle(page) {
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1500);
}

async function shot(page, file) {
  await page.screenshot({ path: file, fullPage: true, animations: "disabled", caret: "hide" });
  console.log("saved", file);
}

function firstId(payload) {
  const list = Array.isArray(payload) ? payload : payload?.items ?? payload?.data ?? payload?.results ?? [];
  return list[0]?.id ?? null;
}

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const failures = [];

for (const app of apps) {
  for (const variant of variants) {
    const dir = join(outDir, app.name, variant.label);
    mkdirSync(dir, { recursive: true });
    const context = await browser.newContext({
      viewport: variant.viewport,
      colorScheme: variant.colorScheme,
      isMobile: variant.isMobile ?? false,
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => failures.push(`${app.name}/${variant.label}: page error ${error.message}`));

    // Logged-out login screen
    await page.goto(`${app.base}/login`);
    await settle(page);
    await shot(page, join(dir, "login.png"));

    const login = await context.request.post(`${app.base}/api/auth/login`, {
      data: { email: app.email, password: PASSWORD },
    });
    if (!login.ok()) {
      failures.push(`${app.name}: login failed ${login.status()} ${await login.text()}`);
      await context.close();
      continue;
    }

    for (const route of app.routes) {
      await page.goto(`${app.base}${route}`);
      await settle(page);
      await shot(page, join(dir, `${slug(route)}.png`));
    }

    if (app.settingsTabs) {
      await page.goto(`${app.base}/settings`);
      await settle(page);
      for (const tab of SETTINGS_TABS) {
        const button = page.locator(".company-settings-tabs button", { hasText: tab }).first();
        if ((await button.count()) === 0) {
          failures.push(`${app.name}/${variant.label}: settings tab "${tab}" not found`);
          continue;
        }
        await button.click();
        await settle(page);
        await shot(page, join(dir, `settings-${slug(tab)}.png`));
      }
    }

    for (const detail of app.details) {
      const response = await context.request.get(`${app.base}${detail.api}`);
      const id = response.ok() ? firstId(await response.json().catch(() => null)) : null;
      if (!id) {
        failures.push(`${app.name}/${variant.label}: no record for ${detail.label} (${response.status()})`);
        continue;
      }
      await page.goto(`${app.base}${detail.path(id)}`);
      await settle(page);
      await shot(page, join(dir, `${detail.label}.png`));
    }

    await context.close();
  }
}

await browser.close();
if (failures.length) {
  console.log("\nNOTES:");
  for (const failure of failures) console.log(" -", failure);
}
