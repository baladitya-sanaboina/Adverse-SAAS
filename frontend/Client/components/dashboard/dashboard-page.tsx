"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DashboardHero } from "./dashboard-hero";
import { StatCard } from "./stat-card";
import { DashboardContentLoader } from "@/components/loader/dashboard-content-loader";

type ClientContact = {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  designation: string;
  is_primary: boolean;
  status: "ACTIVE" | "INACTIVE";
};

type PricingModeCode = "PER_VIDEO" | "PER_PIECE" | "MONTHLY_FIXED" | "MONTHLY_PACKAGE" | "COMMISSION_PER_DELIVERABLE";

type PricingRecord = {
  id: string;
  pricing_model: PricingModeCode;
  amount: string | number;
  currency: string;
  notes: string;
  effective_from: string;
  created_by_name: string;
};

type PricingItem = {
  service_id: string;
  service_name: string;
  service_code: string;
  service_description: string;
  configured: boolean;
  default_pricing_model: PricingModeCode;
  current_rate: PricingRecord | null;
};

type DashboardPayload = {
  client: {
    id: string;
    name: string;
    code: string;
    email: string | null;
    phone: string | null;
    website: string | null;
    address: string;
    city: string;
    state: string;
    country: string;
    status: "ACTIVE" | "INACTIVE";
    account_email: string | null;
    contacts: ClientContact[];
  };
  pricing: {
    items: PricingItem[];
    configured_services: number;
    missing_services: number;
  };
  packages: Array<{
    service_id: string;
    service_name: string;
    pricing_model: PricingModeCode;
    amount: string | number;
    currency: string;
    billing_period_label: string;
    notes: string;
  }>;
  work: {
    ready: boolean;
    message: string;
    total_projects: number | null;
    active_projects: number | null;
    completed_videos: number | null;
    pending_videos: number | null;
    items: Array<{
      task_id: string;
      title: string;
      service: string | null;
      status: string;
      due_date: string | null;
      completion_date: string | null;
      approval_status: string | null;
      final_output_url: string | null;
      client_charge: string | number | null;
    }>;
  };
  billing: {
    ready: boolean;
    message: string;
    total_billed: string | number | null;
    amount_received: string | number | null;
    pending_amount: string | number | null;
    monthly_billing: string | number | null;
    payments: Array<{
      id: string;
      amount: string | number;
      currency: string;
      received_at: string;
      reference: string | null;
      notes: string | null;
    }>;
  };
};

function money(amount: string | number | null | undefined, currency = "INR") {
  const numeric = amount == null ? Number.NaN : typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(numeric);
}

function pricingLabel(value: PricingModeCode) {
  return (
    {
      PER_VIDEO: "Per video",
      PER_PIECE: "Per piece",
      MONTHLY_FIXED: "Monthly fixed",
      MONTHLY_PACKAGE: "Monthly package",
      COMMISSION_PER_DELIVERABLE: "Commission / per deliverable",
    }[value] ?? value
  );
}

function statValue(value: number | null | undefined) {
  return value == null ? "—" : String(value);
}

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/client/dashboard", { cache: "no-store" });
      const body = (await response.json()) as DashboardPayload | { detail?: string };
      if (!response.ok) {
        throw new Error(typeof body === "object" && body && "detail" in body ? body.detail || "Unable to load dashboard." : "Unable to load dashboard.");
      }
      setData(body as DashboardPayload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 120);
    return () => window.clearTimeout(timer);
  }, [load, refreshKey]);

  const configuredRates = useMemo(
    () => (data?.pricing.items ?? []).filter((item) => item.current_rate !== null),
    [data?.pricing.items],
  );

  if (loading) return <DashboardContentLoader />;

  if (error) {
    return (
      <>
        <DashboardHero
          title="Welcome to the "
          highlight="Client Portal"
          description="Review project progress, documents, invoices, and support conversations in one place."
          action={<button type="button" onClick={() => setRefreshKey((current) => current + 1)}>Retry</button>}
        />
        <div className="dash-content">
          <section className="dash-panel client-dashboard-panel">
            <header>
              <h2>Unable to load your workspace</h2>
              <p>{error}</p>
            </header>
          </section>
        </div>
      </>
    );
  }

  return (
    <>
      <DashboardHero
        title="Welcome back, "
        highlight={data?.client.name ?? "Client"}
        description="Review live client profile details, approved pricing, and dashboard dependencies in one place."
        action={<button type="button" onClick={() => scrollToId("client-billing-panel")}>View billing summary</button>}
      />
      <div className="dash-content">
        <section className="dash-stats" aria-label="Workspace summary">
          <StatCard
            label="Active Projects"
            value={statValue(data?.work.active_projects)}
            change={data?.work.ready ? "Live project counts" : data?.work.message ?? "Project workflow pending"}
            icon="globe"
          />
          <StatCard
            label="Completed Videos"
            value={statValue(data?.work.completed_videos)}
            change={data?.work.ready ? "Completed deliverables" : "Task workflow pending"}
            icon="eye"
          />
          <StatCard
            label="Monthly Billing"
            value={money(data?.billing.monthly_billing)}
            change={data?.packages.length ? `${data.packages.length} monthly package${data.packages.length === 1 ? "" : "s"} configured` : "No monthly package configured"}
            icon="money"
          />
          <StatCard
            label="Pending Payments"
            value={money(data?.billing.pending_amount)}
            change={data?.billing.ready ? "Live payment reconciliation" : data?.billing.message ?? "Billing workflow pending"}
            icon="bolt"
          />
        </section>

        <section className="dash-workspace-grid">
          <article className="dash-panel client-dashboard-panel" id="client-work-panel">
            <header>
              <h2>Client profile</h2>
              <p>Your current workspace identity and primary contacts.</p>
            </header>
            <div className="client-dashboard-grid">
              <div>
                <span>Client code</span>
                <strong>{data?.client.code ?? "—"}</strong>
              </div>
              <div>
                <span>Workspace email</span>
                <strong>{data?.client.account_email || data?.client.email || "—"}</strong>
              </div>
              <div>
                <span>Contact phone</span>
                <strong>{data?.client.phone || "—"}</strong>
              </div>
              <div>
                <span>Website</span>
                <strong>{data?.client.website || "—"}</strong>
              </div>
            </div>
            <div className="client-dashboard-list compact">
              {(data?.client.contacts ?? []).length ? (
                data!.client.contacts.map((contact) => (
                  <article key={contact.id}>
                    <div>
                      <strong>{`${contact.first_name} ${contact.last_name}`.trim()}</strong>
                      <span>{contact.designation || "Client contact"}</span>
                    </div>
                    <div>
                      <strong>{contact.email || "No email"}</strong>
                      <span>{contact.phone || "No phone"}</span>
                    </div>
                  </article>
                ))
              ) : (
                <article>
                  <div>
                    <strong>No contacts configured</strong>
                    <span>Your admin can add authorized client contacts here.</span>
                  </div>
                </article>
              )}
            </div>
          </article>

          <article className="dash-panel client-dashboard-panel" id="client-billing-panel">
            <header>
              <h2>Pricing and billing</h2>
              <p>Current client-specific service rates and monthly package references.</p>
            </header>
            <div className="client-dashboard-summary">
              <div>
                <span>Configured services</span>
                <strong>{data?.pricing.configured_services ?? 0}</strong>
              </div>
              <div>
                <span>Pending billed amount</span>
                <strong>{money(data?.billing.pending_amount)}</strong>
              </div>
              <div>
                <span>Total billed</span>
                <strong>{money(data?.billing.total_billed)}</strong>
              </div>
            </div>
            <div className="client-dashboard-list">
              {(data?.packages.length ?? 0) > 0 ? (
                data!.packages.map((pkg) => (
                  <article key={pkg.service_id}>
                    <div>
                      <strong>{pkg.service_name}</strong>
                      <span>{pricingLabel(pkg.pricing_model)} · {pkg.billing_period_label}</span>
                    </div>
                    <div>
                      <strong>{money(pkg.amount, pkg.currency)}</strong>
                      <span>{pkg.notes || "No package notes recorded."}</span>
                    </div>
                  </article>
                ))
              ) : configuredRates.length ? (
                configuredRates.slice(0, 6).map((item) => (
                  <article key={item.service_id}>
                    <div>
                      <strong>{item.service_name}</strong>
                      <span>{pricingLabel(item.current_rate?.pricing_model ?? item.default_pricing_model)}</span>
                    </div>
                    <div>
                      <strong>{money(item.current_rate?.amount, item.current_rate?.currency ?? "INR")}</strong>
                      <span>{item.current_rate?.notes || "Client-specific pricing is active."}</span>
                    </div>
                  </article>
                ))
              ) : (
                <article>
                  <div>
                    <strong>No client pricing configured</strong>
                    <span>Your admin can add service-specific rates from the Clients area.</span>
                  </div>
                </article>
              )}
            </div>
          </article>
        </section>

        <section className="dash-workspace-grid">
          <article className="dash-panel client-dashboard-panel">
            <header>
              <h2>Work visibility</h2>
              <p>{data?.work.message ?? "Task workflow status unavailable."}</p>
            </header>
            <div className="client-dashboard-list">
              {(data?.work.items ?? []).length ? (
                data!.work.items.map((item) => (
                  <article key={item.task_id}>
                    <div>
                      <strong>{item.title}</strong>
                      <span>{item.service || item.status}</span>
                    </div>
                    <div>
                      <strong>{item.due_date ? new Date(item.due_date).toLocaleDateString() : "No due date"}</strong>
                      <span>{item.approval_status || item.status}</span>
                    </div>
                  </article>
                ))
              ) : (
                <article>
                  <div>
                    <strong>No client work items available</strong>
                    <span>Approved task and deliverable tracking will appear here once the workflow is connected.</span>
                  </div>
                </article>
              )}
            </div>
          </article>

          <article className="dash-panel client-dashboard-panel">
            <header>
              <h2>Quick actions</h2>
              <p>Open the most relevant client workspace sections.</p>
            </header>
            <div className="dash-actions">
              <button type="button" onClick={() => scrollToId("client-work-panel")}>View client contacts</button>
              <button type="button" onClick={() => scrollToId("client-billing-panel")}>Review pricing</button>
            </div>
          </article>
        </section>
      </div>
    </>
  );
}
