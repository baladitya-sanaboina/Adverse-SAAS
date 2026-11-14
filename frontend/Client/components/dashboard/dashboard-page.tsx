"use client";

/*
 * Client dashboard in the style of the Admin dashboard (owner request 2026-11-14).
 * Data: GET /client-portal/summary (counts, budget, deliveries, payments) and
 * GET /clients/me/dashboard (profile and agreed rates). No internal costs, people or task codes.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCheck, Hourglass, PiggyBank, ReceiptText, Wallet } from "lucide-react";
import { DashHeader, DashLoading, MonthBars, Panel, PanelHead, Tile, todayText } from "./role-dashboard-ui";
import "@/styles/client-portal.css";

type PricingModeCode = "PER_VIDEO" | "PER_PIECE" | "MONTHLY_FIXED" | "MONTHLY_PACKAGE" | "COMMISSION_PER_DELIVERABLE";

type ProfilePayload = {
  client: {
    id: string;
    name: string;
    code: string;
    email: string | null;
    phone: string | null;
    account_email: string | null;
  };
  pricing: {
    items: {
      service_id: string;
      service_name: string;
      default_pricing_model: PricingModeCode;
      current_rate: { pricing_model: PricingModeCode; amount: string | number; currency: string; notes: string } | null;
    }[];
  };
};

type PaymentMethod = "CASH" | "BANK_TRANSFER" | "UPI" | "CHEQUE" | "CARD" | "OTHER";

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
  recent_deliveries: { title: string; service_name: string; delivered_on: string; amount: string }[];
  monthly: { month: string; items: number; amount: string }[];
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
  const numeric = amount == null ? Number.NaN : Number(amount);
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

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  const body = (await response.json().catch(() => ({}))) as T | { detail?: string };
  if (!response.ok) {
    const detail = typeof body === "object" && body && "detail" in body ? body.detail : "";
    throw new Error(detail || "Unable to load your workspace.");
  }
  return body as T;
}

/** Ring showing how much of the budget approved work has used. */
function BudgetRing({ percent, over }: { percent: number; over: boolean }) {
  const radius = 52;
  const length = 2 * Math.PI * radius;
  const filled = (Math.min(percent, 100) / 100) * length;
  return (
    <svg className="client-ring" viewBox="0 0 132 132" role="img" aria-label={`${percent}% of budget used`}>
      <circle className="track" cx="66" cy="66" r={radius} />
      <circle
        className={`fill${over ? " over" : percent >= 80 ? " near" : ""}`}
        cx="66"
        cy="66"
        r={radius}
        strokeDasharray={`${filled} ${length - filled}`}
        transform="rotate(-90 66 66)"
      />
      <text x="66" y="64" textAnchor="middle" className="value">
        {percent}%
      </text>
      <text x="66" y="82" textAnchor="middle" className="label">
        used
      </text>
    </svg>
  );
}

export function DashboardPage() {
  const [profile, setProfile] = useState<ProfilePayload | null>(null);
  const [summary, setSummary] = useState<SummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const [profileResult, summaryResult] = await Promise.allSettled([
      getJson<ProfilePayload>("/api/client/dashboard"),
      getJson<SummaryPayload>("/api/client/summary"),
    ]);
    if (profileResult.status === "fulfilled") setProfile(profileResult.value);
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    else setError(summaryResult.reason instanceof Error ? summaryResult.reason.message : "Unable to load.");
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const rates = useMemo(
    () => (profile?.pricing.items ?? []).filter((item) => item.current_rate !== null),
    [profile?.pricing.items],
  );

  const name = profile?.client.name ?? summary?.client_name ?? "";
  const header = (
    <DashHeader
      name={name}
      subtitle={`${todayText()}${name ? ` · ${name}` : ""}`}
      actions={
        <a href="#client-budget-panel" className="management-primary-action">
          <PiggyBank /> Budget
        </a>
      }
    />
  );

  if (loading && !summary) {
    return (
      <div className="dash-content production-dashboard">
        {header}
        <DashLoading />
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="dash-content production-dashboard">
        {header}
        <div className="organization-state">
          <h3>{error || "Your workspace is not available yet."}</h3>
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { currency, budget } = summary;
  const over = budget.has_budget && Number(budget.overage) > 0;
  const percent =
    budget.has_budget && Number(budget.total) > 0
      ? Math.min(999, Math.round((Number(budget.used) / Number(budget.total)) * 100))
      : 0;
  const thisMonth = summary.monthly[summary.monthly.length - 1];

  return (
    <div className="dash-content production-dashboard">
      {header}
      <div className="production-dash-body">
        <section className="company-dashboard-kpis" aria-label="Your summary">
          <Tile title="Delivered" value={String(summary.completed_items)} icon={<CheckCheck />}>
            {thisMonth ? `${thisMonth.items} this month` : "Approved work"}
          </Tile>
          <Tile title="In progress" value={String(summary.in_progress_items)} icon={<Hourglass />}>
            Being worked on now
          </Tile>
          <Tile
            title={over ? "Over budget" : "Budget left"}
            value={budget.has_budget ? money(over ? budget.overage : budget.remaining, currency) : "—"}
            icon={<PiggyBank />}
            tone={over ? "negative" : undefined}
          >
            {budget.has_budget ? `of ${money(budget.total, currency)} budget` : "No budget recorded yet"}
          </Tile>
          <Tile title="Pending payment" value={money(summary.pending_amount, currency)} icon={<Wallet />}>
            Billed {money(summary.total_charged, currency)} · paid {money(summary.total_paid, currency)}
          </Tile>
        </section>

        <section className="company-dashboard-grid production-dash-grid">
          <Panel>
            <PanelHead eyebrow="DELIVERED" title="Work per month" />
            <div className="production-dash-panel-body">
              <MonthBars
                label="Items delivered per month"
                points={summary.monthly.map((point) => ({
                  key: point.month.slice(0, 7),
                  value: point.items,
                  display: String(point.items),
                }))}
              />
              <p className="production-dash-footnote">
                Billed this month {money(summary.current_month_charged, currency)}
                {summary.services.some((service) => service.completed > 0)
                  ? ` · ${summary.services
                      .filter((service) => service.completed > 0)
                      .map((service) => `${service.service_name} ${service.completed}`)
                      .join(" · ")}`
                  : ""}
              </p>
            </div>
          </Panel>
          <div id="client-budget-panel" className="client-dash-anchor">
            <Panel>
              <PanelHead eyebrow="BUDGET" title={budget.has_budget ? money(budget.total, currency) : "No budget yet"} />
              <div className="production-dash-panel-body">
                {budget.has_budget ? (
                  <div className="client-budget-ring">
                    <BudgetRing percent={percent} over={over} />
                    <dl>
                      <div>
                        <dt>Used</dt>
                        <dd>{money(budget.used, currency)}</dd>
                      </div>
                      <div>
                        <dt>{over ? "Over by" : "Left"}</dt>
                        <dd className={over ? "client-portal-negative" : undefined}>
                          {money(over ? budget.overage : budget.remaining, currency)}
                        </dd>
                      </div>
                    </dl>
                  </div>
                ) : (
                  <p className="production-dash-empty">
                    <PiggyBank aria-hidden="true" />
                    Your agency will add your budget and top-ups here.
                  </p>
                )}
                {over ? (
                  <p className="client-dash-alert" role="status">
                    Approved work has gone {money(budget.overage, currency)} over your budget. Please contact your
                    agency to top it up.
                  </p>
                ) : budget.has_budget && percent >= 80 ? (
                  <p className="client-dash-note" role="status">
                    You have used most of your budget. Consider a top-up so work continues smoothly.
                  </p>
                ) : null}
              </div>
            </Panel>
          </div>
        </section>

        <section className="company-dashboard-grid production-dash-grid">
          <Panel>
            <PanelHead eyebrow="RECENT" title="Latest deliveries" />
            <div className="production-dash-panel-body">
              {summary.recent_deliveries.length === 0 ? (
                <p className="production-dash-empty">
                  <CheckCheck aria-hidden="true" />
                  Delivered work shows up here.
                </p>
              ) : (
                <ul className="production-dash-rows">
                  {summary.recent_deliveries.map((item, index) => (
                    <li key={`${item.delivered_on}-${index}`}>
                      <div className="client-dash-row">
                        <span>
                          <small>{item.service_name}</small>
                          <strong>{item.title}</strong>
                        </span>
                        <span className="meta">
                          <em>{money(item.amount, currency)}</em>
                          <small>{formatDate(item.delivered_on)}</small>
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
          <Panel>
            <PanelHead eyebrow="PAYMENTS" title={`Paid ${money(summary.total_paid, currency)}`} />
            <div className="production-dash-panel-body">
              {summary.payments.length === 0 ? (
                <p className="production-dash-empty">
                  <ReceiptText aria-hidden="true" />
                  Payments appear here once your agency records them.
                </p>
              ) : (
                <ul className="production-dash-rows">
                  {summary.payments.slice(0, 5).map((payment, index) => (
                    <li key={`${payment.received_on}-${index}`}>
                      <div className="client-dash-row">
                        <span>
                          <small>{METHOD_LABELS[payment.method] ?? payment.method}</small>
                          <strong>{money(payment.amount, currency)}</strong>
                        </span>
                        <span className="meta">
                          <em>{formatDate(payment.received_on)}</em>
                          <small>{payment.reference || "Payment received"}</small>
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </section>

        <section className="company-dashboard-grid production-dash-grid">
          <Panel>
            <PanelHead eyebrow="RATES" title="Your rates" />
            <div className="production-dash-panel-body">
              {rates.length === 0 ? (
                <p className="production-dash-empty">Your agency will add the price for each type of work.</p>
              ) : (
                <ul className="production-dash-rows">
                  {rates.map((item) => (
                    <li key={item.service_id}>
                      <div className="client-dash-row">
                        <span>
                          <small>{pricingLabel(item.current_rate?.pricing_model ?? item.default_pricing_model)}</small>
                          <strong>{item.service_name}</strong>
                        </span>
                        <span className="meta">
                          <em>{money(item.current_rate?.amount, item.current_rate?.currency ?? currency)}</em>
                          <small>{item.current_rate?.notes || "Current rate"}</small>
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
          <Panel>
            <PanelHead eyebrow="PROFILE" title={profile?.client.code ?? "Your account"} />
            <div className="production-dash-panel-body">
              <dl className="client-dash-facts">
                <div>
                  <dt>Workspace email</dt>
                  <dd>{profile?.client.account_email || profile?.client.email || "—"}</dd>
                </div>
                <div>
                  <dt>Phone</dt>
                  <dd>{profile?.client.phone || "—"}</dd>
                </div>
              </dl>
            </div>
          </Panel>
        </section>
      </div>
    </div>
  );
}
