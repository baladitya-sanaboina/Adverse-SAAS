import type { ReactNode } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";

export default function ApplicationShell({ children }: { children: ReactNode }) {
  return <DashboardLayout roleLabel="Company Employee">{children}</DashboardLayout>;
}
