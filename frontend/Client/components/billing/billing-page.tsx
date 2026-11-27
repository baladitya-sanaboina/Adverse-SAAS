"use client";

/*
 * Client Billing (Phase 11, simplified on owner request 2026-11-14): one card with the budget left
 * and the sum behind it (added − used = left), the eye right next to the amount, then top-ups,
 * every delivered video with the budget left after it (like the owner's sheets), invoices and
 * payments. Data: GET /client-portal/billing (own client only; no internal costs or people).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCheck, Download, ReceiptText, Search, Wallet } from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { DashLoading, Panel, PanelHead } from "@/components/dashboard/role-dashboard-ui";
import { PaymentSheets, type Sheet, type SheetLine } from "@/lib/payment-sheets";
import "@/styles/client-portal.css";
import "@/styles/billing.css";

type PaymentMethod = "CASH" | "BANK_TRANSFER" | "UPI" | "CHEQUE" | "CARD" | "OTHER";
type Billing = {
  client_name: string;
  currency: string;
  budget: { has_budget: boolean; total: string; used: string; remaining: string; overage: string };
  total_charged: string;
  total_paid: string;
  pending_amount: string;
  current_month_charged: string;
  cycles: {
    index: number;
    start: string;
    end: string | null;
    amount: string;
    used: string;
    remaining: string;
    items: number;
    carried_in: string;
    ran_out_on: string | null;
    lines: SheetLine[];
  }[];
  sheets: Sheet[];
  deliveries: { delivered_on: string; title: string; service_name: string; amount: string; budget_left: string }[];
  days: { day: string; items: number; amount: string; budget_left: string }[];
  payments: { amount: string; received_on: string; method: PaymentMethod; reference: string }[];
  invoices: {
    id: string;
    code: string;
    status: "SENT" | "PAID";
    period_start: string;
    period_end: string;
    issue_date: string;
    subtotal: string;
    tax_amount?: string;
    total?: string;
    payments_total: string;
    balance: string;
    items: number;
  }[];
};

const METHOD_LABELS: Record<PaymentMethod, string> = {
  BANK_TRANSFER: "Bank transfer",
  UPI: "UPI",
  CASH: "Cash",
  CHEQUE: "Cheque",
  CARD: "Card",
  OTHER: "Other",
};

function formatMoney(amount: string | number | null | undefined, currency = "INR") {
  const value = amount == null ? Number.NaN : Number(amount);
  if (!Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
}

function day(value: string, withYear = true) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    ...(withYear ? { year: "numeric" } : {}),
  }).format(new Date(`${value}T00:00:00`));
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

// Amounts are always shown to the client (owner request 2026-11-28: no show/hide).
export function BillingPage() {
  const money = formatMoney;
  const [data, setData] = useState<Billing | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const response = await fetch("/api/client/billing", { cache: "no-store" });
      const body = (await response.json().catch(() => ({}))) as Billing & { detail?: string };
      if (!response.ok) throw new Error(body.detail || "Unable to load billing.");
      setData(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load billing.");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const cycle = data?.cycles.find((item) => String(item.index) === period) ?? null;
  const rows = useMemo(() => {
    if (!data) return [];
    const needle = search.trim().toLowerCase();
    return data.deliveries.filter((row) => {
      if (cycle && (row.delivered_on < cycle.start || (cycle.end && row.delivered_on > cycle.end))) return false;
      if (!needle) return true;
      return `${row.title} ${row.service_name}`.toLowerCase().includes(needle);
    });
  }, [data, search, cycle]);

  if (!data) {
    return (
      <div className="dash-content production-dashboard">
        <BillingHeader />
        {error ? (
          <div className="organization-state">
            <h3>{error}</h3>
            <button type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : (
          <DashLoading />
        )}
      </div>
    );
  }

  const { currency, budget } = data;
  const over = budget.has_budget && Number(budget.overage) > 0;
  const percent =
    budget.has_budget && Number(budget.total) > 0
      ? Math.min(100, Math.round((Number(budget.used) / Number(budget.total)) * 100))
      : 0;
  const pending = Number(data.pending_amount) > 0;

  function downloadCsv() {
    const header = ["Date", "Work", "Service", "Amount", "Budget left"];
    const lines = [...rows]
      .reverse()
      .map((row) =>
        [row.delivered_on, row.title, row.service_name, row.amount, row.budget_left].map(csvCell).join(","),
      );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `work-delivered${cycle ? `-top-up-${cycle.index}` : ""}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <div className="dash-content production-dashboard">
      <BillingHeader subtitle={data.client_name} />
      <div className="production-dash-body">
        <section className="billing-balance" aria-label="Budget">
          <div className="billing-balance-main">
            <span className="billing-balance-label">
              {!budget.has_budget ? "Payment due" : over ? "Over budget by" : "Available budget"}
            </span>
            <span className="billing-balance-amount">
              <strong className={over ? "negative" : undefined}>
                {budget.has_budget
                  ? money(over ? budget.overage : budget.remaining, currency)
                  : money(data.pending_amount, currency)}
              </strong>
            </span>
            {!budget.has_budget && (
              <small>
                {data.deliveries.length} {data.deliveries.length === 1 ? "video" : "videos"} delivered · no budget added
                yet
              </small>
            )}
            {budget.has_budget && (
              <>
                <span className="billing-bar" aria-hidden="true">
                  <i style={{ width: `${percent}%` }} className={over || percent >= 100 ? "full" : undefined} />
                </span>
                <small>
                  {percent}% of your budget used
                  {over ? " · please top up with your agency" : ""}
                </small>
              </>
            )}
          </div>
          {budget.has_budget && (
            <dl className="billing-sum" aria-label="How the budget left is worked out">
              <div>
                <dt>Added</dt>
                <dd>{money(budget.total, currency)}</dd>
                <small>
                  {data.cycles.length} {data.cycles.length === 1 ? "top-up" : "top-ups"}
                </small>
              </div>
              <span aria-hidden="true">−</span>
              <div>
                <dt>Used</dt>
                <dd>{money(budget.used, currency)}</dd>
                <small>
                  {data.deliveries.length} {data.deliveries.length === 1 ? "video" : "videos"} delivered
                </small>
              </div>
              <span aria-hidden="true">=</span>
              <div className={over ? "negative" : "left"}>
                <dt>{over ? "Over" : "Left"}</dt>
                <dd>{money(over ? -Number(budget.overage) : budget.remaining, currency)}</dd>
                <small>{over ? "Top up to continue" : "For new work"}</small>
              </div>
            </dl>
          )}
          <p className="billing-pay-line">
            <ReceiptText aria-hidden="true" />
            {pending ? (
              <>
                Payment due <b>{money(data.pending_amount, currency)}</b>
              </>
            ) : (
              <>All paid</>
            )}
            <span>
              · billed {money(data.total_charged, currency)} · paid {money(data.total_paid, currency)}
            </span>
          </p>
        </section>

        <section className="company-dashboard-grid production-dash-grid">
          <Panel>
            <PanelHead
              eyebrow="PAYMENT SHEETS"
              title={data.sheets.length ? "Each payment opens a new sheet" : "No payments yet"}
            />
            <div className="production-dash-panel-body">
              <PaymentSheets
                sheets={data.sheets}
                currency={currency}
                money={money}
                date={(value) => day(value, false)}
                itemWord="video"
                empty="Each payment you make to your agency opens a new sheet here."
              />
            </div>
          </Panel>
          <Panel>
            <PanelHead eyebrow="PAYMENTS" title={`Paid ${money(data.total_paid, currency)}`} />
            <div className="production-dash-panel-body">
              {data.payments.length === 0 ? (
                <p className="production-dash-empty">
                  <Wallet aria-hidden="true" />
                  Payments appear here once your agency records them.
                </p>
              ) : (
                <ul className="production-dash-rows">
                  {data.payments.map((payment, index) => (
                    <li key={`${payment.received_on}-${index}`}>
                      <div className="client-dash-row">
                        <span>
                          <small>{METHOD_LABELS[payment.method] ?? payment.method}</small>
                          <strong>{money(payment.amount, currency)}</strong>
                        </span>
                        <span className="meta">
                          <em>{day(payment.received_on)}</em>
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

        <Panel>
          <PanelHead
            eyebrow="DELIVERED WORK"
            title={`${rows.length} ${rows.length === 1 ? "video" : "videos"} · ${money(
              rows.reduce((sum, row) => sum + Number(row.amount), 0),
              currency,
            )}`}
            aside={
              <button type="button" className="billing-link" onClick={downloadCsv} disabled={rows.length === 0}>
                <Download aria-hidden="true" /> CSV
              </button>
            }
          />
          <div className="production-dash-panel-body">
            <div className="billing-tools">
              <label className="billing-search">
                <Search aria-hidden="true" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search work or service"
                  aria-label="Search delivered work"
                />
              </label>
              <LooplessSelect
                value={period}
                onValueChange={setPeriod}
                ariaLabel="Top-up"
                options={[
                  { value: "", label: "All top-ups" },
                  ...data.cycles.map((item) => ({
                    value: String(item.index),
                    label: `Top-up ${item.index} · ${day(item.start, false)} – ${item.end ? day(item.end, false) : "now"}`,
                  })),
                ]}
              />
            </div>
            {rows.length === 0 ? (
              <p className="production-dash-empty">
                <CheckCheck aria-hidden="true" />
                {search || period ? "Nothing matches these filters." : "Delivered work shows up here."}
              </p>
            ) : (
              <div className="billing-table-wrap">
                <table className="billing-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Work</th>
                      <th>Service</th>
                      <th className="num">Amount</th>
                      <th className="num">Budget left</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => (
                      <tr key={`${row.delivered_on}-${index}`}>
                        <td className="nowrap">{day(row.delivered_on)}</td>
                        <td className="strong">{row.title}</td>
                        <td>{row.service_name}</td>
                        <td className="num">− {money(row.amount, currency)}</td>
                        <td className={`num${budget.has_budget && Number(row.budget_left) < 0 ? " negative" : ""}`}>
                          {budget.has_budget ? money(row.budget_left, currency) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Panel>

        <Panel>
          <PanelHead
            eyebrow="INVOICES"
            title={
              data.invoices.length
                ? `${data.invoices.length} ${data.invoices.length === 1 ? "invoice" : "invoices"}`
                : "No invoices yet"
            }
          />
          <div className="production-dash-panel-body">
            {data.invoices.length === 0 ? (
              <p className="production-dash-empty">
                <ReceiptText aria-hidden="true" />
                Invoices from your agency appear here.
              </p>
            ) : (
              <ul className="production-dash-rows">
                {data.invoices.map((invoice) => (
                  <li key={invoice.id}>
                    <div className="client-dash-row">
                      <span>
                        <small>
                          {day(invoice.period_start, false)} – {day(invoice.period_end)} · {invoice.items}{" "}
                          {invoice.items === 1 ? "video" : "videos"}
                        </small>
                        <strong>
                          {invoice.code} · {money(invoice.total ?? invoice.subtotal, currency)}
                          {Number(invoice.tax_amount ?? 0) > 0 ? " incl. GST" : ""}
                        </strong>
                      </span>
                      <span className="meta billing-invoice-meta">
                        <em className={invoice.status === "PAID" ? "paid" : undefined}>
                          {invoice.status === "PAID" ? "Paid" : Number(invoice.balance) > 0 ? "Due" : "Settled"}
                        </em>
                        <a href={`/api/client/invoices/${invoice.id}/pdf?download=true`} className="billing-link">
                          <Download aria-hidden="true" /> PDF
                        </a>
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function BillingHeader({ subtitle = "Your budget, delivered work, payments and invoices" }: { subtitle?: string }) {
  return (
    <header className="production-dash-header">
      <div>
        <h1>Billing</h1>
        <p>{subtitle}</p>
      </div>
    </header>
  );
}
