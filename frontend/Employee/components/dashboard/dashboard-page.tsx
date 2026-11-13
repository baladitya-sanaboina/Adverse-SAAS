"use client";

import { useRouter } from "next/navigation";
import { DashboardHero } from "./dashboard-hero";
import { WorkspaceDashboardBody } from "@/components/workspace/workspace-pages";

export function DashboardPage() {
  const router = useRouter();
  return (
    <>
      <DashboardHero
        title="Do your best work in the "
        highlight="Employee Workspace"
        description="Stay on top of assigned work, attendance, documents, and daily delivery updates."
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
