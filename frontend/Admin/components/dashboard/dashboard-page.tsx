"use client";

import Link from "next/link";
import { TodayFocus } from "@loopless-shared/workspace/today-focus";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlarmClock,
  CircleDollarSign,
  HandCoins,
  PiggyBank,
  Plus,
  Table2,
  TrendingDown,
  TrendingUp,
  UsersRound,
  Wallet,
} from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { loadCompanyDashboard } from "@/lib/company-dashboard/client";
import type { CompanyDashboard } from "@/lib/company-dashboard/types";
import { MoneyPrivacy, PrivacyToggle, useMoneyPrivacy, usePrivateMoney } from "@loopless-shared/production/privacy";
import {
  STATUS_LABELS,
  api,
  errorText,
  formatDate,
  methodLabel,
  money as formatMoney,
  query,
} from "@/lib/production/client";
import type {
  ClientPayment,
  ManagerPayout,
  PaymentList,
  ReportPeriod,
  SalaryPayment,
  TaskStatus,
} from "@/lib/production/types";
import { PaymentsByDatePanel, monthRange, type DatedPayment } from "@loopless-shared/dashboard/payments-by-date";
import { STATUS_TEXT, ownerLine, type SheetsOverview } from "@/components/sheets/sheet-types";
import { useLiveRefresh } from "@loopless-shared/realtime/realtime";
import { AvailabilityPanel } from "@loopless-shared/chat/availability-panel";
import "@/styles/production.css";

// Password asked before the Admin dashboard shows money (owner request 2026-11-14; 3422 since
// 2026-11-28). Change it with
// NEXT_PUBLIC_MONEY_PASSWORD. Screen privacy only: the server already limits money to the Admin.
const MONEY_PASSWORD = process.env.NEXT_PUBLIC_MONEY_PASSWORD || "3422";

type Trend = { month: string; revenue: string; team_cost: string; margin: string };
type AdminDashboard = {
  period: { period: ReportPeriod; start: string | null; end: string | null };
  previous_period: { start: string | null; end: string | null } | null;
  currency: string;
  money: {
    revenue: string;
    previous_revenue: string | null;
    revenue_change_pct: number | null;
    team_cost: string;
    commission_cost: string;
    salary_cost: string;
    gross_margin: string;
    margin_pct: number | null;
    pending_client_payments: string;
    pending_team_payments: string;
    approved_items: number;
  };
  trend: Trend[];
  status_counts: Partial<Record<TaskStatus, number>>;
  open_tasks: number;
  overdue_tasks: number;
  due_this_week: number;
  attention: {
    id: string;
    code: string;
    title: string;
    client_name: string;
    assignee_name: string | null;
    due_date: string;
    status: TaskStatus;
    is_overdue: boolean;
  }[];
  team: {
    person: { id: string; name: string; role: "MANAGER" | "EMPLOYEE" };
    open_tasks: number;
    completed_tasks: number;
    pending: string;
  }[];
  budgets: {
    client: { id: string; name: string; code: string };
    total: string;
    used: string;
    committed: string;
    remaining: string;
    percent_used: number;
    over: boolean;
  }[];
  client_payments: {
    client: { id: string; name: string; code: string };
    billed: string;
    received: string;
    due: string;
    percent_paid: number;
    last_payment_on: string | null;
    unpaid_invoices: number;
    overdue_invoices: number;
  }[];
};

const PERIODS: { value: ReportPeriod; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "previous_month", label: "Previous month" },
  { value: "this_week", label: "This week" },
  { value: "today", label: "Today" },
  { value: "all", label: "All time" },
];
const WORKFLOW: TaskStatus[] = ["PENDING", "ASSIGNED", "IN_PROGRESS", "SUBMITTED", "REVIEW", "APPROVED", "COMPLETED"];

function greeting(): string {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

function compact(value: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return String(Math.round(value));
  }
}

function monthLabel(value: string, style: "short" | "long" = "short"): string {
  return new Intl.DateTimeFormat("en-IN", { month: style, ...(style === "long" ? { year: "numeric" } : {}) }).format(
    new Date(`${value}T00:00:00`),
  );
}

function Tile({
  title,
  value,
  icon,
  children,
  tone,
}: {
  title: string;
  value: string;
  icon: ReactNode;
  children: ReactNode;
  tone?: "negative";
}) {
  return (
    <article className="company-dashboard-kpi production-dash-tile">
      <div>
        <span>{title}</span>
        <i aria-hidden="true">{icon}</i>
      </div>
      <strong className={tone === "negative" ? "negative" : undefined}>{value}</strong>
      <small>{children}</small>
    </article>
  );
}

function PanelHead({ eyebrow, title, aside }: { eyebrow: string; title: string; aside?: ReactNode }) {
  return (
    <header>
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {aside}
    </header>
  );
}

export function DashboardPage() {
  const [company, setCompany] = useState<CompanyDashboard | null>(null);
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [period, setPeriod] = useState<ReportPeriod>("this_month");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [dashboard, overview] = await Promise.all([
        api<AdminDashboard>(`/api/company/finance/dashboard${query({ period })}`),
        loadCompanyDashboard().catch(() => null),
      ]);
      setData(dashboard);
      if (overview) setCompany(overview);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load the dashboard."));
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const firstName = company?.current_user.name.split(/\s+/)[0] ?? "";
  const todayText = new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long" }).format(
    new Date(),
  );

  return (
    <MoneyPrivacy password={MONEY_PASSWORD}>
      <div className="dash-content production-dashboard">
        <header className="production-dash-header">
          <div>
            <h1>
              {greeting()}
              {firstName ? `, ${firstName}` : ""}
            </h1>
            <p>
              {todayText}
              {company ? ` · ${company.company.name}` : ""}
            </p>
          </div>
          <div className="production-dash-actions">
            <PrivacyToggle />
            <LooplessSelect
              value={period}
              onValueChange={(value) => setPeriod(value as ReportPeriod)}
              ariaLabel="Dashboard period"
              options={PERIODS}
            />
            <Link href="/payments" className="management-secondary-action">
              <Wallet /> Record payment
            </Link>
            <Link href="/tasks?mode=create" className="management-primary-action">
              <Plus /> Create task
            </Link>
          </div>
        </header>

        {error ? (
          <div className="organization-state">
            <h3>{error}</h3>
            <button type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : !data ? (
          <div className="company-dashboard-loading" aria-busy="true" aria-label="Loading dashboard">
            <div className="company-dashboard-loading__cards">
              {[1, 2, 3, 4].map((item) => (
                <i key={item} />
              ))}
            </div>
            <div className="company-dashboard-loading__panels">
              <i />
              <i />
            </div>
          </div>
        ) : (
          <DashboardBody data={data} refreshing={loading} />
        )}
      </div>
    </MoneyPrivacy>
  );
}

function DashboardBody({ data, refreshing }: { data: AdminDashboard; refreshing: boolean }) {
  const money = usePrivateMoney(formatMoney);
  const { hidden } = useMoneyPrivacy();
  const { currency, money: m } = data;
  const change = m.revenue_change_pct;
  const marginNegative = Number(m.gross_margin) < 0;

  return (
    <div className={`production-dash-body${refreshing ? " refreshing" : ""}`}>
      <section className="company-dashboard-kpis" aria-label="Money summary">
        <Tile title="Revenue" value={money(m.revenue, currency)} icon={<CircleDollarSign />}>
          {change === null ? (
            `${m.approved_items} approved ${m.approved_items === 1 ? "item" : "items"}`
          ) : (
            <span className={`production-dash-delta ${change >= 0 ? "up" : "down"}`}>
              {change >= 0 ? <TrendingUp aria-hidden="true" /> : <TrendingDown aria-hidden="true" />}
              {change >= 0 ? "Up" : "Down"} {hidden ? "••" : Math.abs(change).toFixed(0)}% vs previous period
            </span>
          )}
        </Tile>
        <Tile title="Team cost" value={money(m.team_cost, currency)} icon={<HandCoins />}>
          Commission {money(m.commission_cost, currency)} · salaries {money(m.salary_cost, currency)}
        </Tile>
        <Tile
          title="Gross margin"
          value={money(m.gross_margin, currency)}
          icon={<TrendingUp />}
          tone={marginNegative ? "negative" : undefined}
        >
          {m.margin_pct === null
            ? "No revenue in this period"
            : `${hidden ? "••" : m.margin_pct.toFixed(0)}% of revenue`}
        </Tile>
        <Tile title="Pending from clients" value={money(m.pending_client_payments, currency)} icon={<Wallet />}>
          To your team: {money(m.pending_team_payments, currency)}
        </Tile>
      </section>

      <section className="company-dashboard-grid production-dash-grid">
        <TodayFocus endpoint="/api/company/tasks/focus" scope="ADMIN" />
      </section>

      <section className="company-dashboard-grid production-dash-grid">
        <TrendPanel trend={data.trend} currency={currency} />
        <StatusPanel data={data} />
      </section>

      <section className="company-dashboard-grid production-dash-grid">
        <AttentionPanel data={data} />
        <TeamPanel data={data} />
      </section>

      <AvailabilityPanel />

      <SheetAlertsPanel currency={data.currency} />
      <BudgetPanel data={data} />
      <ClientPaymentsPanel data={data} />
      <AdminPaymentsPanel currency={data.currency} />
    </div>
  );
}

/* ------------------------------------------------------------------ revenue vs cost */

function TrendPanel({ trend, currency }: { trend: Trend[]; currency: string }) {
  const money = usePrivateMoney(formatMoney);
  const axisMoney = usePrivateMoney(compact);
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  // Draw at the real pixel width so axis text stays 10px on phones instead of being scaled down.
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, Math.round(entry.contentRect.width))));
    observer.observe(element);
    return () => observer.disconnect();
  }, [asTable]);
  const values = trend.flatMap((point) => [Number(point.revenue), Number(point.team_cost)]);
  const max = Math.max(...values, 0);
  const empty = max === 0;

  // Chart geometry (SVG user units; the SVG scales to the panel width).
  const height = width < 480 ? 200 : 230;
  const pad = { top: 12, right: 8, bottom: 26, left: width < 480 ? 44 : 52 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const scaleMax = useMemo(() => {
    if (max <= 0) return 1;
    const magnitude = 10 ** Math.floor(Math.log10(max));
    return Math.ceil(max / magnitude) * magnitude;
  }, [max]);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((step) => step * scaleMax);
  const groupW = plotW / Math.max(trend.length, 1);
  const barW = Math.min(26, (groupW - 18) / 2);
  const y = (value: number) => pad.top + plotH - (value / scaleMax) * plotH;

  // Bar with 4px rounded top corners, square at the baseline.
  const bar = (x: number, value: number) => {
    const top = y(value);
    const h = pad.top + plotH - top;
    if (h <= 0) return "";
    const r = Math.min(4, h, barW / 2);
    return `M${x},${top + h} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${
      x + barW
    },${top + r} V${top + h} Z`;
  };

  const active = hover === null ? null : trend[hover];

  return (
    <article className="company-dashboard-panel production-dash-panel">
      <PanelHead
        eyebrow="LAST 6 MONTHS"
        title="Revenue vs team cost"
        aside={
          <div className="production-dash-legend">
            <span>
              <i className="revenue" aria-hidden="true" />
              Revenue
            </span>
            <span>
              <i className="cost" aria-hidden="true" />
              Team cost
            </span>
            <button
              type="button"
              className="production-icon-button"
              aria-pressed={asTable}
              aria-label={asTable ? "Show chart" : "Show as table"}
              title={asTable ? "Show chart" : "Show as table"}
              onClick={() => setAsTable(!asTable)}
            >
              <Table2 />
            </button>
          </div>
        }
      />
      <div className="production-dash-panel-body">
        {asTable ? (
          <table className="production-dash-table">
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col">Revenue</th>
                <th scope="col">Team cost</th>
                <th scope="col">Margin</th>
              </tr>
            </thead>
            <tbody>
              {trend.map((point) => (
                <tr key={point.month}>
                  <th scope="row">{monthLabel(point.month, "long")}</th>
                  <td>{money(point.revenue, currency)}</td>
                  <td>{money(point.team_cost, currency)}</td>
                  <td className={Number(point.margin) < 0 ? "negative" : undefined}>{money(point.margin, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : empty ? (
          <p className="production-dash-empty">No approved work or salaries in the last 6 months yet.</p>
        ) : (
          <div className="production-dash-chart" ref={box} onMouseLeave={() => setHover(null)}>
            <svg
              width={width}
              height={height}
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label="Revenue and team cost for the last 6 months"
            >
              {ticks.map((tick) => (
                <g key={tick}>
                  <line className="grid" x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} />
                  <text className="axis" x={pad.left - 8} y={y(tick) + 3} textAnchor="end">
                    {axisMoney(tick, currency)}
                  </text>
                </g>
              ))}
              {trend.map((point, index) => {
                const x0 = pad.left + index * groupW + (groupW - (barW * 2 + 2)) / 2;
                return (
                  <g key={point.month} className={hover !== null && hover !== index ? "dim" : undefined}>
                    <path className="revenue" d={bar(x0, Number(point.revenue))} />
                    <path className="cost" d={bar(x0 + barW + 2, Number(point.team_cost))} />
                    <text
                      className="axis"
                      x={pad.left + index * groupW + groupW / 2}
                      y={height - 8}
                      textAnchor="middle"
                    >
                      {monthLabel(point.month)}
                    </text>
                    <rect
                      className="hit"
                      x={pad.left + index * groupW}
                      y={pad.top}
                      width={groupW}
                      height={plotH}
                      onMouseEnter={() => setHover(index)}
                      onFocus={() => setHover(index)}
                      onBlur={() => setHover(null)}
                      tabIndex={0}
                      aria-label={`${monthLabel(point.month, "long")}: revenue ${money(point.revenue, currency)}, team cost ${money(
                        point.team_cost,
                        currency,
                      )}`}
                    />
                  </g>
                );
              })}
              <line className="baseline" x1={pad.left} x2={width - pad.right} y1={y(0)} y2={y(0)} />
            </svg>
            {active && hover !== null && (
              <div
                className="production-dash-tooltip"
                style={{ left: `${((pad.left + hover * groupW + groupW / 2) / width) * 100}%` }}
                role="status"
              >
                <b>{monthLabel(active.month, "long")}</b>
                <span>
                  <i className="revenue" aria-hidden="true" />
                  Revenue <strong>{money(active.revenue, currency)}</strong>
                </span>
                <span>
                  <i className="cost" aria-hidden="true" />
                  Team cost <strong>{money(active.team_cost, currency)}</strong>
                </span>
                <span>
                  Margin{" "}
                  <strong className={Number(active.margin) < 0 ? "negative" : undefined}>
                    {money(active.margin, currency)}
                  </strong>
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ work by status */

function StatusPanel({ data }: { data: AdminDashboard }) {
  const rows = WORKFLOW.map((status) => ({ status, count: data.status_counts[status] ?? 0 }));
  const max = Math.max(...rows.map((row) => row.count), 1);
  return (
    <article className="company-dashboard-panel production-dash-panel">
      <PanelHead eyebrow="WORK" title={`${data.open_tasks} open ${data.open_tasks === 1 ? "task" : "tasks"}`} />
      <div className="production-dash-panel-body">
        <ul className="production-dash-bars" aria-label="Tasks by status">
          {rows.map((row) => (
            <li key={row.status}>
              <Link href={`/tasks?status=${row.status}`}>
                <span>{STATUS_LABELS[row.status]}</span>
                <span className="track" aria-hidden="true">
                  {row.count > 0 && <i style={{ width: `${(row.count / max) * 100}%` }} />}
                </span>
                <b>{row.count}</b>
              </Link>
            </li>
          ))}
        </ul>
        <p className="production-dash-footnote">
          {data.overdue_tasks > 0 ? `${data.overdue_tasks} overdue · ` : ""}
          {data.due_this_week} due within 7 days
        </p>
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ needs attention */

function AttentionPanel({ data }: { data: AdminDashboard }) {
  return (
    <article className="company-dashboard-panel production-dash-panel">
      <PanelHead
        eyebrow="NEEDS ATTENTION"
        title="Overdue and due this week"
        aside={
          <Link href="/tasks" className="production-dash-link">
            All tasks
          </Link>
        }
      />
      <div className="production-dash-panel-body">
        {data.attention.length === 0 ? (
          <p className="production-dash-empty">
            <AlarmClock aria-hidden="true" />
            Nothing overdue or due in the next 7 days.
          </p>
        ) : (
          <ul className="production-dash-rows">
            {data.attention.map((task) => (
              <li key={task.id}>
                <Link href={`/tasks?task=${task.id}`}>
                  <span>
                    <small>
                      {task.code} · {task.client_name}
                    </small>
                    <strong>{task.title}</strong>
                  </span>
                  <span className="meta">
                    <em className={task.is_overdue ? "overdue" : undefined}>
                      {task.is_overdue ? "Overdue" : "Due"} {formatDate(task.due_date)}
                    </em>
                    <small>
                      {STATUS_LABELS[task.status]} · {task.assignee_name ?? "Not assigned"}
                    </small>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ team workload */

function TeamPanel({ data }: { data: AdminDashboard }) {
  const money = usePrivateMoney(formatMoney);
  const max = Math.max(...data.team.map((row) => row.open_tasks), 1);
  return (
    <article className="company-dashboard-panel production-dash-panel">
      <PanelHead
        eyebrow="TEAM"
        title="Workload"
        aside={
          <Link href="/payments" className="production-dash-link">
            Payouts
          </Link>
        }
      />
      <div className="production-dash-panel-body">
        {data.team.length === 0 ? (
          <p className="production-dash-empty">
            <UsersRound aria-hidden="true" />
            No managers or employees yet.
          </p>
        ) : (
          <ul className="production-dash-team">
            {data.team.map((row) => (
              <li key={row.person.id}>
                <b aria-hidden="true">
                  {row.person.name
                    .split(/\s+/)
                    .slice(0, 2)
                    .map((part) => part[0])
                    .join("")
                    .toUpperCase()}
                </b>
                <span>
                  <strong>{row.person.name}</strong>
                  <small>
                    {row.person.role === "MANAGER" ? "Manager" : "Employee"} · {row.open_tasks} open ·{" "}
                    {Number(row.pending) > 0 ? `${money(row.pending, data.currency)} to pay` : "nothing to pay"}
                  </small>
                  <span className="track" aria-hidden="true">
                    {row.open_tasks > 0 && <i style={{ width: `${(row.open_tasks / max) * 100}%` }} />}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ budgets */

function BudgetPanel({ data }: { data: AdminDashboard }) {
  const money = usePrivateMoney(formatMoney);
  return (
    <article className="company-dashboard-panel production-dash-panel production-dash-budgets">
      <PanelHead
        eyebrow="CLIENT BUDGETS"
        title="Budget watch"
        aside={
          <Link href="/payments" className="production-dash-link">
            Manage budgets
          </Link>
        }
      />
      <div className="production-dash-panel-body">
        {data.budgets.length === 0 ? (
          <p className="production-dash-empty">
            <PiggyBank aria-hidden="true" />
            No client budgets set. Add them in Payments → Budgets.
          </p>
        ) : (
          <ul className="production-dash-meters">
            {data.budgets.map((row) => {
              const pct = Math.min(row.percent_used, 100);
              const near = !row.over && row.percent_used >= 80;
              return (
                <li key={row.client.id}>
                  <div>
                    <strong>{row.client.name}</strong>
                    <span className={row.over ? "over" : undefined}>
                      {row.over ? "Over budget" : near ? "Near limit" : `${row.percent_used.toFixed(0)}% used`}
                    </span>
                  </div>
                  <span
                    className={`meter${row.over ? " over" : ""}`}
                    role="meter"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round(row.percent_used)}
                    aria-label={`${row.client.name} budget used`}
                  >
                    <i style={{ width: `${pct}%` }} />
                  </span>
                  <small>
                    {money(row.used, data.currency)} of {money(row.total, data.currency)}
                    {Number(row.committed) > 0 ? ` · ${money(row.committed, data.currency)} in progress` : ""}
                  </small>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ client payments */

function ClientPaymentsPanel({ data }: { data: AdminDashboard }) {
  const money = usePrivateMoney(formatMoney);
  const rows = data.client_payments;
  const totalDue = rows.reduce((sum, row) => sum + Number(row.due), 0);
  return (
    <article className="company-dashboard-panel production-dash-panel production-dash-budgets">
      <PanelHead
        eyebrow="CLIENT PAYMENTS"
        title={totalDue > 0 ? `${money(totalDue, data.currency)} to collect` : "All clients paid up"}
        aside={
          <Link href="/payments" className="production-dash-link">
            Record payment
          </Link>
        }
      />
      <div className="production-dash-panel-body">
        {rows.length === 0 ? (
          <p className="production-dash-empty">
            <Wallet aria-hidden="true" />
            Nothing billed yet. Approved work shows up here.
          </p>
        ) : (
          <ul className="production-dash-meters">
            {rows.map((row) => {
              const due = Number(row.due) > 0;
              const late = row.overdue_invoices > 0;
              return (
                <li key={row.client.id}>
                  <div>
                    <strong>{row.client.name}</strong>
                    <span className={late ? "over" : due ? undefined : "paid"}>
                      {due ? `${money(row.due, data.currency)} due` : "Paid up"}
                    </span>
                  </div>
                  <span
                    className={`meter${due ? (late ? " over" : "") : " paid"}`}
                    role="meter"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round(row.percent_paid)}
                    aria-label={`${row.client.name} paid`}
                  >
                    <i style={{ width: `${Math.min(row.percent_paid, 100)}%` }} />
                  </span>
                  <small>
                    Paid {money(row.received, data.currency)} of {money(row.billed, data.currency)}
                    {row.last_payment_on ? ` · last on ${formatDate(row.last_payment_on)}` : " · no payment yet"}
                    {late
                      ? ` · ${row.overdue_invoices} ${row.overdue_invoices === 1 ? "invoice" : "invoices"} overdue`
                      : row.unpaid_invoices > 0
                        ? ` · ${row.unpaid_invoices} ${row.unpaid_invoices === 1 ? "invoice" : "invoices"} sent`
                        : ""}
                  </small>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ payments by date */

/** Every payment of a month, day by day (owner request 2026-11-28): client payments in,
 * salaries and manager top-ups out. */
function AdminPaymentsPanel({ currency }: { currency: string }) {
  const money = usePrivateMoney(formatMoney);
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [rows, setRows] = useState<DatedPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const range = query({ ...monthRange(month), page_size: 100 });
    try {
      const [received, salaries, payouts] = await Promise.all([
        api<PaymentList<ClientPayment>>(`/api/company/finance/client-payments${range}`),
        api<PaymentList<SalaryPayment>>(`/api/company/finance/salary-payments${range}`),
        api<PaymentList<ManagerPayout>>(`/api/company/finance/manager-payouts${range}`),
      ]);
      const note = (method: ClientPayment["method"], reference: string) =>
        `${methodLabel(method)}${reference ? ` · ${reference}` : ""}`;
      setRows([
        ...received.items.map((item) => ({
          id: `c-${item.id}`,
          day: item.received_on,
          title: item.client.name,
          detail: `Client payment · ${note(item.method, item.reference)}`,
          amount: Number(item.amount),
          direction: "IN" as const,
        })),
        ...salaries.items.map((item) => ({
          id: `s-${item.id}`,
          day: item.paid_on,
          title: item.employee_name,
          detail: `Salary for ${new Intl.DateTimeFormat("en-IN", { month: "short", year: "numeric" }).format(
            new Date(`${item.period_month.slice(0, 10)}T00:00:00`),
          )} · ${note(item.method, item.reference)}`,
          amount: Number(item.amount),
          direction: "OUT" as const,
        })),
        ...payouts.items.map((item) => ({
          id: `p-${item.id}`,
          day: item.paid_on,
          title: item.manager_name,
          detail: `Manager top-up · ${note(item.method, item.reference)}`,
          amount: Number(item.amount),
          direction: "OUT" as const,
        })),
      ]);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load payments."));
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <PaymentsByDatePanel
      rows={rows}
      month={month}
      onMonth={setMonth}
      money={(amount) => money(amount, currency)}
      loading={loading}
      error={error}
      inLabel="Received from clients"
      outLabel="Paid to the team"
    />
  );
}

/* ------------------------------------------------------------------ payment sheets */

/** Managers and clients whose current payment sheet is running low or used up (2026-11-14). */
function SheetAlertsPanel({ currency }: { currency: string }) {
  const money = usePrivateMoney(formatMoney);
  const [data, setData] = useState<SheetsOverview | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api<SheetsOverview>("/api/company/finance/sheets"));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useLiveRefresh(["task.", "payout.", "budget."], () => void load());

  if (failed || !data) return null;
  const owners = [...data.managers, ...data.clients];
  const alerts = owners.filter((owner) => owner.status !== "OK");
  return (
    <article className="company-dashboard-panel production-dash-panel production-dash-budgets">
      <PanelHead
        eyebrow="PAYMENT SHEETS"
        title={
          alerts.length === 0
            ? owners.length
              ? "Everyone has money left"
              : "No sheets yet"
            : `${alerts.length} ${alerts.length === 1 ? "needs" : "need"} a top-up soon`
        }
        aside={
          <Link href="/sheets" className="production-dash-link">
            All sheets
          </Link>
        }
      />
      <div className="production-dash-panel-body">
        {alerts.length === 0 ? (
          <p className="production-dash-empty">
            <PiggyBank aria-hidden="true" />
            {owners.length
              ? `${owners.length} open ${owners.length === 1 ? "sheet" : "sheets"}, none running low.`
              : "A sheet opens when you send a manager top-up or add a client budget."}
          </p>
        ) : (
          <ul className="production-dash-meters">
            {alerts.map((owner) => {
              const tone = owner.status === "NEAR" ? "near" : "over";
              return (
                <li key={`${owner.kind}-${owner.id}`}>
                  <div>
                    <strong>
                      <Link
                        href={`/sheets?tab=${owner.kind === "CLIENT" ? "clients" : "managers"}&owner=${owner.id}`}
                        className="production-dash-sheet-link"
                      >
                        {owner.name}
                      </Link>
                    </strong>
                    <span className={tone}>
                      {owner.kind === "MANAGER" ? "Manager" : "Client"} · {STATUS_TEXT[owner.status]}
                    </span>
                  </div>
                  <span
                    className={`meter ${tone}`}
                    role="meter"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round(owner.percent_used)}
                    aria-label={`${owner.name} sheet used`}
                  >
                    <i style={{ width: `${Math.min(owner.percent_used, 100)}%` }} />
                  </span>
                  <small>
                    Sheet {owner.sheets.length} · {ownerLine(owner, money, currency)}
                    {owner.ran_out_on ? ` · ran out ${formatDate(owner.ran_out_on)}` : ""}
                  </small>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </article>
  );
}
