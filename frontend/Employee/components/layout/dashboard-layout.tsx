import type { ReactNode } from "react";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import "@/styles/dashboard.css";
import "@/styles/foundation.css";
import "@/styles/font-structure.css";
import "@/styles/profile.css";
import "@/styles/company-branding.css";
import "@/styles/management-surfaces.css";

export function DashboardLayout({ children, roleLabel }: { children: ReactNode; roleLabel: string }) {
  return <DashboardShell roleLabel={roleLabel}>{children}</DashboardShell>;
}
