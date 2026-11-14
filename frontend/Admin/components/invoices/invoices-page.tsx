"use client";

/*
 * Invoices (Phase 11, owner request 2026-11-14). A draft is prepared automatically when a client's
 * top-up is used up; the Admin can also make one for any client and period. Each invoice lists
 * every video with its date and amount, the payments received in the period and the balance.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Ban,
  CalendarDays,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Plus,
  ReceiptText,
  RefreshCw,
  Send,
  Trash2,
} from "lucide-react";
import { SheetHeader, TaskSheet } from "@loopless-shared/production/task-board-ui";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { Field, Panel } from "@/components/production/production-ui";
import { api, errorText, formatDate, formatDateTime, money, query } from "@/lib/production/client";
import type { Paged } from "@/lib/production/types";
import "@/styles/organization.css";
import "@/styles/production.css";
import "@/styles/invoices.css";

type InvoiceStatus = "DRAFT" | "SENT" | "PAID" | "VOID";
type Invoice = {
  id: string;
  code: string;
  status: InvoiceStatus;
  source: "MANUAL" | "TOP_UP";
  client: { id: string; name: string; code: string };
  client_email: string | null;
  period_start: string;
  period_end: string;
  issue_date: string;
  due_date: string | null;
  currency: string;
  subtotal: string;
  payments_total: string;
  budget_added: string;
  balance: string;
  items: number;
  notes: string;
  created_by_name: string;
  sent_at: string | null;
  paid_at: string | null;
  created_at: string;
};
type InvoiceDetail = Invoice & {
  lines: { position: number; delivered_on: string; title: string; service_name: string; amount: string }[];
  payments: { received_on: string; method: string; reference: string; amount: string }[];
};
type Cycle = {
  index: number;
  start: string;
  end: string | null;
  amount: string;
  used: string;
  remaining: string;
  items: number;
  invoice_id: string | null;
  invoice_code: string | null;
};
type ClientItem = { id: string; name: string; status?: string };
type Sheet = { mode: "create" } | { mode: "detail"; id: string } | null;

const STATUS_LABELS: Record<InvoiceStatus, string> = { DRAFT: "Draft", SENT: "Sent", PAID: "Paid", VOID: "Void" };
const METHOD_LABELS: Record<string, string> = {
  BANK_TRANSFER: "Bank transfer",
  UPI: "UPI",
  CASH: "Cash",
  CHEQUE: "Cheque",
  CARD: "Card",
  OTHER: "Other",
};
const TABS: ("" | InvoiceStatus)[] = ["", "DRAFT", "SENT", "PAID", "VOID"];
const UUID = /^[0-9a-f-]{36}$/i;

function tone(status: InvoiceStatus): string {
  return status === "PAID" ? "active" : status === "VOID" ? "inactive" : status === "DRAFT" ? "draft" : "";
}

function syncUrl(sheet: Sheet) {
  const url = new URL(window.location.href);
  url.searchParams.delete("invoice");
  url.searchParams.delete("mode");
  if (sheet?.mode === "detail") url.searchParams.set("invoice", sheet.id);
  if (sheet?.mode === "create") url.searchParams.set("mode", "create");
  window.history.replaceState(null, "", `${url.pathname}${url.search}`);
}

function balanceText(invoice: Invoice): string {
  const balance = Number(invoice.balance);
  if (balance > 0) return money(balance, invoice.currency);
  if (balance < 0) return `${money(-balance, invoice.currency)} credit`;
  return "Settled";
}

export function InvoicesPage() {
  const [items, setItems] = useState<Invoice[]>([]);
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<"" | InvoiceStatus>("");
  const [client, setClient] = useState("");
  const [sheet, setSheet] = useState<Sheet>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api<Paged<Invoice>>(`/api/company/invoices${query({ client_id: client, page_size: 100 })}`);
      setItems(data.items);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load invoices."));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const id = params.get("invoice");
      if (id && UUID.test(id)) setSheet({ mode: "detail", id });
      else if (params.get("mode") === "create") setSheet({ mode: "create" });
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const data = await api<Paged<ClientItem> | ClientItem[]>("/api/company/clients?page_size=100");
        setClients(Array.isArray(data) ? data : data.items);
      } catch {
        // The client filter just stays empty.
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const open = (next: Sheet, message = "") => {
    setNotice(message);
    setSheet(next);
    syncUrl(next);
  };
  const close = useCallback(() => {
    setSheet(null);
    syncUrl(null);
  }, []);

  const counts = useMemo(() => {
    const result: Record<string, number> = { "": items.length };
    for (const item of items) result[item.status] = (result[item.status] ?? 0) + 1;
    return result;
  }, [items]);
  const visible = status ? items.filter((item) => item.status === status) : items;
  const outstanding = items
    .filter((item) => item.status === "SENT" && Number(item.balance) > 0)
    .reduce((sum, item) => sum + Number(item.balance), 0);
  const currency = items[0]?.currency ?? "INR";

  return (
    <div className="dash-content production-tasks-content">
      <section className="organization-workspace production-workspace production-tasks-page" aria-live="polite">
        <header className="production-dash-header production-tasks-header">
          <div>
            <h1>Invoices</h1>
            <p>
              {loading && items.length === 0
                ? "Loading invoices…"
                : `${counts.DRAFT ?? 0} draft · ${counts.SENT ?? 0} sent · ${money(outstanding, currency)} outstanding`}
            </p>
          </div>
          <div className="production-dash-actions">
            <button type="button" className="management-primary-action" onClick={() => open({ mode: "create" })}>
              <Plus /> New invoice
            </button>
          </div>
        </header>

        <div className="production-task-filters">
          <div className="production-chips" role="group" aria-label="Invoice status">
            {TABS.map((key) => (
              <button
                type="button"
                key={key || "all"}
                className={`production-chip${status === key ? " active" : ""}`}
                aria-pressed={status === key}
                onClick={() => setStatus(key)}
              >
                {key ? STATUS_LABELS[key] : "All"}
                <b>{counts[key] ?? 0}</b>
              </button>
            ))}
          </div>
          <div className="production-task-selects">
            <LooplessSelect
              value={client}
              onValueChange={setClient}
              ariaLabel="Filter by client"
              options={[{ value: "", label: "All clients" }, ...clients.map((c) => ({ value: c.id, label: c.name }))]}
            />
          </div>
        </div>

        {notice && !sheet && <div className="organization-notice">{notice}</div>}
        {error ? (
          <div className="organization-state">
            <h3>{error}</h3>
            <button type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : loading && items.length === 0 ? (
          <div className="organization-skeleton">
            {[1, 2, 3].map((row) => (
              <i key={row} />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <div className="organization-state">
            <ReceiptText />
            <h3>{status || client ? "No invoices match these filters" : "No invoices yet"}</h3>
            <p>
              A draft is prepared automatically when a client&apos;s top-up is used up. You can also make one for any
              period.
            </p>
            <button type="button" onClick={() => open({ mode: "create" })}>
              <Plus /> New invoice
            </button>
          </div>
        ) : (
          <div className="organization-table production-invoices" role="table">
            <div className="organization-table-head">
              <span>Invoice</span>
              <span>Client</span>
              <span>Items</span>
              <span className="production-money">Amount</span>
              <span className="production-money">Balance</span>
              <span>Status</span>
              <span>Actions</span>
            </div>
            {visible.map((invoice) => (
              <article key={invoice.id}>
                <div className="production-cell">
                  <small>
                    {formatDate(invoice.period_start)} – {formatDate(invoice.period_end)}
                    {invoice.source === "TOP_UP" ? " · top-up" : ""}
                  </small>
                  <strong>{invoice.code}</strong>
                </div>
                <span>{invoice.client.name}</span>
                <span>{invoice.items}</span>
                <span className="production-money">{money(invoice.subtotal, invoice.currency)}</span>
                <span className="production-money">{balanceText(invoice)}</span>
                <em className={tone(invoice.status)}>{STATUS_LABELS[invoice.status]}</em>
                <CrudActionButtons
                  view={{ label: `Open ${invoice.code}`, onClick: () => open({ mode: "detail", id: invoice.id }) }}
                />
              </article>
            ))}
          </div>
        )}

        {sheet && (
          <TaskSheet label={sheet.mode === "create" ? "New invoice" : "Invoice"} onClose={close}>
            {sheet.mode === "create" ? (
              <CreateInvoice
                clients={clients}
                initialClient={client}
                onClose={close}
                onCreated={(id, message) => {
                  open({ mode: "detail", id }, message);
                  void load();
                }}
              />
            ) : (
              <InvoiceDetailSheet
                key={sheet.id}
                id={sheet.id}
                notice={notice}
                onClose={close}
                onNotice={setNotice}
                onChanged={() => void load()}
              />
            )}
          </TaskSheet>
        )}
      </section>
    </div>
  );
}

/* ---------------------------------------------------------------------------------- create */

function CreateInvoice({
  clients,
  initialClient,
  onClose,
  onCreated,
}: {
  clients: ClientItem[];
  initialClient: string;
  onClose: () => void;
  onCreated: (id: string, message: string) => void;
}) {
  const [clientId, setClientId] = useState(initialClient);
  const [mode, setMode] = useState<"cycle" | "custom">("cycle");
  const [cycles, setCycles] = useState<Cycle[] | null>(null);
  const [cycleIndex, setCycleIndex] = useState<number | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [due, setDue] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setCycles(null);
      setCycleIndex(null);
      try {
        const data = await api<Cycle[]>(`/api/company/invoices/cycles/${clientId}`);
        if (cancelled) return;
        setCycles(data);
        setMode(data.length ? "cycle" : "custom");
        const next = [...data].reverse().find((cycle) => !cycle.invoice_id);
        setCycleIndex(next?.index ?? data[data.length - 1]?.index ?? null);
      } catch {
        if (!cancelled) setCycles([]);
      }
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [clientId]);

  const today = new Date().toISOString().slice(0, 10);
  const chosen = cycles?.find((cycle) => cycle.index === cycleIndex) ?? null;

  async function create() {
    setError("");
    const periodStart = mode === "cycle" ? chosen?.start : start;
    const periodEnd = mode === "cycle" ? (chosen?.end ?? today) : end;
    if (!clientId) return setError("Choose a client.");
    if (!periodStart || !periodEnd) return setError("Choose the period to invoice.");
    if (periodEnd < periodStart) return setError("The end date must be on or after the start date.");
    setSaving(true);
    try {
      const invoice = await api<InvoiceDetail>("/api/company/invoices", {
        method: "POST",
        json: {
          client_id: clientId,
          period_start: periodStart,
          period_end: periodEnd,
          due_date: due || null,
          notes: notes.trim(),
        },
      });
      onCreated(
        invoice.id,
        `${invoice.code} created as a draft with ${invoice.items} ${invoice.items === 1 ? "item" : "items"}.`,
      );
    } catch (requestError) {
      setError(errorText(requestError, "Unable to create the invoice."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <SheetHeader eyebrow="New invoice" title="Create invoice" onClose={onClose} />
      <Panel
        icon={<ReceiptText />}
        eyebrow="CLIENT AND PERIOD"
        title="What to invoice"
        description="Pick a top-up period, or any dates. Every video approved in the period is listed."
      >
        <div className="production-panel-body">
          {error && <div className="management-form-message">{error}</div>}
          <Field label="Client">
            <LooplessSelect
              value={clientId}
              onValueChange={setClientId}
              ariaLabel="Client"
              options={[
                { value: "", label: "Choose a client" },
                ...clients.filter((c) => c.status !== "INACTIVE").map((c) => ({ value: c.id, label: c.name })),
              ]}
            />
          </Field>
          {clientId && (
            <div className="production-view-toggle invoice-mode" role="group" aria-label="Period">
              <button
                type="button"
                className={mode === "cycle" ? "active" : ""}
                aria-pressed={mode === "cycle"}
                disabled={!cycles?.length}
                onClick={() => setMode("cycle")}
              >
                Top-up period
              </button>
              <button
                type="button"
                className={mode === "custom" ? "active" : ""}
                aria-pressed={mode === "custom"}
                onClick={() => setMode("custom")}
              >
                Custom dates
              </button>
            </div>
          )}
          {clientId && mode === "cycle" && (
            <div className="invoice-cycles" role="radiogroup" aria-label="Top-up periods">
              {cycles === null ? (
                <p className="production-muted">Loading budget periods…</p>
              ) : cycles.length === 0 ? (
                <p className="production-muted">This client has no budget yet. Use custom dates.</p>
              ) : (
                [...cycles].reverse().map((cycle) => {
                  const used =
                    Number(cycle.amount) > 0 ? Math.min(100, (Number(cycle.used) / Number(cycle.amount)) * 100) : 0;
                  return (
                    <button
                      type="button"
                      role="radio"
                      aria-checked={cycleIndex === cycle.index}
                      key={cycle.index}
                      className={`invoice-cycle${cycleIndex === cycle.index ? " active" : ""}`}
                      onClick={() => setCycleIndex(cycle.index)}
                    >
                      <span className="invoice-cycle-top">
                        <strong>Period {cycle.index}</strong>
                        <small>
                          {formatDate(cycle.start)} – {cycle.end ? formatDate(cycle.end) : "now"}
                        </small>
                      </span>
                      <span className="invoice-cycle-bar" aria-hidden="true">
                        <i
                          style={{ width: `${used}%` }}
                          className={Number(cycle.remaining) <= 0 ? "full" : undefined}
                        />
                      </span>
                      <span className="invoice-cycle-meta">
                        <span>
                          {money(cycle.used)} of {money(cycle.amount)} · {cycle.items}{" "}
                          {cycle.items === 1 ? "item" : "items"}
                        </span>
                        {cycle.invoice_code && <em>{cycle.invoice_code} already made</em>}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          )}
          {clientId && mode === "custom" && (
            <div className="invoice-dates">
              <Field label="From">
                <span className="management-input">
                  <CalendarDays aria-hidden="true" />
                  <input type="date" value={start} max={today} onChange={(event) => setStart(event.target.value)} />
                </span>
              </Field>
              <Field label="To">
                <span className="management-input">
                  <CalendarDays aria-hidden="true" />
                  <input type="date" value={end} max={today} onChange={(event) => setEnd(event.target.value)} />
                </span>
              </Field>
            </div>
          )}
          <div className="invoice-dates">
            <Field label="Due date (optional)">
              <span className="management-input">
                <CalendarDays aria-hidden="true" />
                <input type="date" value={due} onChange={(event) => setDue(event.target.value)} />
              </span>
            </Field>
          </div>
          <Field label="Notes (optional)">
            <span className="management-input organization-textarea-shell">
              <FileText aria-hidden="true" />
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Shown at the bottom of the invoice"
                maxLength={1000}
              />
            </span>
          </Field>
          <div className="production-inline-actions">
            <button type="button" className="management-secondary-action" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="management-primary-action"
              disabled={saving || !clientId}
              onClick={() => void create()}
            >
              {saving && <RefreshCw className="spin" />}
              {saving ? "Creating…" : "Create draft"}
            </button>
          </div>
        </div>
      </Panel>
    </>
  );
}

/* ---------------------------------------------------------------------------------- detail */

function InvoiceDetailSheet({
  id,
  notice,
  onClose,
  onNotice,
  onChanged,
}: {
  id: string;
  notice: string;
  onClose: () => void;
  onNotice: (message: string) => void;
  onChanged: () => void;
}) {
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [notes, setNotes] = useState("");
  const [confirm, setConfirm] = useState<"void" | "delete" | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api<InvoiceDetail>(`/api/company/invoices/${id}`);
      setInvoice(data);
      setNotes(data.notes);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load the invoice."));
    }
  }, [id]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function run(label: string, action: () => Promise<string>) {
    setBusy(label);
    setError("");
    try {
      onNotice(await action());
      onChanged();
    } catch (requestError) {
      setError(errorText(requestError, "That did not work. Please try again."));
    } finally {
      setBusy("");
      setConfirm(null);
    }
  }

  if (!invoice) {
    return (
      <>
        <SheetHeader eyebrow="Invoice" title={error ? "Invoice not available" : "Loading…"} onClose={onClose} />
        {error ? (
          <div className="organization-state">
            <h3>{error}</h3>
            <button type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : (
          <div className="organization-skeleton">
            {[1, 2, 3].map((row) => (
              <i key={row} />
            ))}
          </div>
        )}
      </>
    );
  }

  const pdfUrl = `/api/company/invoices/${invoice.id}/pdf`;
  const balance = Number(invoice.balance);
  const editable = invoice.status !== "VOID";

  return (
    <>
      <SheetHeader
        eyebrow={`${invoice.code} · ${invoice.client.name}`}
        title={money(invoice.subtotal, invoice.currency)}
        onClose={onClose}
        badges={
          <>
            <em className={tone(invoice.status)}>{STATUS_LABELS[invoice.status]}</em>
            {invoice.source === "TOP_UP" && <em>Top-up period</em>}
            <em>
              {invoice.items} {invoice.items === 1 ? "item" : "items"}
            </em>
          </>
        }
        actions={
          <a className="management-secondary-action" href={`${pdfUrl}?download=true`}>
            <Download /> PDF
          </a>
        }
      />
      {notice && <div className="organization-notice">{notice}</div>}
      {error && <div className="organization-form-error">{error}</div>}

      <div className="invoice-actions">
        {editable && (
          <button
            type="button"
            className="management-primary-action"
            disabled={Boolean(busy)}
            onClick={() =>
              void run("send", async () => {
                const result = await api<{ invoice: InvoiceDetail; message: string }>(
                  `/api/company/invoices/${invoice.id}/send`,
                  { method: "POST" },
                );
                setInvoice(result.invoice);
                return `${invoice.code} sent. ${result.message}`;
              })
            }
          >
            {busy === "send" ? <RefreshCw className="spin" /> : <Send />}
            {invoice.status === "DRAFT" ? "Send to client" : "Send again"}
          </button>
        )}
        <a className="management-secondary-action" href={pdfUrl} target="_blank" rel="noreferrer">
          <ExternalLink /> Preview
        </a>
        {invoice.status === "SENT" && (
          <button
            type="button"
            className="management-secondary-action"
            disabled={Boolean(busy)}
            onClick={() =>
              void run("paid", async () => {
                setInvoice(
                  await api<InvoiceDetail>(`/api/company/invoices/${invoice.id}`, {
                    method: "PATCH",
                    json: { status: "PAID" },
                  }),
                );
                return `${invoice.code} marked as paid.`;
              })
            }
          >
            <CheckCircle2 /> Mark paid
          </button>
        )}
        {invoice.status === "DRAFT" ? (
          <button
            type="button"
            className="management-secondary-action invoice-danger"
            disabled={Boolean(busy)}
            onClick={() => setConfirm("delete")}
          >
            <Trash2 /> Delete draft
          </button>
        ) : (
          editable && (
            <button
              type="button"
              className="management-secondary-action invoice-danger"
              disabled={Boolean(busy)}
              onClick={() => setConfirm("void")}
            >
              <Ban /> Void
            </button>
          )
        )}
      </div>

      <Panel icon={<FileText />} eyebrow="SUMMARY" title={`${invoice.client.name} · ${invoice.code}`}>
        <div className="production-panel-body">
          <dl className="production-facts">
            <div>
              <dt>Work period</dt>
              <dd>
                {formatDate(invoice.period_start)} – {formatDate(invoice.period_end)}
              </dd>
            </div>
            <div>
              <dt>Issued</dt>
              <dd>{formatDate(invoice.issue_date)}</dd>
            </div>
            <div>
              <dt>Due</dt>
              <dd>{invoice.due_date ? formatDate(invoice.due_date) : "On receipt"}</dd>
            </div>
            <div>
              <dt>Client email</dt>
              <dd>{invoice.client_email ?? "—"}</dd>
            </div>
            <div>
              <dt>Subtotal</dt>
              <dd>{money(invoice.subtotal, invoice.currency)}</dd>
            </div>
            <div>
              <dt>Payments in period</dt>
              <dd>{money(invoice.payments_total, invoice.currency)}</dd>
            </div>
            {Number(invoice.budget_added) > 0 && (
              <div>
                <dt>Budget added in period</dt>
                <dd>{money(invoice.budget_added, invoice.currency)}</dd>
              </div>
            )}
            <div>
              <dt>{balance > 0 ? "Balance due" : balance < 0 ? "Credit" : "Balance"}</dt>
              <dd className={balance > 0 ? "invoice-balance" : undefined}>
                {balance === 0 ? "Settled" : money(Math.abs(balance), invoice.currency)}
              </dd>
            </div>
            <div>
              <dt>Made by</dt>
              <dd>
                {invoice.created_by_name}
                <small>{formatDateTime(invoice.created_at)}</small>
              </dd>
            </div>
            {invoice.sent_at && (
              <div>
                <dt>Sent</dt>
                <dd>{formatDateTime(invoice.sent_at)}</dd>
              </div>
            )}
          </dl>
        </div>
      </Panel>

      <Panel
        icon={<ReceiptText />}
        eyebrow="WORK"
        title={`${invoice.items} delivered ${invoice.items === 1 ? "item" : "items"}`}
      >
        <div className="production-panel-body">
          {invoice.lines.length === 0 ? (
            <p className="production-muted">No approved work in this period.</p>
          ) : (
            <div className="invoice-lines-wrap">
              <table className="invoice-lines">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Date</th>
                    <th>Work</th>
                    <th>Service</th>
                    <th className="num">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.lines.map((line) => (
                    <tr key={line.position}>
                      <td>{line.position}</td>
                      <td>{formatDate(line.delivered_on)}</td>
                      <td>{line.title}</td>
                      <td>{line.service_name}</td>
                      <td className="num">{money(line.amount, invoice.currency)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={4}>Subtotal</td>
                    <td className="num">{money(invoice.subtotal, invoice.currency)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </Panel>

      {invoice.payments.length > 0 && (
        <Panel icon={<CheckCircle2 />} eyebrow="PAYMENTS" title="Received in this period">
          <div className="production-panel-body">
            <ul className="production-list">
              {invoice.payments.map((payment, index) => (
                <li key={index}>
                  <div>
                    <strong>{money(payment.amount, invoice.currency)}</strong>
                    <small>
                      {formatDate(payment.received_on)} · {METHOD_LABELS[payment.method] ?? payment.method}
                      {payment.reference ? ` · ${payment.reference}` : ""}
                    </small>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </Panel>
      )}

      {editable && (
        <Panel icon={<FileText />} eyebrow="NOTES" title="Printed on the invoice">
          <div className="production-panel-body">
            <Field label="Notes">
              <span className="management-input organization-textarea-shell">
                <FileText aria-hidden="true" />
                <textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={1000} />
              </span>
            </Field>
            <div className="production-inline-actions">
              <button
                type="button"
                className="management-secondary-action"
                disabled={Boolean(busy) || notes === invoice.notes}
                onClick={() =>
                  void run("notes", async () => {
                    setInvoice(
                      await api<InvoiceDetail>(`/api/company/invoices/${invoice.id}`, {
                        method: "PATCH",
                        json: { notes },
                      }),
                    );
                    return "Notes saved.";
                  })
                }
              >
                Save notes
              </button>
            </div>
          </div>
        </Panel>
      )}

      <ConfirmationDialog
        open={confirm !== null}
        title={confirm === "delete" ? `Delete ${invoice.code}?` : `Void ${invoice.code}?`}
        description={
          confirm === "delete"
            ? "The draft is removed. You can make a new one at any time."
            : "The invoice stays on record but is marked void and no longer counts as due."
        }
        confirmLabel={confirm === "delete" ? "Delete draft" : "Void invoice"}
        tone="danger"
        loading={Boolean(busy)}
        onCancel={() => setConfirm(null)}
        onConfirm={() =>
          void run(confirm ?? "", async () => {
            if (confirm === "delete") {
              await api(`/api/company/invoices/${invoice.id}`, { method: "DELETE" });
              onClose();
              return `${invoice.code} deleted.`;
            }
            setInvoice(
              await api<InvoiceDetail>(`/api/company/invoices/${invoice.id}`, {
                method: "PATCH",
                json: { status: "VOID" },
              }),
            );
            return `${invoice.code} marked as void.`;
          })
        }
      />
    </>
  );
}
