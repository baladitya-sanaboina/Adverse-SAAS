"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { BriefcaseBusiness, Contact, UsersRound } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { LooplessDate } from "@/components/foundation/loopless-date";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { TableSkeleton } from "@/components/production/production-ui";
import { PERIOD_OPTIONS, api, errorText, formatDate, money, query, today } from "@/lib/production/client";
import type {
  ClientReportRow,
  FinanceSummary,
  Report,
  ReportPeriod,
  ServiceReport,
  TeamReportRow,
} from "@/lib/production/types";
import "@/styles/organization.css";
import "@/styles/service-pricing-settings.css";
import "@/styles/production.css";

type Tab = "clients" | "team" | "services";
const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: "clients", label: "Clients", icon: <Contact /> },
  { id: "team", label: "Team", icon: <UsersRound /> },
  { id: "services", label: "Services", icon: <BriefcaseBusiness /> },
];

export function ReportsPage() {
  const [period, setPeriod] = useState<ReportPeriod>("this_month");
  const [start, setStart] = useState(`${today().slice(0, 7)}-01`);
  const [end, setEnd] = useState(today());
  const [tab, setTab] = useState<Tab>("clients");
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [clients, setClients] = useState<Report<ClientReportRow> | null>(null);
  const [team, setTeam] = useState<Report<TeamReportRow> | null>(null);
  const [services, setServices] = useState<ServiceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const custom = period === "custom";
  const range = query({ period, start: custom ? start : null, end: custom ? end : null });

  const load = useCallback(async () => {
    if (custom && (!start || !end)) return;
    setLoading(true);
    setError("");
    try {
      const [summaryData, clientData, teamData, serviceData] = await Promise.all([
        api<FinanceSummary>(`/api/company/finance/summary${range}`),
        api<Report<ClientReportRow>>(`/api/company/finance/reports/clients${range}`),
        api<Report<TeamReportRow>>(`/api/company/finance/reports/team${range}`),
        api<ServiceReport>(`/api/company/finance/reports/services${range}`),
      ]);
      setSummary(summaryData);
      setClients(clientData);
      setTeam(teamData);
      setServices(serviceData);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load reports."));
    } finally {
      setLoading(false);
    }
  }, [range, custom, start, end]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  const currency = summary?.currency ?? "INR";
  const periodText = summary?.period.start
    ? summary.period.start === summary.period.end
      ? formatDate(summary.period.start)
      : `${formatDate(summary.period.start)} – ${formatDate(summary.period.end)}`
    : "All time";

  return (
    <>
      <DashboardHero
        title=""
        highlight="Reports"
        description="Revenue, team cost, margin and pending money, by client, team member and service."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace" aria-live="polite">
          <header className="management-toolbar">
            <div>
              <span>Reporting period</span>
              <strong>{periodText}</strong>
            </div>
          </header>
          <div className="organization-tools production-period">
            <LooplessSelect
              value={period}
              onValueChange={(value) => setPeriod(value as ReportPeriod)}
              ariaLabel="Reporting period"
              options={PERIOD_OPTIONS}
            />
            {custom && (
              <>
                <LooplessDate value={start} onValueChange={setStart} ariaLabel="From" max={end || undefined} />
                <LooplessDate value={end} onValueChange={setEnd} ariaLabel="To" min={start || undefined} />
              </>
            )}
          </div>
          {error ? (
            <div className="organization-state">
              <h3>{error}</h3>
              <button type="button" onClick={() => void load()}>
                Retry
              </button>
            </div>
          ) : loading && !summary ? (
            <TableSkeleton />
          ) : summary ? (
            <>
              <div className="services-pricing-summary-grid production-summary">
                <article>
                  <span>Revenue</span>
                  <strong>{money(summary.revenue, currency)}</strong>
                  <small>
                    {summary.approved_items} approved {summary.approved_items === 1 ? "item" : "items"}
                  </small>
                </article>
                <article>
                  <span>Team cost</span>
                  <strong>{money(summary.team_cost, currency)}</strong>
                  <small>
                    Commission {money(summary.commission_cost, currency)} · salaries{" "}
                    {money(summary.salary_cost, currency)}
                  </small>
                </article>
                <article>
                  <span>Gross margin</span>
                  <strong className={Number(summary.gross_margin) < 0 ? "negative" : undefined}>
                    {money(summary.gross_margin, currency)}
                  </strong>
                  <small>Revenue minus team cost</small>
                </article>
                <article>
                  <span>Pending from clients</span>
                  <strong>{money(summary.pending_client_payments, currency)}</strong>
                  <small>Billed but not yet received (all time)</small>
                </article>
                <article>
                  <span>Pending to team</span>
                  <strong>{money(summary.pending_team_payments, currency)}</strong>
                  <small>
                    Managers {money(summary.pending_manager_payments, currency)} · salaries{" "}
                    {money(summary.pending_salary_payments, currency)}
                  </small>
                </article>
                <article>
                  <span>Open tasks</span>
                  <strong>{summary.open_tasks}</strong>
                  <small>
                    {summary.overdue_tasks} overdue · {summary.in_review_tasks} to review · {summary.unassigned_tasks}{" "}
                    unassigned
                  </small>
                </article>
                <article>
                  <span>Most open work</span>
                  <strong>{summary.top_client ? summary.top_client.name : "—"}</strong>
                  <small>
                    {summary.top_client
                      ? `${summary.top_client_open_tasks} open ${summary.top_client_open_tasks === 1 ? "task" : "tasks"}`
                      : "No open tasks"}
                  </small>
                </article>
              </div>
              <nav className="production-tabs" aria-label="Report type">
                {TABS.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className={tab === item.id ? "active" : ""}
                    aria-pressed={tab === item.id}
                    onClick={() => setTab(item.id)}
                  >
                    {item.icon}
                    {item.label}
                  </button>
                ))}
              </nav>
              {tab === "clients" && clients && <ClientTable report={clients} />}
              {tab === "team" && team && <TeamTable report={team} />}
              {tab === "services" && services && <ServiceTable report={services} />}
              <p className="production-muted">
                Revenue, commission and completed counts use the approval date. Pending amounts are all-time balances.
              </p>
            </>
          ) : null}
        </section>
      </div>
    </>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="organization-state">
      <h3>{text}</h3>
    </div>
  );
}

function ClientTable({ report }: { report: Report<ClientReportRow> }) {
  if (report.rows.length === 0) return <Empty text="No clients yet." />;
  const currency = report.currency;
  return (
    <div className="organization-table production-report-clients" role="table">
      <div className="organization-table-head">
        <span>Client</span>
        <span className="production-money">Tasks</span>
        <span className="production-money">Done</span>
        <span className="production-money">Billed</span>
        <span className="production-money">Received</span>
        <span className="production-money">Unpaid</span>
        <span className="production-money">Budget left</span>
      </div>
      {report.rows.map((row) => (
        <article key={row.client.id}>
          <div className="production-cell">
            <small>
              {row.client.code}
              {row.open_tasks ? ` · ${row.open_tasks} open` : ""}
            </small>
            <strong>{row.client.name}</strong>
          </div>
          <span className="production-money" data-label="Tasks">
            {row.total_tasks}
          </span>
          <span className="production-money" data-label="Done">
            {row.completed_tasks}
          </span>
          <span className="production-money" data-label="Billed">
            {money(row.billed, currency)}
          </span>
          <span className="production-money" data-label="Received">
            {money(row.received, currency)}
          </span>
          <span
            className={`production-money${Number(row.pending) > 0 ? " production-overdue" : ""}`}
            data-label="Unpaid"
          >
            {money(row.pending, currency)}
          </span>
          <span className="production-money" data-label="Budget left">
            {Number(row.budget_total) > 0 ? money(row.budget_remaining, currency) : "No budget"}
          </span>
        </article>
      ))}
    </div>
  );
}

function TeamTable({ report }: { report: Report<TeamReportRow> }) {
  if (report.rows.length === 0) return <Empty text="No managers or employees yet." />;
  const currency = report.currency;
  return (
    <div className="organization-table production-report-team" role="table">
      <div className="organization-table-head">
        <span>Team member</span>
        <span>Pay</span>
        <span className="production-money">Tasks</span>
        <span className="production-money">Done</span>
        <span className="production-money">Earned</span>
        <span className="production-money">Paid</span>
        <span className="production-money">Pending</span>
      </div>
      {report.rows.map((row) => (
        <article key={row.person.id}>
          <div className="production-cell">
            <small>
              {row.person.role === "MANAGER" ? "Manager" : "Employee"}
              {row.open_tasks ? ` · ${row.open_tasks} open` : ""}
            </small>
            <strong>{row.person.name}</strong>
          </div>
          <span data-label="Pay">{row.person.role === "MANAGER" ? "Commission" : "Salary"}</span>
          <span className="production-money" data-label="Tasks">
            {row.total_tasks}
          </span>
          <span className="production-money" data-label="Done">
            {row.completed_tasks}
          </span>
          <span className="production-money" data-label="Earned">
            {money(row.earnings, currency)}
          </span>
          <span className="production-money" data-label="Paid">
            {money(row.paid, currency)}
          </span>
          <span
            className={`production-money${Number(row.pending) > 0 ? " production-overdue" : ""}`}
            data-label="Pending"
          >
            {money(row.pending, currency)}
          </span>
        </article>
      ))}
    </div>
  );
}

function ServiceTable({ report }: { report: ServiceReport }) {
  if (report.rows.length === 0) return <Empty text="No services yet." />;
  const currency = report.currency;
  const rows = report.totals ? [...report.rows, report.totals] : report.rows;
  return (
    <div className="organization-table production-report-services" role="table">
      <div className="organization-table-head">
        <span>Service</span>
        <span className="production-money">Items</span>
        <span className="production-money">Revenue</span>
        <span className="production-money">Commission</span>
        <span className="production-money">Margin</span>
      </div>
      {rows.map((row) => {
        const total = row === report.totals;
        return (
          <article key={total ? "total" : row.service.id} className={total ? "production-total" : undefined}>
            <div className="production-cell">
              <strong>{row.service.name}</strong>
            </div>
            <span className="production-money" data-label="Items">
              {row.items}
            </span>
            <span className="production-money" data-label="Revenue">
              {money(row.revenue, currency)}
            </span>
            <span className="production-money" data-label="Commission">
              {money(row.commission_cost, currency)}
            </span>
            <span
              className={`production-money${Number(row.margin) < 0 ? " production-overdue" : ""}`}
              data-label="Margin"
            >
              {money(row.margin, currency)}
            </span>
          </article>
        );
      })}
    </div>
  );
}
