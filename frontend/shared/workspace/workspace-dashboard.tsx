"use client";

/*
 * Manager and Employee dashboards, in the style of the Admin dashboard (owner request 2026-11-14).
 * Money (commission, salary) is hidden until the privacy eye is pressed.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlarmClock, CheckCheck, ClipboardList, HandCoins, Hourglass, Wallet } from "lucide-react";
import {
  DashHeader,
  DashLoading,
  MonthBars,
  Panel,
  PanelHead,
  StatusBars,
  Tile,
  lastMonths,
  monthKey,
  todayText,
} from "../dashboard/role-dashboard-ui";
import { STATUS_LABELS, api, errorText, formatDate, money as formatMoney } from "../production/client";
import { MoneyPrivacy, PrivacyToggle, usePrivateMoney } from "../production/privacy";
import type { EmployeeSalary, ManagerEarnings, Paged, TaskStatus } from "../production/types";
import type { WorkerTask, WorkspaceDashboard } from "./types";
import { useLiveRefresh } from "../realtime/realtime";

type Role = "MANAGER" | "EMPLOYEE";
type Me = { user: { name: string }; company: { name: string } | null };

const DONE: TaskStatus[] = ["APPROVED", "COMPLETED"];

function compactMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(amount);
}

export function WorkspaceDashboardPage({ role }: { role: Role }) {
  return (
    <MoneyPrivacy>
      <WorkspaceDashboardContent role={role} />
    </MoneyPrivacy>
  );
}

function WorkspaceDashboardContent({ role }: { role: Role }) {
  const money = usePrivateMoney(formatMoney);
  const chartMoney = usePrivateMoney(compactMoney);
  const [me, setMe] = useState<Me | null>(null);
  const [dash, setDash] = useState<WorkspaceDashboard | null>(null);
  const [tasks, setTasks] = useState<WorkerTask[]>([]);
  const [earnings, setEarnings] = useState<ManagerEarnings | null>(null);
  const [salary, setSalary] = useState<EmployeeSalary | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [profile, dashboard, list, pay] = await Promise.all([
        api<Me>("/api/auth/me").catch(() => null),
        api<WorkspaceDashboard>("/api/workspace/dashboard"),
        api<Paged<WorkerTask>>("/api/workspace/tasks?page_size=500"),
        role === "MANAGER"
          ? api<ManagerEarnings>("/api/workspace/earnings/commission").catch(() => null)
          : api<EmployeeSalary>("/api/workspace/earnings/salary").catch(() => null),
      ]);
      setMe(profile);
      setDash(dashboard);
      setTasks(list.items);
      if (role === "MANAGER") setEarnings(pay as ManagerEarnings | null);
      else setSalary(pay as EmployeeSalary | null);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load your dashboard."));
    }
  }, [role]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useLiveRefresh(["task.", "payout.", "salary."], () => void load());

  const months = useMemo(() => lastMonths(6), []);
  const thisMonth = months[months.length - 1];
  const delivered = useMemo(
    () =>
      tasks
        .filter((task) => task.my_role === "ASSIGNEE" && DONE.includes(task.status) && task.approved_at)
        .sort((a, b) => (b.approved_at ?? "").localeCompare(a.approved_at ?? "")),
    [tasks],
  );

  const subtitle = `${todayText()}${me?.company ? ` · ${me.company.name}` : ""}`;
  const earningsHref = role === "MANAGER" ? "/earnings" : "/salary";

  return (
    <div className="dash-content production-dashboard">
      <DashHeader
        name={me?.user.name ?? ""}
        subtitle={subtitle}
        actions={
          <>
            <PrivacyToggle />
            <Link href={earningsHref} className="management-secondary-action">
              <Wallet /> {role === "MANAGER" ? "My earnings" : "My salary"}
            </Link>
            <Link href="/tasks" className="management-primary-action">
              <ClipboardList /> My tasks
            </Link>
          </>
        }
      />

      {error ? (
        <div className="organization-state">
          <h3>{error}</h3>
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : !dash ? (
        <DashLoading />
      ) : (
        <div className="production-dash-body">
          <section className="company-dashboard-kpis" aria-label="Your summary">
            <Tile
              title={role === "MANAGER" ? "Commission this month" : "Salary this month"}
              value={money(dash.current_month_earnings, dash.currency)}
              icon={<HandCoins />}
            >
              {Number(dash.pending_payment) > 0
                ? `${money(dash.pending_payment, dash.currency)} not paid yet`
                : "Everything paid"}
            </Tile>
            <Tile
              title="Open tasks"
              value={String(dash.counts.assigned + dash.counts.in_progress)}
              icon={<ClipboardList />}
            >
              {dash.counts.overdue > 0 ? `${dash.counts.overdue} overdue` : "Nothing overdue"}
            </Tile>
            <Tile
              title="Waiting for review"
              value={String(dash.counts.submitted + dash.counts.in_review)}
              icon={<Hourglass />}
            >
              The Admin approves these
            </Tile>
            {role === "MANAGER" ? (
              <Tile
                title={Number(earnings?.wallet?.balance ?? 0) < 0 ? "Due to you" : "Advance left"}
                value={money(Math.abs(Number(earnings?.wallet?.balance ?? 0)), dash.currency)}
                icon={<Wallet />}
                tone={Number(earnings?.wallet?.balance ?? 0) < 0 ? "negative" : undefined}
              >
                {earnings?.wallet ? `Topped up ${money(earnings.wallet.topped_up, dash.currency)}` : "No top-ups yet"}
              </Tile>
            ) : (
              <Tile
                title="Delivered this month"
                value={String(delivered.filter((task) => monthKey(task.approved_at) === thisMonth).length)}
                icon={<CheckCheck />}
              >
                Approved by the Admin
              </Tile>
            )}
          </section>

          <section className="company-dashboard-grid production-dash-grid">
            <Panel>
              {role === "MANAGER" ? (
                <>
                  <PanelHead eyebrow="EARNINGS" title="Commission, last 6 months" />
                  <div className="production-dash-panel-body">
                    <MonthBars
                      label="Commission earned per month"
                      points={months.map((key) => {
                        const value = (earnings?.tasks ?? [])
                          .filter((line) => monthKey(line.approved_at) === key)
                          .reduce((sum, line) => sum + Number(line.commission), 0);
                        return { key, value, display: chartMoney(value, earnings?.currency ?? dash.currency) };
                      })}
                    />
                  </div>
                </>
              ) : (
                <>
                  <PanelHead eyebrow="DELIVERIES" title="Work delivered, last 6 months" />
                  <div className="production-dash-panel-body">
                    <MonthBars
                      label="Tasks approved per month"
                      points={months.map((key) => {
                        const value = delivered.filter((task) => monthKey(task.approved_at) === key).length;
                        return { key, value, display: String(value) };
                      })}
                    />
                    {salary?.current_monthly_salary && (
                      <p className="production-dash-footnote">
                        Monthly salary {money(salary.current_monthly_salary, salary.currency)}
                      </p>
                    )}
                  </div>
                </>
              )}
            </Panel>
            <Panel>
              <PanelHead
                eyebrow="WORK"
                title={`${dash.counts.assigned + dash.counts.in_progress + dash.counts.submitted + dash.counts.in_review} in progress`}
              />
              <div className="production-dash-panel-body">
                <StatusBars
                  href={(status) => `/tasks?status=${status}`}
                  rows={[
                    { key: "ASSIGNED", label: STATUS_LABELS.ASSIGNED, count: dash.counts.assigned },
                    { key: "IN_PROGRESS", label: STATUS_LABELS.IN_PROGRESS, count: dash.counts.in_progress },
                    { key: "SUBMITTED", label: STATUS_LABELS.SUBMITTED, count: dash.counts.submitted },
                    { key: "REVIEW", label: STATUS_LABELS.REVIEW, count: dash.counts.in_review },
                    { key: "APPROVED", label: STATUS_LABELS.APPROVED, count: dash.counts.approved },
                    { key: "COMPLETED", label: STATUS_LABELS.COMPLETED, count: dash.counts.completed },
                  ]}
                />
                <p className="production-dash-footnote">
                  {dash.counts.overdue > 0 ? `${dash.counts.overdue} overdue · ` : ""}
                  {role === "MANAGER" ? `${dash.counts.monitoring} monitoring` : "Only your own tasks"}
                </p>
              </div>
            </Panel>
          </section>

          <section className="company-dashboard-grid production-dash-grid">
            <Panel>
              <PanelHead
                eyebrow="NEXT UP"
                title="Due soon"
                aside={
                  <Link href="/tasks" className="production-dash-link">
                    All tasks
                  </Link>
                }
              />
              <div className="production-dash-panel-body">
                {dash.upcoming_tasks.length === 0 ? (
                  <p className="production-dash-empty">
                    <AlarmClock aria-hidden="true" />
                    Nothing due right now.
                  </p>
                ) : (
                  <ul className="production-dash-rows">
                    {dash.upcoming_tasks.map((task) => (
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
                              {task.due_date
                                ? `${task.is_overdue ? "Overdue" : "Due"} ${formatDate(task.due_date)}`
                                : "No due date"}
                            </em>
                            <small>
                              {STATUS_LABELS[task.status]}
                              {task.my_role === "MONITOR" ? " · monitoring" : ""}
                            </small>
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Panel>
            <Panel>
              <PanelHead eyebrow="DELIVERED" title="Recently approved" />
              <div className="production-dash-panel-body">
                {delivered.length === 0 ? (
                  <p className="production-dash-empty">
                    <CheckCheck aria-hidden="true" />
                    Approved work shows up here.
                  </p>
                ) : (
                  <ul className="production-dash-rows">
                    {delivered.slice(0, 5).map((task) => (
                      <li key={task.id}>
                        <Link href={`/tasks?task=${task.id}`}>
                          <span>
                            <small>
                              {task.code} · {task.service_name}
                            </small>
                            <strong>{task.title}</strong>
                          </span>
                          <span className="meta">
                            <em>{task.my_commission ? money(task.my_commission, task.currency) : "Approved"}</em>
                            <small>{formatDate(task.approved_at)}</small>
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Panel>
          </section>
        </div>
      )}
    </div>
  );
}
