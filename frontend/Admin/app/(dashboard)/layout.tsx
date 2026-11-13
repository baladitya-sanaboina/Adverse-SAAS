import type { ReactNode } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import "@/styles/company-settings.css";

export default function ApplicationShell({ children }: { children: ReactNode }) {
  return <DashboardLayout roleLabel="Company Admin">{children}</DashboardLayout>;
}
