"use client";

/*
 * Client details → "Client work" (owner request 2026-11-14): every video made for this client,
 * who edited it, where it stands, what it costs, and the client's budget, payments and invoices.
 * Admin only: the endpoints below refuse other roles on the server.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCheck, ClipboardList, FileText, Hourglass, RefreshCw, Search, Wallet } from "lucide-react";
import {
  STATUS_LABELS,
  api,
  errorText,
  formatDate,
  methodLabel,
  money,
  query,
  statusTone,
} from "@/lib/production/client";
import type { AdminTask, ClientBudget, ClientPayment, Paged, PaymentList, TaskStatus } from "@/lib/production/types";
import { SheetInvoiceButton } from "@/components/sheets/sheet-invoice-button";
import { PaymentSheets, type Sheet } from "@loopless-shared/production/payment-sheets";
import { useLiveRefresh } from "@loopless-shared/realtime/realtime";
import "@/styles/client-work.css";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";

type Invoice = {
  id: string;
  code: string;
  status: "DRAFT" | "SENT" | "PAID" | "VOID";
  issue_date: string;
  due_date: string | null;
  currency: string;
  subtotal: string;
  items: number;
};

type Filter = "all" | "delivered" | "review" | "progress" | "cancelled";

const GROUPS: Record<Exclude<Filter, "all">, TaskStatus[]> = {
  delivered: ["APPROVED", "COMPLETED"],
  review: ["SUBMITTED", "REVIEW"],
  progress: ["PENDING", "ASSIGNED", "IN_PROGRESS"],
  cancelled: ["CANCELLED"],
};

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "delivered", label: "Delivered" },
  { key: "review", label: "Waiting review" },
  { key: "progress", label: "In progress" },
  { key: "cancelled", label: "Cancelled" },
];

function inGroup(task: AdminTask, filter: Filter): boolean {
  return filter === "all" || GROUPS[filter].includes(task.status);
}

function dateText(task: AdminTask): string {
  if (GROUPS.delivered.includes(task.status)) return `Delivered ${formatDate(task.approved_at)}`;
  if (task.status === "CANCELLED") return `Cancelled ${formatDate(task.cancelled_at)}`;
  if (GROUPS.review.includes(task.status)) return `Sent for review ${formatDate(task.submitted_at)}`;
  return task.due_date ? `${task.is_overdue ? "Overdue" : "Due"} ${formatDate(task.due_date)}` : "No due date";
}

export function ClientWorkPanel({ clientId }: { clientId: string }) {
  const [tasks, setTasks] = useState<AdminTask[] | null>(null);
  const [budget, setBudget] = useState<ClientBudget | null>(null);
  const [payments, setPayments] = useState<PaymentList<ClientPayment> | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [sheets, setSheets] = useState<Sheet[]>([]);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [taskList, budgetData, paymentList, invoiceList, sheetList] = await Promise.all([
        api<Paged<AdminTask>>(`/api/company/tasks${query({ client_id: clientId, page_size: 500 })}`),
        api<ClientBudget>(`/api/company/finance/budgets/${clientId}`).catch(() => null),
        api<PaymentList<ClientPayment>>(
          `/api/company/finance/client-payments${query({ client_id: clientId, page_size: 100 })}`,
        ).catch(() => null),
        api<Paged<Invoice>>(`/api/company/invoices${query({ client_id: clientId, page_size: 100 })}`).catch(() => null),
        api<Sheet[]>(`/api/company/finance/sheets/clients/${clientId}`).catch(() => []),
      ]);
      setTasks(taskList.items);
      setBudget(budgetData);
      setPayments(paymentList);
      setInvoices(invoiceList?.items ?? []);
      setSheets(sheetList);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load this client's work."));
    }
  }, [clientId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useLiveRefresh(["task.", "payment.", "invoice.", "budget."], () => void load());

  const all = useMemo(() => tasks ?? [], [tasks]);
  const currency = all[0]?.currency ?? budget?.budget.currency ?? payments?.items[0]?.currency ?? "INR";
  const count = (group: Exclude<Filter, "all">) => all.filter((task) => inGroup(task, group)).length;
  const delivered = all.filter((task) => inGroup(task, "delivered"));
  const billed = delivered.reduce((sum, task) => sum + Number(task.client_price), 0);
  const paid = Number(payments?.total_amount ?? 0);
  const due = Math.max(billed - paid, 0);
  const lastPayment = payments?.items[0]?.received_on ?? null;

  const services = useMemo(() => {
    const rows = new Map<string, { name: string; delivered: number; open: number; billed: number }>();
    for (const task of all) {
      if (task.status === "CANCELLED") continue;
      const row = rows.get(task.service.id) ?? { name: task.service.name, delivered: 0, open: 0, billed: 0 };
      if (inGroup(task, "delivered")) {
        row.delivered += 1;
        row.billed += Number(task.client_price);
      } else row.open += 1;
      rows.set(task.service.id, row);
    }
    return [...rows.values()].sort((a, b) => b.delivered + b.open - (a.delivered + a.open));
  }, [all]);

  const shown = useMemo(() => {
    const term = search.trim().toLowerCase();
    return all
      .filter((task) => inGroup(task, filter))
      .filter(
        (task) =>
          !term ||
          [task.code, task.title, task.service.name, task.assignee?.name ?? ""].some((text) =>
            text.toLowerCase().includes(term),
          ),
      )
      .sort((a, b) =>
        (b.approved_at ?? b.updated_at ?? b.created_at).localeCompare(a.approved_at ?? a.updated_at ?? a.created_at),
      );
  }, [all, filter, search]);

  const live = all.filter((task) => task.status !== "CANCELLED").length;

  return (
    <section className="client-pricing client-work" aria-label="Client work">
      <header>
        <div>
          <span>Client work</span>
          <h3>
            {tasks === null
              ? "Loading work…"
              : `${live} ${live === 1 ? "video" : "videos"} · ${delivered.length} delivered`}
          </h3>
        </div>
        <div className="client-detail-actions">
          <Link href={`/tasks?client=${clientId}`} className="management-secondary-action">
            <ClipboardList /> Open in Tasks
          </Link>
          <Link href="/invoices" className="management-primary-action">
            <FileText /> Invoices
          </Link>
        </div>
      </header>

      {error ? (
        <div className="client-work-state" role="alert">
          <strong>{error}</strong>
          <button type="button" className="management-secondary-action" onClick={() => void load()}>
            <RefreshCw /> Retry
          </button>
        </div>
      ) : tasks === null ? (
        <div className="client-work-state">
          <OrbitLoader size={56} label="Loading this client's videos" />
        </div>
      ) : (
        <>
          <div className="client-work-summary">
            <article>
              <span>
                <CheckCheck aria-hidden="true" /> Delivered
              </span>
              <strong>{delivered.length}</strong>
              <small>
                {count("review")} waiting review · {count("progress")} in progress
              </small>
            </article>
            <article>
              <span>
                <FileText aria-hidden="true" /> Billed
              </span>
              <strong>{money(billed, currency)}</strong>
              <small>
                For {delivered.length} delivered {delivered.length === 1 ? "video" : "videos"}
              </small>
            </article>
            <article>
              <span>
                <Wallet aria-hidden="true" /> Paid
              </span>
              <strong className="good">{money(paid, currency)}</strong>
              <small>{lastPayment ? `Last payment ${formatDate(lastPayment)}` : "No payment yet"}</small>
            </article>
            <article className={due > 0 ? "due" : undefined}>
              <span>
                <Hourglass aria-hidden="true" /> {due > 0 ? "Still to collect" : "Balance"}
              </span>
              <strong>{due > 0 ? money(due, currency) : "Paid up"}</strong>
              <small>
                {budget?.budget.has_budget
                  ? `Budget ${money(budget.budget.total, currency)} · ${money(budget.budget.remaining, currency)} left`
                  : "No budget recorded"}
              </small>
            </article>
          </div>

          {services.length > 0 && (
            <div className="client-work-services" aria-label="Videos by service">
              {services.map((row) => (
                <article key={row.name}>
                  <strong>{row.name}</strong>
                  <span>
                    {row.delivered} delivered{row.open ? ` · ${row.open} open` : ""}
                  </span>
                  <em>{money(row.billed, currency)}</em>
                </article>
              ))}
            </div>
          )}

          <div className="client-work-tools">
            <nav className="client-work-filters" aria-label="Filter videos">
              {FILTERS.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  className={filter === key ? "active" : undefined}
                  aria-pressed={filter === key}
                  onClick={() => setFilter(key)}
                >
                  {label}
                  <em>{key === "all" ? all.length : count(key)}</em>
                </button>
              ))}
            </nav>
            <label className="client-work-search">
              <Search aria-hidden="true" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search video, code or editor"
                aria-label="Search this client's videos"
              />
            </label>
          </div>

          {shown.length === 0 ? (
            <div className="client-work-state">
              {all.length === 0 ? "No videos for this client yet." : "No videos match this filter."}
            </div>
          ) : (
            <div className="client-work-table" role="table" aria-label="Videos for this client">
              <div className="client-work-row head" role="row">
                <span role="columnheader">Video</span>
                <span role="columnheader">Edited by</span>
                <span role="columnheader">Status</span>
                <span role="columnheader">Date</span>
                <span role="columnheader">Amount</span>
              </div>
              {shown.map((task) => (
                <Link key={task.id} href={`/tasks?task=${task.id}`} className="client-work-row" role="row">
                  <span role="cell" className="video">
                    <small>
                      {task.code} · {task.service.name}
                    </small>
                    <strong>{task.title}</strong>
                  </span>
                  <span role="cell" data-label="Edited by">
                    {task.assignee ? task.assignee.name : "Not assigned"}
                    {task.monitor ? <small>Manager {task.monitor.name}</small> : null}
                  </span>
                  <span role="cell" data-label="Status">
                    <em className={`client-work-status ${statusTone(task.status)}`}>{STATUS_LABELS[task.status]}</em>
                  </span>
                  <span
                    role="cell"
                    data-label="Date"
                    className={task.is_overdue && !inGroup(task, "delivered") ? "late" : undefined}
                  >
                    {dateText(task)}
                  </span>
                  <span role="cell" data-label="Amount" className="amount">
                    {task.status === "CANCELLED" ? "—" : money(task.client_price, task.currency)}
                  </span>
                </Link>
              ))}
            </div>
          )}

          <div className="client-work-sheets">
            <h4>Payment sheets</h4>
            <PaymentSheets
              sheets={sheets}
              currency={currency}
              money={money}
              date={formatDate}
              itemWord="video"
              empty="No payments yet. Each payment you record in Payments → Client payments opens a new sheet."
              sheetAction={(sheet) => <SheetInvoiceButton sheet={sheet} clientId={clientId} />}
            />
          </div>

          <div className="client-work-money">
            <article>
              <h4>Payments received</h4>
              {payments?.items.length ? (
                <ul>
                  {payments.items.map((payment) => (
                    <li key={payment.id}>
                      <span>
                        <strong>{formatDate(payment.received_on)}</strong>
                        <small>
                          {methodLabel(payment.method)}
                          {payment.reference ? ` · ${payment.reference}` : ""}
                        </small>
                      </span>
                      <em className="good">{money(payment.amount, payment.currency)}</em>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>
                  No payment yet. <Link href="/payments">Record a payment</Link>
                </p>
              )}
            </article>
            <article>
              <h4>Invoices</h4>
              {invoices.length ? (
                <ul>
                  {invoices.map((invoice) => (
                    <li key={invoice.id}>
                      <span>
                        <a href={`/api/company/invoices/${invoice.id}/pdf`} target="_blank" rel="noreferrer">
                          <strong>{invoice.code}</strong>
                        </a>
                        <small>
                          {invoice.status === "DRAFT"
                            ? "Draft"
                            : invoice.status === "PAID"
                              ? "Paid"
                              : invoice.status === "VOID"
                                ? "Void"
                                : invoice.due_date
                                  ? `Sent · due ${formatDate(invoice.due_date)}`
                                  : "Sent"}{" "}
                          · {invoice.items} {invoice.items === 1 ? "video" : "videos"}
                        </small>
                      </span>
                      <em>{money(invoice.subtotal, invoice.currency)}</em>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>
                  No invoices yet. <Link href="/invoices">Create one</Link>
                </p>
              )}
            </article>
          </div>
        </>
      )}
    </section>
  );
}
