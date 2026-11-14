"use client";

import { WorkspaceTasksPage } from "@loopless-shared/workspace/workspace-tasks-page";

export { EmployeeSalaryPage } from "@loopless-shared/workspace/workspace-earnings";

/** Employees see only tasks assigned to them (only managers can monitor). */
export function MyTasksPage() {
  return <WorkspaceTasksPage canMonitor={false} />;
}
