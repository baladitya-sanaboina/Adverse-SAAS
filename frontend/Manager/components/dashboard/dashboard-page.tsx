"use client";

import { useRouter } from "next/navigation";
import { DashboardHero } from "./dashboard-hero";
import { WorkspaceDashboardBody } from "@/components/workspace/workspace-pages";

export function DashboardPage() {
  const router = useRouter();
  return (
    <>
      <DashboardHero
        title="Lead your "
        highlight="Manager Workspace"
        description="Track delivery, client momentum, and team execution from one clean Adverse command center."
        action={
          <button type="button" onClick={() => router.push("/tasks")}>
            Open my tasks
          </button>
        }
      />
      <WorkspaceDashboardBody />
    </>
  );
}
