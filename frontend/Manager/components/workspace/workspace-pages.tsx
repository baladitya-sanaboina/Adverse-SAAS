"use client";

import { WorkspaceTasksPage } from "@loopless-shared/workspace/workspace-tasks-page";

export { ManagerEarningsPage, ManagerSheetsPage } from "@loopless-shared/workspace/workspace-earnings";

/** Managers see tasks assigned to them and tasks they monitor. */
export function MyTasksPage() {
  return <WorkspaceTasksPage canMonitor />;
}
