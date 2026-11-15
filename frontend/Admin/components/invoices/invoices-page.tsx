"use client";

/*
 * Invoices (Phase 11, owner request 2026-11-14). A draft is prepared automatically when a client's
 * payment sheet is complete (2026-11-15, numbered ADV-0001 on, with GST when the client has it);
 * the Admin can also make one for any payment sheet, client and period. Each invoice lists
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
  source: "MANUAL" | "TOP_UP" | "SHEET";
  client: { id: string; name: string; code: string };
  client_email: string | null;
  period_start: string;
  period_end: string;
  issue_date: string;
  due_date: string | null;
  currency: string;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  client_gstin: string;
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
  paid: string;
  used: string;
  left: string;
  items: number;
  ran_out_on: string | null;
  invoice_id?: string | null;
  invoice_code?: string | null;
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
              A draft is prepared automatically when a client&apos;s payment sheet is complete. You can also make one
              for any period.
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
                    {invoice.source === "TOP_UP" ? " · top-up" : invoice.source === "SHEET" ? " · payment sheet" : ""}
                  </small>
                  <strong>{invoice.code}</strong>
                </div>
                <span>{invoice.client.name}</span>
                <span>{invoice.items}</span>
                <span className="production-money">{money(invoice.total, invoice.currency)}</span>
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

type Preview = {
  period_start: string;
  period_end: string;
  currency: string;
  items: number;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  payments_total: string;
  budget_added: string;
  lines: { position: number; delivered_on: string; title: string; service_name: string; amount: string }[];
};
type Range = "topup" | "this-month" | "last-month" | "custom";

function isoDay(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** Start and end (ISO days) of this or last month, in the browser's local time. */
function monthRange(offset: 0 | -1): [string, string] {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const last = offset === 0 ? now : new Date(now.getFullYear(), now.getMonth(), 0);
  return [isoDay(first), isoDay(last)];
}

/*
 * Create invoice, simplified on owner request (2026-11-14): pick the client, pick what to bill
 * (a top-up, this month, last month or any dates), see the exact videos and total before saving,
 * then save a draft or create and email it in one click.
 */
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
  const [range, setRange] = useState<Range>("topup");
  const [cycles, setCycles] = useState<Cycle[] | null>(null);
  const [cycleIndex, setCycleIndex] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [due, setDue] = useState("");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState<"" | "draft" | "send">("");
  const [error, setError] = useState("");

  const today = isoDay(new Date());

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setCycles(null);
      setCycleIndex("");
      try {
        const data = await api<Cycle[]>(`/api/company/finance/sheets/clients/${clientId}`);
        if (cancelled) return;
        setCycles(data);
        const next = [...data].reverse().find((cycle) => !cycle.invoice_id) ?? data[data.length - 1];
        setCycleIndex(next ? String(next.index) : "");
        setRange(data.length ? "topup" : "this-month");
      } catch {
        if (!cancelled) setCycles([]);
      }
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [clientId]);

  const chosen = cycles?.find((cycle) => String(cycle.index) === cycleIndex) ?? null;
  const [periodStart, periodEnd] = useMemo((): [string, string] => {
    if (range === "topup") return chosen ? [chosen.start, chosen.end ?? today] : ["", ""];
    // (A payment sheet runs from its payment to the day before the next one.)
    if (range === "this-month") return monthRange(0);
    if (range === "last-month") return monthRange(-1);
    return [start, end];
  }, [range, chosen, start, end, today]);
  const periodError =
    periodStart && periodEnd && periodEnd < periodStart ? "The end date is before the start date." : "";

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPreview(null);
      if (!clientId || !periodStart || !periodEnd || periodEnd < periodStart) return;
      setPreviewing(true);
      try {
        const data = await api<Preview>(
          `/api/company/invoices/preview${query({ client_id: clientId, start: periodStart, end: periodEnd })}`,
        );
        if (!cancelled) setPreview(data);
      } catch (requestError) {
        if (!cancelled) setError(errorText(requestError, "Unable to preview the invoice."));
      } finally {
        if (!cancelled) setPreviewing(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [clientId, periodStart, periodEnd]);

  async function create(send: boolean) {
    setError("");
    if (!clientId) return setError("Choose a client.");
    if (!periodStart || !periodEnd) return setError("Choose what to bill.");
    if (periodError) return setError(periodError);
    setSaving(send ? "send" : "draft");
    try {
      let invoice: InvoiceDetail;
      if (range === "topup" && chosen) {
        // One invoice per payment sheet: made here, or the one already made is opened.
        invoice = await api<InvoiceDetail>("/api/company/invoices/sheet", {
          method: "POST",
          json: { client_id: clientId, start: chosen.start },
        });
        if ((due || notes.trim()) && invoice.status === "DRAFT") {
          invoice = await api<InvoiceDetail>(`/api/company/invoices/${invoice.id}`, {
            method: "PATCH",
            json: { due_date: due || null, notes: notes.trim() },
          });
        }
      } else {
        invoice = await api<InvoiceDetail>("/api/company/invoices", {
          method: "POST",
          json: {
            client_id: clientId,
            period_start: periodStart,
            period_end: periodEnd,
            due_date: due || null,
            notes: notes.trim(),
          },
        });
      }
      const count = `${invoice.items} ${invoice.items === 1 ? "video" : "videos"}`;
      if (!send) return onCreated(invoice.id, `${invoice.code} saved as a draft with ${count}.`);
      try {
        const result = await api<{ message: string }>(`/api/company/invoices/${invoice.id}/send`, { method: "POST" });
        onCreated(invoice.id, `${invoice.code} created and sent (${count}). ${result.message}`);
      } catch (sendError) {
        onCreated(
          invoice.id,
          `${invoice.code} was saved as a draft but not sent: ${errorText(sendError, "sending failed")}.`,
        );
      }
    } catch (requestError) {
      setError(errorText(requestError, "Unable to create the invoice."));
    } finally {
      setSaving("");
    }
  }

  const ranges: { value: Range; label: string; disabled?: boolean }[] = [
    { value: "topup", label: "A payment sheet", disabled: !cycles?.length },
    { value: "this-month", label: "This month" },
    { value: "last-month", label: "Last month" },
    { value: "custom", label: "Pick dates" },
  ];
  const shown = preview?.lines.slice(0, 6) ?? [];
  const balance = preview ? Number(preview.total) - Number(preview.payments_total) : 0;

  return (
    <>
      <SheetHeader eyebrow="New invoice" title="Create invoice" onClose={onClose} />
      <Panel
        icon={<ReceiptText />}
        eyebrow="STEP 1 AND 2"
        title="Who and what to bill"
        description="Every video approved in the chosen dates goes on the invoice."
      >
        <div className="production-panel-body">
          {error && <div className="management-form-message">{error}</div>}
          <Field label="Client">
            <LooplessSelect
              value={clientId}
              onValueChange={(value) => {
                setError("");
                setClientId(value);
              }}
              ariaLabel="Client"
              options={[
                { value: "", label: "Choose a client" },
                ...clients.filter((c) => c.status !== "INACTIVE").map((c) => ({ value: c.id, label: c.name })),
              ]}
            />
          </Field>
          {clientId && (
            <Field label="Bill for">
              <div className="invoice-range" role="radiogroup" aria-label="Bill for">
                {ranges.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={range === option.value}
                    className={range === option.value ? "active" : ""}
                    disabled={option.disabled}
                    onClick={() => {
                      setError("");
                      setRange(option.value);
                    }}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </Field>
          )}
          {clientId && range === "topup" && cycles && cycles.length > 0 && (
            <Field label="Payment sheet">
              <LooplessSelect
                value={cycleIndex}
                onValueChange={setCycleIndex}
                ariaLabel="Payment sheet"
                options={[...cycles].reverse().map((cycle) => ({
                  value: String(cycle.index),
                  label: `Sheet ${cycle.index} · ${formatDate(cycle.start)} – ${
                    cycle.end ? formatDate(cycle.end) : "now"
                  } · ${cycle.items} ${cycle.items === 1 ? "video" : "videos"}${
                    cycle.invoice_code ? ` · ${cycle.invoice_code} made` : ""
                  }`,
                }))}
              />
            </Field>
          )}
          {clientId && range === "custom" && (
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
          {chosen?.invoice_code && range === "topup" && (
            <p className="invoice-hint">{chosen.invoice_code} was already made for this sheet; saving opens it.</p>
          )}
          {periodError && <p className="invoice-hint error">{periodError}</p>}
        </div>
      </Panel>

      {clientId && periodStart && periodEnd && !periodError && (
        <Panel
          icon={<FileText />}
          eyebrow="STEP 3"
          title="Check and create"
          description={`${formatDate(periodStart)} – ${formatDate(periodEnd)}`}
        >
          <div className="production-panel-body">
            {!preview ? (
              <p className="production-muted">{previewing ? "Working out the invoice…" : "No preview yet."}</p>
            ) : (
              <>
                <div className="invoice-preview-total">
                  <span>
                    <small>
                      {preview.items} {preview.items === 1 ? "video" : "videos"}
                    </small>
                    <strong>{money(preview.subtotal, preview.currency)}</strong>
                  </span>
                  {Number(preview.tax_amount) > 0 && (
                    <span>
                      <small>GST @ {Number(preview.tax_rate)}%</small>
                      <strong>{money(preview.tax_amount, preview.currency)}</strong>
                    </span>
                  )}
                  {Number(preview.payments_total) > 0 && (
                    <span>
                      <small>Paid in these dates</small>
                      <strong>{money(preview.payments_total, preview.currency)}</strong>
                    </span>
                  )}
                  <span>
                    <small>{balance > 0 ? "Balance due" : "Balance"}</small>
                    <strong>{money(Math.max(balance, 0), preview.currency)}</strong>
                  </span>
                </div>
                {preview.items === 0 ? (
                  <p className="invoice-hint">No approved videos in these dates. The invoice would be empty.</p>
                ) : (
                  <ol className="invoice-preview-lines">
                    {shown.map((line) => (
                      <li key={line.position}>
                        <span>
                          <strong>{line.title}</strong>
                          <small>
                            {formatDate(line.delivered_on)} · {line.service_name}
                          </small>
                        </span>
                        <em>{money(line.amount, preview.currency)}</em>
                      </li>
                    ))}
                    {preview.lines.length > shown.length && (
                      <li className="more">+ {preview.lines.length - shown.length} more on the invoice</li>
                    )}
                  </ol>
                )}
              </>
            )}
            <details className="invoice-more">
              <summary>Due date and notes (optional)</summary>
              <div className="invoice-dates">
                <Field label="Due date">
                  <span className="management-input">
                    <CalendarDays aria-hidden="true" />
                    <input type="date" value={due} onChange={(event) => setDue(event.target.value)} />
                  </span>
                </Field>
              </div>
              <Field label="Notes">
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
            </details>
            <div className="production-inline-actions">
              <button type="button" className="management-secondary-action" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                className="management-secondary-action"
                disabled={Boolean(saving) || !preview || preview.items === 0}
                onClick={() => void create(false)}
              >
                {saving === "draft" && <RefreshCw className="spin" />}
                Save draft
              </button>
              <button
                type="button"
                className="management-primary-action"
                disabled={Boolean(saving) || !preview || preview.items === 0}
                onClick={() => void create(true)}
              >
                {saving === "send" ? <RefreshCw className="spin" /> : <Send />}
                {saving === "send" ? "Sending…" : "Create and email"}
              </button>
            </div>
          </div>
        </Panel>
      )}
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
        title={money(invoice.total, invoice.currency)}
        onClose={onClose}
        badges={
          <>
            <em className={tone(invoice.status)}>{STATUS_LABELS[invoice.status]}</em>
            {invoice.source === "TOP_UP" && <em>Top-up period</em>}
            {invoice.source === "SHEET" && <em>Payment sheet</em>}
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
            {Number(invoice.tax_amount) > 0 && (
              <>
                <div>
                  <dt>GST @ {Number(invoice.tax_rate)}%</dt>
                  <dd>{money(invoice.tax_amount, invoice.currency)}</dd>
                </div>
                <div>
                  <dt>Total with GST</dt>
                  <dd>{money(invoice.total, invoice.currency)}</dd>
                </div>
              </>
            )}
            {invoice.client_gstin && (
              <div>
                <dt>Client GSTIN</dt>
                <dd>{invoice.client_gstin}</dd>
              </div>
            )}
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
                  {Number(invoice.tax_amount) > 0 && (
                    <>
                      <tr>
                        <td colSpan={4}>GST @ {Number(invoice.tax_rate)}%</td>
                        <td className="num">{money(invoice.tax_amount, invoice.currency)}</td>
                      </tr>
                      <tr>
                        <td colSpan={4}>Total</td>
                        <td className="num">{money(invoice.total, invoice.currency)}</td>
                      </tr>
                    </>
                  )}
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
