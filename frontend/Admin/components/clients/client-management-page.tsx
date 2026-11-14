"use client";

import { ClientManagementPage as SharedClientManagementPage } from "@loopless-shared/clients/client-management-page";
import { ClientWorkPanel } from "./client-work-panel";

/** Admin's client page: the shared page plus the client's videos and money (Admin only). */
export function ClientManagementPage({ initialClientId }: { initialClientId?: string }) {
  return (
    <SharedClientManagementPage
      initialClientId={initialClientId}
      renderWork={(clientId) => <ClientWorkPanel clientId={clientId} />}
    />
  );
}
