import type { CompanyDashboard, CompanyDashboardError } from "./types";

export async function loadCompanyDashboard(): Promise<CompanyDashboard> {
  const response = await fetch("/api/company/dashboard", { cache: "no-store" });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as CompanyDashboardError;
    throw new Error(payload.detail || "Unable to load your company dashboard.");
  }
  return response.json() as Promise<CompanyDashboard>;
}
