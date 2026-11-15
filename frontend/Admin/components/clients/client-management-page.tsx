"use client";

import { ClientManagementPage as SharedClientManagementPage } from "@loopless-shared/clients/client-management-page";
import { ClientBillingSettings } from "./client-billing-settings";
import { ClientWorkPanel } from "./client-work-panel";

/** Admin's client page: the shared page plus the client's videos, money and billing (Admin only). */
export function ClientManagementPage({ initialClientId }: { initialClientId?: string }) {
  return (
    <SharedClientManagementPage
      initialClientId={initialClientId}
      renderWork={(clientId) => (
        <>
          <ClientWorkPanel clientId={clientId} />
          <ClientBillingSettings clientId={clientId} />
        </>
      )}
    />
  );
}
