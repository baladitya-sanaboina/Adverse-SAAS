"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DashboardHero } from "./dashboard-hero";
import { StatCard } from "./stat-card";
import { DashboardContentLoader } from "@/components/loader/dashboard-content-loader";
import "@/styles/client-portal.css";

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

type PricingItem = {
  service_id: string;
  service_name: string;
  service_code: string;
  configured: boolean;
  default_pricing_model: PricingModeCode;
  current_rate: {
    id: string;
    pricing_model: PricingModeCode;
    amount: string | number;
    currency: string;
    notes: string;
  } | null;
};

/** Profile and agreed rates (GET /clients/me/dashboard). */
type ProfilePayload = {
  client: {
    id: string;
    name: string;
    code: string;
    email: string | null;
    phone: string | null;
    website: string | null;
    account_email: string | null;
    contacts: ClientContact[];
  };
  pricing: { items: PricingItem[] };
};

type PaymentMethod = "CASH" | "BANK_TRANSFER" | "UPI" | "CHEQUE" | "CARD" | "OTHER";

/** Work counts, budget and payments (GET /client-portal/summary). Never contains a task list. */
type SummaryPayload = {
  client_name: string;
  currency: string;
  completed_items: number;
  in_progress_items: number;
  services: { service_id: string; service_name: string; completed: number; in_progress: number; charged: string }[];
  budget: { has_budget: boolean; total: string; used: string; remaining: string; overage: string };
  total_charged: string;
  total_paid: string;
  pending_amount: string;
  current_month_charged: string;
  payments: { amount: string; received_on: string; method: PaymentMethod; reference: string }[];
};

const METHOD_LABELS: Record<PaymentMethod, string> = {
  BANK_TRANSFER: "Bank transfer",
  UPI: "UPI",
  CASH: "Cash",
  CHEQUE: "Cheque",
  CARD: "Card",
  OTHER: "Other",
};

function money(amount: string | number | null | undefined, currency = "INR") {
  const numeric = amount == null ? Number.NaN : typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(numeric);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function pricingLabel(value: PricingModeCode) {
  return (
    {
      PER_VIDEO: "Per video",
      PER_PIECE: "Per piece",
      MONTHLY_FIXED: "Monthly fixed",
      MONTHLY_PACKAGE: "Monthly package",
      COMMISSION_PER_DELIVERABLE: "Per deliverable",
    }[value] ?? value
  );
}

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  const body = (await response.json().catch(() => ({}))) as T | { detail?: string };
  if (!response.ok) {
    const detail = typeof body === "object" && body && "detail" in body ? body.detail : "";
    throw new Error(detail || "Unable to load your workspace.");
  }
  return body as T;
}

export function DashboardPage() {
  const [profile, setProfile] = useState<ProfilePayload | null>(null);
  const [summary, setSummary] = useState<SummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [summaryError, setSummaryError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setSummaryError("");
    const [profileResult, summaryResult] = await Promise.allSettled([
      getJson<ProfilePayload>("/api/client/dashboard"),
      getJson<SummaryPayload>("/api/client/summary"),
    ]);
    if (profileResult.status === "fulfilled") setProfile(profileResult.value);
    else setError(profileResult.reason instanceof Error ? profileResult.reason.message : "Unable to load dashboard.");
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    else
      setSummaryError(
        summaryResult.reason instanceof Error ? summaryResult.reason.message : "Work and billing are unavailable.",
      );
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 120);
    return () => window.clearTimeout(timer);
  }, [load, refreshKey]);

  const configuredRates = useMemo(
    () => (profile?.pricing.items ?? []).filter((item) => item.current_rate !== null),
    [profile?.pricing.items],
  );

  if (loading) return <DashboardContentLoader />;

  if (error && !summary) {
    return (
      <>
        <DashboardHero
          title="Welcome to the "
          highlight="Client Portal"
          description="See the work delivered for you, your budget and your payments in one place."
          action={
            <button type="button" onClick={() => setRefreshKey((current) => current + 1)}>
              Retry
            </button>
          }
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

  const currency = summary?.currency ?? "INR";
  const budget = summary?.budget;
  const overBudget = Boolean(budget?.has_budget && Number(budget.overage) > 0);
  const usedPercent =
    budget?.has_budget && Number(budget.total) > 0
      ? Math.min(100, Math.round((Number(budget.used) / Number(budget.total)) * 100))
      : 0;
  const topServices = (summary?.services ?? [])
    .filter((service) => service.completed > 0)
    .slice(0, 2)
    .map((service) => `${service.service_name} ${service.completed}`)
    .join(" · ");

  return (
    <>
      <DashboardHero
        title="Welcome back, "
        highlight={profile?.client.name ?? summary?.client_name ?? "Client"}
        description="See the work delivered for you, your budget and your payments in one place."
        action={
          <button type="button" onClick={() => scrollToId("client-budget-panel")}>
            View budget
          </button>
        }
      />
      <div className="dash-content">
        <section className="dash-stats" aria-label="Workspace summary">
          <StatCard
            label="Work Delivered"
            value={summary ? String(summary.completed_items) : "—"}
            change={summary ? topServices || "Approved and completed items" : "Not available yet"}
            icon="eye"
          />
          <StatCard
            label="In Progress"
            value={summary ? String(summary.in_progress_items) : "—"}
            change="Being worked on now"
            icon="bolt"
          />
          <StatCard
            label="Budget Remaining"
            value={budget?.has_budget ? money(budget.remaining, currency) : "—"}
            change={
              !budget?.has_budget
                ? "No budget recorded yet"
                : overBudget
                  ? `Over budget by ${money(budget.overage, currency)}`
                  : `of ${money(budget.total, currency)} budget`
            }
            icon="globe"
            tone={overBudget ? "warning" : undefined}
          />
          <StatCard
            label="Pending Payment"
            value={summary ? money(summary.pending_amount, currency) : "—"}
            change={
              summary
                ? `Billed ${money(summary.total_charged, currency)} · paid ${money(summary.total_paid, currency)}`
                : "Not available yet"
            }
            icon="money"
          />
        </section>

        {summaryError && (
          <section className="dash-panel client-dashboard-panel">
            <header>
              <h2>Work and billing are not available</h2>
              <p>{summaryError}</p>
            </header>
          </section>
        )}

        <section className="dash-workspace-grid">
          <article className="dash-panel client-dashboard-panel" id="client-budget-panel">
            <header>
              <h2>Budget</h2>
              <p>The amount you set aside with your agency, and how much of it approved work has used.</p>
            </header>
            {budget?.has_budget ? (
              <>
                <div className="client-dashboard-summary">
                  <div>
                    <span>Budget</span>
                    <strong>{money(budget.total, currency)}</strong>
                  </div>
                  <div>
                    <span>Used</span>
                    <strong>{money(budget.used, currency)}</strong>
                  </div>
                  <div>
                    <span>{overBudget ? "Over budget" : "Remaining"}</span>
                    <strong className={overBudget ? "client-portal-negative" : undefined}>
                      {money(overBudget ? budget.overage : budget.remaining, currency)}
                    </strong>
                  </div>
                </div>
                <div className="client-portal-meter-wrap">
                  <div
                    className={`client-portal-meter${overBudget ? " over" : usedPercent >= 80 ? " near" : ""}`}
                    role="meter"
                    aria-label="Budget used"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={usedPercent}
                  >
                    <i style={{ width: `${usedPercent}%` }} />
                  </div>
                  <span>{usedPercent}% used</span>
                </div>
                {overBudget ? (
                  <p className="client-portal-alert" role="status">
                    Approved work has gone {money(budget.overage, currency)} over your budget. Please contact your
                    agency to top it up.
                  </p>
                ) : usedPercent >= 80 ? (
                  <p className="client-portal-note" role="status">
                    You have used most of your budget. Consider a top-up so work continues smoothly.
                  </p>
                ) : null}
              </>
            ) : (
              <div className="client-dashboard-list">
                <article>
                  <div>
                    <strong>No budget recorded yet</strong>
                    <span>Your agency will add your budget and any top-ups here.</span>
                  </div>
                </article>
              </div>
            )}
          </article>
          <article className="dash-panel client-dashboard-panel" id="client-rates-panel">
            <header>
              <h2>Your rates</h2>
              <p>Prices agreed with your agency for each type of work.</p>
            </header>
            <div className="client-dashboard-list">
              {configuredRates.length ? (
                configuredRates.map((item) => (
                  <article key={item.service_id}>
                    <div>
                      <strong>{item.service_name}</strong>
                      <span>{pricingLabel(item.current_rate?.pricing_model ?? item.default_pricing_model)}</span>
                    </div>
                    <div>
                      <strong>{money(item.current_rate?.amount, item.current_rate?.currency ?? currency)}</strong>
                      <span>{item.current_rate?.notes || "Current rate"}</span>
                    </div>
                  </article>
                ))
              ) : (
                <article>
                  <div>
                    <strong>No rates set yet</strong>
                    <span>Your agency will add the price for each type of work.</span>
                  </div>
                </article>
              )}
            </div>
          </article>
        </section>

        <section className="dash-workspace-grid">
          <article className="dash-panel client-dashboard-panel" id="client-work-panel">
            <header>
              <h2>Work delivered</h2>
              <p>Finished work by service. You are billed only for work the agency has approved.</p>
            </header>
            <div className="client-dashboard-list">
              {(summary?.services ?? []).length ? (
                summary!.services.map((service) => (
                  <article key={service.service_id}>
                    <div>
                      <strong>
                        {service.service_name}: {service.completed} delivered
                      </strong>
                      <span>{service.in_progress ? `${service.in_progress} in progress` : "Nothing in progress"}</span>
                    </div>
                    <div>
                      <strong>{money(service.charged, currency)}</strong>
                      <span>Billed for this service</span>
                    </div>
                  </article>
                ))
              ) : (
                <article>
                  <div>
                    <strong>No work delivered yet</strong>
                    <span>Counts appear here as your agency completes work for you.</span>
                  </div>
                </article>
              )}
            </div>
          </article>
          <article className="dash-panel client-dashboard-panel">
            <header>
              <h2>Quick actions</h2>
              <p>Jump to the part of your workspace you need.</p>
            </header>
            <div className="dash-actions">
              <button type="button" onClick={() => scrollToId("client-work-panel")}>
                Work delivered
              </button>
              <button type="button" onClick={() => scrollToId("client-budget-panel")}>
                Budget
              </button>
              <button type="button" onClick={() => scrollToId("client-billing-panel")}>
                Payments
              </button>
              <button type="button" onClick={() => scrollToId("client-rates-panel")}>
                Rates
              </button>
            </div>
          </article>
        </section>

        <section className="dash-workspace-grid">
          <article className="dash-panel client-dashboard-panel" id="client-billing-panel">
            <header>
              <h2>Billing and payments</h2>
              <p>
                {summary
                  ? `Billed this month: ${money(summary.current_month_charged, currency)}`
                  : "Your billing summary will appear here."}
              </p>
            </header>
            <div className="client-dashboard-summary">
              <div>
                <span>Total billed</span>
                <strong>{money(summary?.total_charged, currency)}</strong>
              </div>
              <div>
                <span>Paid</span>
                <strong>{money(summary?.total_paid, currency)}</strong>
              </div>
              <div>
                <span>Pending</span>
                <strong>{money(summary?.pending_amount, currency)}</strong>
              </div>
            </div>
            <div className="client-dashboard-list">
              {(summary?.payments ?? []).length ? (
                summary!.payments.map((payment, index) => (
                  <article key={`${payment.received_on}-${index}`}>
                    <div>
                      <strong>{money(payment.amount, currency)}</strong>
                      <span>{METHOD_LABELS[payment.method] ?? payment.method}</span>
                    </div>
                    <div>
                      <strong>{formatDate(payment.received_on)}</strong>
                      <span>{payment.reference || "Payment received"}</span>
                    </div>
                  </article>
                ))
              ) : (
                <article>
                  <div>
                    <strong>No payments recorded yet</strong>
                    <span>Payments you make appear here once your agency records them.</span>
                  </div>
                </article>
              )}
            </div>
          </article>
          <article className="dash-panel client-dashboard-panel" id="client-profile-panel">
            <header>
              <h2>Client profile</h2>
              <p>Your workspace identity and primary contacts.</p>
            </header>
            <div className="client-dashboard-grid">
              <div>
                <span>Client code</span>
                <strong>{profile?.client.code ?? "—"}</strong>
              </div>
              <div>
                <span>Workspace email</span>
                <strong>{profile?.client.account_email || profile?.client.email || "—"}</strong>
              </div>
              <div>
                <span>Contact phone</span>
                <strong>{profile?.client.phone || "—"}</strong>
              </div>
            </div>
            <div className="client-dashboard-list compact">
              {(profile?.client.contacts ?? []).length ? (
                profile!.client.contacts.map((contact) => (
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
                    <span>Your agency can add authorised contacts here.</span>
                  </div>
                </article>
              )}
            </div>
          </article>
        </section>
      </div>
    </>
  );
}
