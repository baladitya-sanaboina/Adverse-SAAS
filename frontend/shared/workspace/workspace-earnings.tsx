"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarDays, ClipboardList, History } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { Panel, TableSkeleton } from "../production/production-ui";
import {
  STATUS_LABELS,
  api,
  errorText,
  formatDate,
  formatMonth,
  methodLabel,
  money as formatMoneyText,
} from "../production/client";
import { MoneyPrivacy, PrivacyToggle, usePrivateMoney } from "../production/privacy";
import { AdvanceWallet } from "./advance-wallet";
import type { EmployeeSalary, ManagerEarnings } from "../production/types";
import "../styles/organization.css";
import "../styles/service-pricing-settings.css";
import "../styles/production.css";

function useLoad<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      setData(await api<T>(url));
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load."));
    }
  }, [url]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  return { data, error, load };
}

function Failed({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="organization-state">
      <h3>{error}</h3>
      <button type="button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

/** Manager's own commission: earned on approval, minus payouts received. */
/** Manager → Payment Sheets (owner request 2026-11-14): each Admin top-up is a sheet. */
export function ManagerSheetsPage() {
  return (
    <MoneyPrivacy>
      <ManagerSheetsPageContent />
    </MoneyPrivacy>
  );
}

function ManagerSheetsPageContent() {
  const money = usePrivateMoney(formatMoneyText);
  const { data, error, load } = useLoad<ManagerEarnings>("/api/workspace/earnings/commission");
  return (
    <>
      <DashboardHero
        title=""
        highlight="Payment Sheets"
        action={<PrivacyToggle className="" />}
        description="Every top-up from the Admin opens a new sheet. What is left, or owed, carries into the next one."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace">
          {error ? (
            <Failed error={error} onRetry={() => void load()} />
          ) : !data ? (
            <TableSkeleton />
          ) : (
            <AdvanceWallet
              wallet={data.wallet ?? { topped_up: "0", earned: data.earned, balance: "0", periods: [], lines: [] }}
              currency={data.currency}
              money={money}
              viewer="MANAGER"
              statementUrl={(index) => `/api/workspace/earnings/sheets/${index}/statement.pdf`}
            />
          )}
        </section>
      </div>
    </>
  );
}

export function ManagerEarningsPage() {
  return (
    <MoneyPrivacy>
      <ManagerEarningsPageContent />
    </MoneyPrivacy>
  );
}

function ManagerEarningsPageContent() {
  const money = usePrivateMoney(formatMoneyText);
  const { data, error, load } = useLoad<ManagerEarnings>("/api/workspace/earnings/commission");
  const currency = data?.currency ?? "INR";
  return (
    <>
      <DashboardHero
        title=""
        highlight="My Earnings"
        action={<PrivacyToggle className="" />}
        description="Your advance from the Admin, the commission it covers, and every top-up you have received."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace">
          {error ? (
            <Failed error={error} onRetry={() => void load()} />
          ) : !data ? (
            <TableSkeleton />
          ) : (
            <>
              {data.wallet && (
                <AdvanceWallet
                  wallet={data.wallet}
                  currency={currency}
                  money={money}
                  viewer="MANAGER"
                  statementUrl={(index) => `/api/workspace/earnings/sheets/${index}/statement.pdf`}
                />
              )}
              <div className="services-pricing-summary-grid production-summary">
                <article>
                  <span>This month</span>
                  <strong>{money(data.current_month_earned, currency)}</strong>
                  <small>Commission approved this month</small>
                </article>
                <article>
                  <span>Earned</span>
                  <strong>{money(data.earned, currency)}</strong>
                  <small>All approved work</small>
                </article>
                <article>
                  <span>Coming</span>
                  <strong>{money(data.upcoming, currency)}</strong>
                  <small>Your tasks not yet approved</small>
                </article>
                <article>
                  <span>Top-ups received</span>
                  <strong>{money(data.paid, currency)}</strong>
                  <small>
                    {data.payouts.length} {data.payouts.length === 1 ? "top-up" : "top-ups"} so far
                  </small>
                </article>
              </div>
              <div className="production-detail">
                <div>
                  <Panel icon={<ClipboardList />} eyebrow="COMMISSION" title="By task">
                    <div className="production-panel-body">
                      {data.tasks.length === 0 ? (
                        <p className="production-muted">No tasks assigned to you yet.</p>
                      ) : (
                        <ul className="production-list">
                          {data.tasks.map((task) => (
                            <li key={task.task_id}>
                              <div>
                                <strong>
                                  {task.code} · {task.title}
                                </strong>
                                <small>
                                  {task.service_name} · {STATUS_LABELS[task.status]}
                                  {task.approved_at ? ` · approved ${formatDate(task.approved_at)}` : ""}
                                </small>
                              </div>
                              <b>{money(task.commission, currency)}</b>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </Panel>
                </div>
                <div>
                  <Panel icon={<History />} eyebrow="TOP-UPS" title="Received">
                    <div className="production-panel-body">
                      {data.payouts.length === 0 ? (
                        <p className="production-muted">No top-ups yet.</p>
                      ) : (
                        <ul className="production-list">
                          {data.payouts.map((payout) => (
                            <li key={payout.id}>
                              <div>
                                <strong>{formatDate(payout.paid_on)}</strong>
                                <small>
                                  {methodLabel(payout.method)}
                                  {payout.reference ? ` · ${payout.reference}` : ""}
                                </small>
                              </div>
                              <b>{money(payout.amount, payout.currency)}</b>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </Panel>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}

/** Employee's own salary: due by month, paid and pending. */
export function EmployeeSalaryPage() {
  return (
    <MoneyPrivacy>
      <EmployeeSalaryPageContent />
    </MoneyPrivacy>
  );
}

function EmployeeSalaryPageContent() {
  const money = usePrivateMoney(formatMoneyText);
  const { data, error, load } = useLoad<EmployeeSalary>("/api/workspace/earnings/salary");
  const currency = data?.currency ?? "INR";
  return (
    <>
      <DashboardHero
        title=""
        highlight="My Salary"
        action={<PrivacyToggle className="" />}
        description="Your monthly salary, what has been paid and what is still pending."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace">
          {error ? (
            <Failed error={error} onRetry={() => void load()} />
          ) : !data ? (
            <TableSkeleton />
          ) : (
            <>
              <div className="services-pricing-summary-grid production-summary">
                <article>
                  <span>Monthly salary</span>
                  <strong>
                    {data.current_monthly_salary ? money(data.current_monthly_salary, currency) : "Not set"}
                  </strong>
                  <small>Current rate</small>
                </article>
                <article>
                  <span>Total due</span>
                  <strong>{money(data.total_due, currency)}</strong>
                  <small>All months so far</small>
                </article>
                <article>
                  <span>Paid</span>
                  <strong>{money(data.total_paid, currency)}</strong>
                  <small>All salary payments</small>
                </article>
                <article>
                  <span>Pending</span>
                  <strong>{money(data.pending, currency)}</strong>
                  <small>Due minus paid</small>
                </article>
              </div>
              <div className="production-detail">
                <div>
                  <Panel icon={<CalendarDays />} eyebrow="MONTHS" title="Salary by month">
                    <div className="production-panel-body">
                      {data.months.length === 0 ? (
                        <p className="production-muted">Your salary has not been set yet.</p>
                      ) : (
                        <ul className="production-list">
                          {data.months.map((line) => (
                            <li key={line.month}>
                              <div>
                                <strong>{formatMonth(line.month)}</strong>
                                <small>
                                  Due {money(line.due, currency)} · paid {money(line.paid, currency)}
                                </small>
                              </div>
                              <b>{Number(line.pending) > 0 ? `${money(line.pending, currency)} pending` : "Paid"}</b>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </Panel>
                </div>
                <div>
                  <Panel icon={<History />} eyebrow="PAYMENTS" title="Received">
                    <div className="production-panel-body">
                      {data.payments.length === 0 ? (
                        <p className="production-muted">No salary payments yet.</p>
                      ) : (
                        <ul className="production-list">
                          {data.payments.map((payment) => (
                            <li key={payment.id}>
                              <div>
                                <strong>{formatMonth(payment.period_month)}</strong>
                                <small>
                                  Paid {formatDate(payment.paid_on)} · {methodLabel(payment.method)}
                                </small>
                              </div>
                              <b>{money(payment.amount, payment.currency)}</b>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </Panel>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
