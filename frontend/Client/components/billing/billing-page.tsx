"use client";

/*
 * Client Billing (Phase 11, owner request 2026-11-14): budget periods, every delivered video with
 * the budget left after it (like the owner's sheets), a day picker, daily summary, payments and
 * invoices. Data: GET /client-portal/billing (own client only; no internal costs or people).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, CheckCheck, Download, PiggyBank, ReceiptText, Search, Wallet } from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { DashLoading, MonthBars, Panel, PanelHead, Tile } from "@/components/dashboard/role-dashboard-ui";
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
  }[];
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

function money(amount: string | number | null | undefined, currency = "INR") {
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

function localToday(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function shiftDay(value: string, delta: number): string {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + delta);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function BillingPage() {
  const [data, setData] = useState<Billing | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState("");
  const [selectedDay, setSelectedDay] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const response = await fetch("/api/client/billing", { cache: "no-store" });
      const body = (await response.json().catch(() => ({}))) as Billing & { detail?: string };
      if (!response.ok) throw new Error(body.detail || "Unable to load billing.");
      setData(body);
      setSelectedDay((current) => current || body.days[0]?.day || localToday());
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

  const last14 = useMemo(() => {
    const end = localToday();
    return Array.from({ length: 14 }, (_, index) => shiftDay(end, index - 13));
  }, []);

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
    budget.has_budget && Number(budget.total) > 0 ? Math.round((Number(budget.used) / Number(budget.total)) * 100) : 0;
  const dayItems = data.deliveries.filter((row) => row.delivered_on === selectedDay);
  const daySummary = data.days.find((item) => item.day === selectedDay);
  const dayAmounts = new Map(data.days.map((item) => [item.day, Number(item.amount)]));

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
    link.download = `work-delivered${cycle ? `-period-${cycle.index}` : ""}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <div className="dash-content production-dashboard">
      <BillingHeader
        subtitle={`${data.client_name} · billed this month ${money(data.current_month_charged, currency)}`}
      />
      <div className="production-dash-body">
        <section className="company-dashboard-kpis" aria-label="Billing summary">
          <Tile title="Budget" value={budget.has_budget ? money(budget.total, currency) : "—"} icon={<PiggyBank />}>
            {data.cycles.length
              ? `${data.cycles.length} budget ${data.cycles.length === 1 ? "period" : "periods"}`
              : "No budget recorded yet"}
          </Tile>
          <Tile title="Used" value={money(budget.used, currency)} icon={<CheckCheck />}>
            {budget.has_budget ? `${percent}% of your budget` : `${data.deliveries.length} items delivered`}
          </Tile>
          <Tile
            title={over ? "Over budget" : "Budget left"}
            value={budget.has_budget ? money(over ? budget.overage : budget.remaining, currency) : "—"}
            icon={<Wallet />}
            tone={over ? "negative" : undefined}
          >
            {over ? "Please top up with your agency" : "Available for new work"}
          </Tile>
          <Tile title="Pending payment" value={money(data.pending_amount, currency)} icon={<ReceiptText />}>
            Billed {money(data.total_charged, currency)} · paid {money(data.total_paid, currency)}
          </Tile>
        </section>

        <section className="company-dashboard-grid production-dash-grid">
          <Panel>
            <PanelHead eyebrow="LAST 14 DAYS" title="Work billed per day" />
            <div className="production-dash-panel-body">
              <MonthBars
                label="Amount billed per day for the last 14 days"
                emptyText="No work delivered in the last 14 days."
                axisLabel={(key) => String(Number(key.slice(8, 10)))}
                points={last14.map((key) => {
                  const value = dayAmounts.get(key) ?? 0;
                  return {
                    key,
                    value,
                    display: value
                      ? new Intl.NumberFormat("en-IN", {
                          style: "currency",
                          currency,
                          notation: "compact",
                          maximumFractionDigits: 1,
                        }).format(value)
                      : "",
                  };
                })}
              />
            </div>
          </Panel>
          <Panel>
            <PanelHead eyebrow="BUDGET PERIODS" title={data.cycles.length ? "One per top-up" : "No budget yet"} />
            <div className="production-dash-panel-body">
              {data.cycles.length === 0 ? (
                <p className="production-dash-empty">
                  <PiggyBank aria-hidden="true" />
                  Your agency will add your budget and top-ups here.
                </p>
              ) : (
                <ul className="billing-cycles">
                  {[...data.cycles].reverse().map((item) => {
                    const used =
                      Number(item.amount) > 0 ? Math.min(100, (Number(item.used) / Number(item.amount)) * 100) : 0;
                    const full = Number(item.remaining) <= 0;
                    return (
                      <li key={item.index}>
                        <span className="billing-cycle-top">
                          <strong>Period {item.index}</strong>
                          <small>
                            {day(item.start, false)} – {item.end ? day(item.end, false) : "now"}
                          </small>
                        </span>
                        <span className="billing-bar" aria-hidden="true">
                          <i style={{ width: `${used}%` }} className={full ? "full" : undefined} />
                        </span>
                        <span className="billing-cycle-meta">
                          {money(item.used, currency)} of {money(item.amount, currency)} · {item.items}{" "}
                          {item.items === 1 ? "item" : "items"}
                          <b className={full ? "full" : undefined}>
                            {full
                              ? Number(item.remaining) < 0
                                ? `Over by ${money(-Number(item.remaining), currency)}`
                                : "Used up"
                              : `${money(item.remaining, currency)} left`}
                          </b>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </Panel>
        </section>

        <section className="company-dashboard-grid production-dash-grid">
          <Panel>
            <PanelHead
              eyebrow="SELECTED DAY"
              title={selectedDay ? day(selectedDay) : "Pick a day"}
              aside={
                <span className="billing-day-picker">
                  <CalendarDays aria-hidden="true" />
                  <input
                    type="date"
                    value={selectedDay}
                    max={localToday()}
                    onChange={(event) => setSelectedDay(event.target.value)}
                    aria-label="Selected day"
                  />
                </span>
              }
            />
            <div className="production-dash-panel-body">
              {dayItems.length === 0 ? (
                <p className="production-dash-empty">
                  <CalendarDays aria-hidden="true" />
                  No work delivered on this day.
                </p>
              ) : (
                <>
                  <ul className="production-dash-rows">
                    {dayItems.map((row, index) => (
                      <li key={`${row.title}-${index}`}>
                        <div className="client-dash-row">
                          <span>
                            <small>{row.service_name}</small>
                            <strong>{row.title}</strong>
                          </span>
                          <span className="meta">
                            <em>{money(row.amount, currency)}</em>
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                  {daySummary && (
                    <p className="production-dash-footnote">
                      {daySummary.items} {daySummary.items === 1 ? "item" : "items"} ·{" "}
                      {money(daySummary.amount, currency)} · budget left after this day{" "}
                      {money(daySummary.budget_left, currency)}
                    </p>
                  )}
                </>
              )}
            </div>
          </Panel>
          <Panel>
            <PanelHead eyebrow="RECENT DAYS" title="Day by day" />
            <div className="production-dash-panel-body">
              {data.days.length === 0 ? (
                <p className="production-dash-empty">Delivered work shows up here.</p>
              ) : (
                <table className="billing-table compact">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th className="num">Items</th>
                      <th className="num">Amount</th>
                      <th className="num">Budget left</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.days.slice(0, 8).map((item) => (
                      <tr
                        key={item.day}
                        className={item.day === selectedDay ? "selected" : undefined}
                        onClick={() => setSelectedDay(item.day)}
                      >
                        <td className="nowrap">{day(item.day, false)}</td>
                        <td className="num">{item.items}</td>
                        <td className="num">{money(item.amount, currency)}</td>
                        <td className={`num${Number(item.budget_left) < 0 ? " negative" : ""}`}>
                          {money(item.budget_left, currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Panel>
        </section>

        <Panel>
          <PanelHead
            eyebrow="DELIVERED WORK"
            title={`${rows.length} ${rows.length === 1 ? "item" : "items"} · ${money(
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
                ariaLabel="Budget period"
                options={[
                  { value: "", label: "All periods" },
                  ...data.cycles.map((item) => ({
                    value: String(item.index),
                    label: `Period ${item.index} · ${day(item.start, false)} – ${item.end ? day(item.end, false) : "now"}`,
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
                        <td>{day(row.delivered_on)}</td>
                        <td className="strong">{row.title}</td>
                        <td>{row.service_name}</td>
                        <td className="num">{money(row.amount, currency)}</td>
                        <td className={`num${Number(row.budget_left) < 0 ? " negative" : ""}`}>
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

        <section className="company-dashboard-grid production-dash-grid">
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
                            {invoice.items === 1 ? "item" : "items"}
                          </small>
                          <strong>
                            {invoice.code} · {money(invoice.subtotal, currency)}
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
