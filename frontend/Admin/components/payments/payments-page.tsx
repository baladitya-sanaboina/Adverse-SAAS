"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowLeft,
  Banknote,
  CalendarDays,
  ClipboardList,
  FileText,
  Hash,
  HandCoins,
  History,
  PiggyBank,
  Plus,
  RefreshCw,
  Wallet,
} from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { Field, Panel, TableSkeleton } from "@/components/production/production-ui";
import {
  PAYMENT_METHOD_OPTIONS,
  STATUS_LABELS,
  api,
  errorText,
  formatDate,
  formatMonth,
  methodLabel,
  money,
  query,
  today,
} from "@/lib/production/client";
import type {
  BudgetEntryType,
  ClientBudget,
  ClientPayment,
  ClientReportRow,
  NamedRef,
  Paged,
  PaymentList,
  PaymentMethod,
  PersonFinance,
  Report,
  TeamReportRow,
} from "@/lib/production/types";
import "@/styles/organization.css";
import "@/styles/service-pricing-settings.css";
import "@/styles/production.css";

type Tab = "client-payments" | "budgets" | "salaries" | "payouts";
type ChoiceItem = { id: string; name: string; status?: string };

const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: "client-payments", label: "Client payments", icon: <Wallet /> },
  { id: "budgets", label: "Budgets", icon: <PiggyBank /> },
  { id: "salaries", label: "Salaries", icon: <Banknote /> },
  { id: "payouts", label: "Manager payouts", icon: <HandCoins /> },
];

const BUDGET_TYPE_OPTIONS: { value: BudgetEntryType; label: string }[] = [
  { value: "TOP_UP", label: "Top-up (add money)" },
  { value: "INITIAL", label: "Initial budget" },
  { value: "ADJUSTMENT", label: "Adjustment (can be negative)" },
];

function firstOfMonth(): string {
  return `${today().slice(0, 7)}-01`;
}

export function PaymentsPage() {
  const [tab, setTab] = useState<Tab>("client-payments");
  const [notice, setNotice] = useState("");

  return (
    <>
      <DashboardHero
        title=""
        highlight="Payments"
        description="Money received from clients, client budgets, salaries and manager commission payouts."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace" aria-live="polite">
          <nav className="production-tabs" aria-label="Payment sections">
            {TABS.map((item) => (
              <button
                type="button"
                key={item.id}
                className={tab === item.id ? "active" : ""}
                aria-pressed={tab === item.id}
                onClick={() => {
                  setTab(item.id);
                  setNotice("");
                }}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>
          {notice && <div className="organization-notice">{notice}</div>}
          {tab === "client-payments" && <ClientPaymentsTab onNotice={setNotice} />}
          {tab === "budgets" && <BudgetsTab onNotice={setNotice} />}
          {tab === "salaries" && <PeopleTab role="EMPLOYEE" onNotice={setNotice} />}
          {tab === "payouts" && <PeopleTab role="MANAGER" onNotice={setNotice} />}
        </section>
      </div>
    </>
  );
}

function StateBlock({ error, onRetry, children }: { error: string; onRetry: () => void; children?: ReactNode }) {
  return (
    <div className="organization-state">
      {children}
      <h3>{error}</h3>
      <button type="button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

function PaymentFields({
  values,
  onChange,
  dateLabel,
}: {
  values: { amount: string; date: string; method: PaymentMethod; reference: string; note: string };
  onChange: (key: "amount" | "date" | "method" | "reference" | "note", value: string) => void;
  dateLabel: string;
}) {
  return (
    <>
      <Field label="Amount">
        <span className="management-input">
          <Wallet aria-hidden="true" />
          <input
            type="number"
            min="0"
            step="0.01"
            value={values.amount}
            onChange={(event) => onChange("amount", event.target.value)}
            placeholder="0.00"
          />
        </span>
      </Field>
      <Field label={dateLabel}>
        <span className="management-input">
          <CalendarDays aria-hidden="true" />
          <input type="date" value={values.date} onChange={(event) => onChange("date", event.target.value)} />
        </span>
      </Field>
      <Field label="Method">
        <LooplessSelect
          value={values.method}
          onValueChange={(value) => onChange("method", value)}
          ariaLabel="Payment method"
          options={PAYMENT_METHOD_OPTIONS}
        />
      </Field>
      <Field label="Reference">
        <span className="management-input">
          <Hash aria-hidden="true" />
          <input
            value={values.reference}
            onChange={(event) => onChange("reference", event.target.value)}
            placeholder="UPI ref, cheque no."
            maxLength={200}
          />
        </span>
      </Field>
      <Field label="Note" wide>
        <span className="management-input">
          <FileText aria-hidden="true" />
          <input
            value={values.note}
            onChange={(event) => onChange("note", event.target.value)}
            placeholder="Optional"
            maxLength={500}
          />
        </span>
      </Field>
    </>
  );
}

const emptyPayment = () => ({
  amount: "",
  date: today(),
  method: "BANK_TRANSFER" as PaymentMethod,
  reference: "",
  note: "",
});

/* ------------------------------------------------------------------ client payments */

function ClientPaymentsTab({ onNotice }: { onNotice: (message: string) => void }) {
  const [data, setData] = useState<PaymentList<ClientPayment> | null>(null);
  const [clients, setClients] = useState<ChoiceItem[]>([]);
  const [client, setClient] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [removeItem, setRemoveItem] = useState<ClientPayment | null>(null);
  const [removing, setRemoving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(
        await api<PaymentList<ClientPayment>>(
          `/api/company/finance/client-payments${query({ client_id: client, page_size: 100 })}`,
        ),
      );
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load client payments."));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const result = await api<Paged<ChoiceItem> | ChoiceItem[]>("/api/company/clients?page_size=100");
        setClients(Array.isArray(result) ? result : result.items);
      } catch {
        // The filter falls back to "All clients".
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function remove() {
    if (!removeItem) return;
    setRemoving(true);
    try {
      await api(`/api/company/finance/client/${removeItem.id}`, { method: "DELETE" });
      onNotice("Payment deleted.");
      setRemoveItem(null);
      await load();
    } catch (requestError) {
      setError(errorText(requestError, "Unable to delete the payment."));
      setRemoveItem(null);
    } finally {
      setRemoving(false);
    }
  }

  if (creating) {
    return (
      <ClientPaymentForm
        clients={clients}
        defaultClient={client}
        onCancel={() => setCreating(false)}
        onSaved={(message) => {
          setCreating(false);
          onNotice(message);
          void load();
        }}
      />
    );
  }

  const currency = data?.items[0]?.currency;
  return (
    <>
      <header className="management-toolbar">
        <div>
          <span>Payments received from clients</span>
          <strong>
            {data ? `${data.total} ${data.total === 1 ? "payment" : "payments"}` : "Payments"}
            {data && data.total > 0 && ` · ${money(data.total_amount, currency)}`}
          </strong>
        </div>
        <button type="button" onClick={() => setCreating(true)}>
          <Plus /> Record payment
        </button>
      </header>
      <div className="organization-tools production-tools" style={{ ["--production-filters" as string]: 1 }}>
        <span aria-hidden="true" />
        <LooplessSelect
          value={client}
          onValueChange={setClient}
          ariaLabel="Filter payments by client"
          options={[
            { value: "", label: "All clients" },
            ...clients.map((item) => ({ value: item.id, label: item.name })),
          ]}
        />
      </div>
      {error ? (
        <StateBlock error={error} onRetry={() => void load()} />
      ) : loading ? (
        <TableSkeleton />
      ) : !data || data.items.length === 0 ? (
        <div className="organization-state">
          <Wallet />
          <h3>No payments recorded</h3>
          <p>Record money as it arrives from clients to track what is still pending.</p>
          <button type="button" onClick={() => setCreating(true)}>
            <Plus /> Record payment
          </button>
        </div>
      ) : (
        <div className="organization-table production-client-payments" role="table">
          <div className="organization-table-head">
            <span>Date</span>
            <span>Client</span>
            <span>Method</span>
            <span>Reference</span>
            <span className="production-money">Amount</span>
            <span>Actions</span>
          </div>
          {data.items.map((item) => (
            <article key={item.id}>
              <span>{formatDate(item.received_on)}</span>
              <div className="production-cell">
                <strong>{item.client.name}</strong>
                {item.note && <small>{item.note}</small>}
              </div>
              <span>{methodLabel(item.method)}</span>
              <span>{item.reference || "—"}</span>
              <span className="production-money">{money(item.amount, item.currency)}</span>
              <CrudActionButtons
                remove={{ label: `Delete payment from ${item.client.name}`, onClick: () => setRemoveItem(item) }}
              />
            </article>
          ))}
        </div>
      )}
      <ConfirmationDialog
        open={Boolean(removeItem)}
        title="Delete this payment?"
        description={`${removeItem ? money(removeItem.amount, removeItem.currency) : ""} from ${
          removeItem?.client.name ?? "the client"
        } will be removed, and their pending amount will go up again.`}
        confirmLabel="Delete payment"
        tone="danger"
        loading={removing}
        onCancel={() => setRemoveItem(null)}
        onConfirm={() => void remove()}
      />
    </>
  );
}

function ClientPaymentForm({
  clients,
  defaultClient,
  onCancel,
  onSaved,
}: {
  clients: ChoiceItem[];
  defaultClient: string;
  onCancel: () => void;
  onSaved: (message: string) => void;
}) {
  const [clientId, setClientId] = useState(defaultClient);
  const [values, setValues] = useState(emptyPayment);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!clientId) return setError("Choose the client who paid.");
    if (!values.amount || Number(values.amount) <= 0) return setError("Enter an amount greater than zero.");
    if (!values.date) return setError("Enter the date the payment was received.");
    setSaving(true);
    setError("");
    try {
      const payment = await api<ClientPayment>("/api/company/finance/client-payments", {
        method: "POST",
        json: {
          client_id: clientId,
          amount: values.amount,
          received_on: values.date,
          method: values.method,
          reference: values.reference.trim(),
          note: values.note.trim(),
        },
      });
      onSaved(`${money(payment.amount, payment.currency)} received from ${payment.client.name} recorded.`);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to record the payment."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <EditorShell
      back="Back to payments"
      label="New payment"
      icon={<Wallet />}
      eyebrow="RECORD PAYMENT"
      title="Payment received"
      description="Recording money from a client lowers their pending amount. It does not change their budget."
      onCancel={onCancel}
    >
      <form className="management-form organization-form-grid" noValidate onSubmit={save}>
        {error && <div className="management-form-message">{error}</div>}
        <Field label="Client" wide>
          <LooplessSelect
            value={clientId}
            onValueChange={setClientId}
            ariaLabel="Client"
            options={[
              { value: "", label: "Choose a client" },
              ...clients.map((item) => ({ value: item.id, label: item.name })),
            ]}
          />
        </Field>
        <PaymentFields
          values={values}
          dateLabel="Received on"
          onChange={(key, value) => setValues((current) => ({ ...current, [key]: value }))}
        />
        <FormFooter saving={saving} label="Record payment" onCancel={onCancel} />
      </form>
    </EditorShell>
  );
}

function EditorShell({
  back,
  label,
  icon,
  eyebrow,
  title,
  description,
  onCancel,
  children,
}: {
  back: string;
  label: string;
  icon: ReactNode;
  eyebrow: string;
  title: string;
  description: string;
  onCancel: () => void;
  children: ReactNode;
}) {
  return (
    <>
      <header className="management-toolbar">
        <button type="button" className="management-back" onClick={onCancel}>
          <ArrowLeft /> {back}
        </button>
        <span>{label}</span>
      </header>
      <section className="management-editor">
        <header>
          <i aria-hidden="true">{icon}</i>
          <div>
            <span>{eyebrow}</span>
            <h2>{title}</h2>
            <p>{description}</p>
          </div>
        </header>
        {children}
      </section>
    </>
  );
}

function FormFooter({ saving, label, onCancel }: { saving: boolean; label: string; onCancel?: () => void }) {
  return (
    <div className="management-form-footer">
      {onCancel && (
        <button type="button" className="management-secondary-action" onClick={onCancel}>
          Cancel
        </button>
      )}
      <button type="submit" className="management-primary-action" disabled={saving}>
        {saving && <RefreshCw className="spin" />}
        {saving ? "Saving…" : label}
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ budgets */

function BudgetsTab({ onNotice }: { onNotice: (message: string) => void }) {
  const [rows, setRows] = useState<ClientReportRow[]>([]);
  const [currency, setCurrency] = useState("INR");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<NamedRef | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const report = await api<Report<ClientReportRow>>("/api/company/finance/reports/clients?period=all");
      setRows(report.rows);
      setCurrency(report.currency);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load client budgets."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (open) {
    return (
      <BudgetDetail
        client={open}
        onBack={() => {
          setOpen(null);
          void load();
        }}
        onNotice={onNotice}
      />
    );
  }

  const withBudget = rows.filter((row) => Number(row.budget_total) > 0).length;
  return (
    <>
      <header className="management-toolbar">
        <div>
          <span>One-time client budgets</span>
          <strong>
            {withBudget} of {rows.length} clients have a budget
          </strong>
        </div>
      </header>
      {error ? (
        <StateBlock error={error} onRetry={() => void load()} />
      ) : loading ? (
        <TableSkeleton />
      ) : rows.length === 0 ? (
        <div className="organization-state">
          <PiggyBank />
          <h3>No clients yet</h3>
          <p>Add clients first, then set their budgets here.</p>
        </div>
      ) : (
        <div className="organization-table production-budgets" role="table">
          <div className="organization-table-head">
            <span>Client</span>
            <span className="production-money">Budget</span>
            <span className="production-money">Used</span>
            <span className="production-money">Remaining</span>
            <span className="production-money">Unpaid</span>
            <span>Actions</span>
          </div>
          {rows.map((row) => {
            // Period "all": billed is everything approved so far, which is what the budget is used by.
            const billed = Number(row.billed);
            const over = Number(row.budget_total) > 0 && billed > Number(row.budget_total);
            return (
              <article key={row.client.id}>
                <div className="production-cell">
                  <small>{row.client.code}</small>
                  <strong>{row.client.name}</strong>
                </div>
                <span className="production-money">
                  {Number(row.budget_total) > 0 ? money(row.budget_total, currency) : "Not set"}
                </span>
                <span className="production-money">{Number(row.budget_total) > 0 ? money(billed, currency) : "—"}</span>
                <span className={`production-money${over ? " production-overdue" : ""}`}>
                  {Number(row.budget_total) > 0 ? (over ? "Over budget" : money(row.budget_remaining, currency)) : "—"}
                </span>
                <span className="production-money">{money(row.pending, currency)}</span>
                <CrudActionButtons
                  view={{ label: `Open budget for ${row.client.name}`, onClick: () => setOpen(row.client) }}
                />
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}

function BudgetDetail({
  client,
  onBack,
  onNotice,
}: {
  client: NamedRef;
  onBack: () => void;
  onNotice: (message: string) => void;
}) {
  const [data, setData] = useState<ClientBudget | null>(null);
  const [error, setError] = useState("");
  const [values, setValues] = useState({ type: "TOP_UP" as BudgetEntryType, amount: "", note: "" });
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const result = await api<ClientBudget>(`/api/company/finance/budgets/${client.id}`);
      setData(result);
      if (result.entries.length === 0) setValues((current) => ({ ...current, type: "INITIAL" }));
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load the budget."));
    }
  }, [client.id]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function add(event: FormEvent) {
    event.preventDefault();
    const amount = Number(values.amount);
    if (!values.amount || amount === 0) return setFormError("Enter an amount.");
    if (values.type !== "ADJUSTMENT" && amount < 0) return setFormError("Use an adjustment to reduce the budget.");
    setSaving(true);
    setFormError("");
    try {
      const result = await api<ClientBudget>(`/api/company/finance/budgets/${client.id}/entries`, {
        method: "POST",
        json: { type: values.type, amount: values.amount, note: values.note.trim() },
      });
      setData(result);
      setValues({ type: "TOP_UP", amount: "", note: "" });
      onNotice(`Budget for ${client.name} updated.`);
    } catch (requestError) {
      setFormError(errorText(requestError, "Unable to update the budget."));
    } finally {
      setSaving(false);
    }
  }

  const budget = data?.budget;
  const currency = budget?.currency ?? "INR";
  return (
    <>
      <header className="management-toolbar">
        <button type="button" className="management-back" onClick={onBack}>
          <ArrowLeft /> Back to budgets
        </button>
        <span>{client.name}</span>
      </header>
      {error ? (
        <StateBlock error={error} onRetry={() => void load()} />
      ) : !data || !budget ? (
        <TableSkeleton />
      ) : (
        <>
          <div className="services-pricing-summary-grid production-summary">
            <article>
              <span>Budget</span>
              <strong>{budget.has_budget ? money(budget.total, currency) : "Not set"}</strong>
              <small>One-time amount, including top-ups</small>
            </article>
            <article>
              <span>Used</span>
              <strong>{money(budget.used, currency)}</strong>
              <small>Approved and completed work</small>
            </article>
            <article>
              <span>In progress</span>
              <strong>{money(budget.committed, currency)}</strong>
              <small>Assigned work not yet approved</small>
            </article>
            <article>
              <span>{Number(budget.overage) > 0 ? "Over budget" : "Remaining"}</span>
              <strong className={Number(budget.overage) > 0 ? "negative" : undefined}>
                {money(Number(budget.overage) > 0 ? budget.overage : budget.remaining, currency)}
              </strong>
              <small>{budget.message}</small>
            </article>
          </div>
          <div className="production-detail">
            <div>
              <Panel
                icon={<History />}
                eyebrow="HISTORY"
                title="Budget entries"
                description="Every amount added or adjusted, newest first."
              >
                <div className="production-panel-body">
                  {data.entries.length === 0 ? (
                    <p className="production-muted">No budget set yet.</p>
                  ) : (
                    <ul className="production-list">
                      {data.entries.map((entry) => (
                        <li key={entry.id}>
                          <div>
                            <strong>
                              {BUDGET_TYPE_OPTIONS.find((option) => option.value === entry.type)?.label.split(" (")[0]}
                            </strong>
                            {entry.note && <p>{entry.note}</p>}
                            <small>
                              {entry.created_by_name} · {formatDate(entry.created_at)}
                            </small>
                          </div>
                          <b>{money(entry.amount, entry.currency)}</b>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </Panel>
            </div>
            <div>
              <Panel
                icon={<PiggyBank />}
                eyebrow="ADD MONEY"
                title={data.entries.length === 0 ? "Set the budget" : "Top up or adjust"}
                description="Tasks above the budget are still allowed; you get a warning when assigning them."
              >
                <form className="management-form" noValidate onSubmit={add}>
                  {formError && <div className="management-form-message">{formError}</div>}
                  <Field label="Type" wide>
                    <LooplessSelect
                      value={values.type}
                      onValueChange={(value) => setValues({ ...values, type: value as BudgetEntryType })}
                      ariaLabel="Budget entry type"
                      options={BUDGET_TYPE_OPTIONS}
                    />
                  </Field>
                  <Field label={`Amount (${currency})`} wide>
                    <span className="management-input">
                      <Wallet aria-hidden="true" />
                      <input
                        type="number"
                        step="0.01"
                        value={values.amount}
                        onChange={(event) => setValues({ ...values, amount: event.target.value })}
                        placeholder="0.00"
                      />
                    </span>
                  </Field>
                  <Field label="Note" wide>
                    <span className="management-input">
                      <FileText aria-hidden="true" />
                      <input
                        value={values.note}
                        onChange={(event) => setValues({ ...values, note: event.target.value })}
                        placeholder="For example: advance for December"
                        maxLength={500}
                      />
                    </span>
                  </Field>
                  <FormFooter saving={saving} label="Save" />
                </form>
              </Panel>
            </div>
          </div>
        </>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ salaries & payouts */

function PeopleTab({ role, onNotice }: { role: "EMPLOYEE" | "MANAGER"; onNotice: (message: string) => void }) {
  const [rows, setRows] = useState<TeamReportRow[]>([]);
  const [currency, setCurrency] = useState("INR");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const isManager = role === "MANAGER";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const report = await api<Report<TeamReportRow>>("/api/company/finance/reports/team?period=all");
      setRows(report.rows.filter((row) => row.person.role === role));
      setCurrency(report.currency);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load the team."));
    } finally {
      setLoading(false);
    }
  }, [role]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (openId) {
    return (
      <PersonDetail
        userId={openId}
        onBack={() => {
          setOpenId(null);
          void load();
        }}
        onNotice={onNotice}
      />
    );
  }

  const pending = rows.reduce((sum, row) => sum + Number(row.pending), 0);
  return (
    <>
      <header className="management-toolbar">
        <div>
          <span>{isManager ? "Commission per task, paid to managers" : "Monthly salaries for employees"}</span>
          <strong>
            {rows.length}{" "}
            {isManager ? (rows.length === 1 ? "manager" : "managers") : rows.length === 1 ? "employee" : "employees"}
            {rows.length > 0 && ` · ${money(pending, currency)} pending`}
          </strong>
        </div>
      </header>
      {error ? (
        <StateBlock error={error} onRetry={() => void load()} />
      ) : loading ? (
        <TableSkeleton />
      ) : rows.length === 0 ? (
        <div className="organization-state">
          {isManager ? <HandCoins /> : <Banknote />}
          <h3>No {isManager ? "managers" : "employees"} yet</h3>
          <p>Add team members from Employees first.</p>
        </div>
      ) : (
        <div className="organization-table production-people" role="table">
          <div className="organization-table-head">
            <span>{isManager ? "Manager" : "Employee"}</span>
            <span className="production-money">{isManager ? "Earned" : "Salary due"}</span>
            <span className="production-money">Paid</span>
            <span className="production-money">Pending</span>
            <span className="production-money">Open tasks</span>
            <span>Actions</span>
          </div>
          {rows.map((row) => (
            <article key={row.person.id}>
              <div className="production-cell">
                <small>{isManager ? "Manager" : "Employee"}</small>
                <strong>{row.person.name}</strong>
              </div>
              <span className="production-money">{money(row.earnings, currency)}</span>
              <span className="production-money">{money(row.paid, currency)}</span>
              <span className={`production-money${Number(row.pending) > 0 ? " production-overdue" : ""}`}>
                {money(row.pending, currency)}
              </span>
              <span className="production-money">{row.open_tasks}</span>
              <CrudActionButtons view={{ label: `Open ${row.person.name}`, onClick: () => setOpenId(row.person.id) }} />
            </article>
          ))}
        </div>
      )}
    </>
  );
}

function PersonDetail({
  userId,
  onBack,
  onNotice,
}: {
  userId: string;
  onBack: () => void;
  onNotice: (message: string) => void;
}) {
  const [data, setData] = useState<PersonFinance | null>(null);
  const [error, setError] = useState("");
  const [removeId, setRemoveId] = useState<{ kind: "salary" | "payout"; id: string } | null>(null);
  const [removing, setRemoving] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await api<PersonFinance>(`/api/company/finance/people/${userId}`));
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load this person."));
    }
  }, [userId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function remove() {
    if (!removeId) return;
    setRemoving(true);
    try {
      await api(`/api/company/finance/${removeId.kind}/${removeId.id}`, { method: "DELETE" });
      setRemoveId(null);
      onNotice("Payment deleted.");
      await load();
    } catch (requestError) {
      setRemoveId(null);
      setError(errorText(requestError, "Unable to delete the payment."));
    } finally {
      setRemoving(false);
    }
  }

  const isManager = data?.person.role === "MANAGER";
  return (
    <>
      <header className="management-toolbar">
        <button type="button" className="management-back" onClick={onBack}>
          <ArrowLeft /> {isManager ? "Back to manager payouts" : "Back to salaries"}
        </button>
        <span>{data?.person.name ?? ""}</span>
      </header>
      {error ? (
        <StateBlock error={error} onRetry={() => void load()} />
      ) : !data ? (
        <TableSkeleton />
      ) : data.manager ? (
        <ManagerFinance
          data={data}
          onReload={load}
          onNotice={onNotice}
          onRemove={(id) => setRemoveId({ kind: "payout", id })}
        />
      ) : data.employee ? (
        <EmployeeFinance
          data={data}
          onReload={load}
          onNotice={onNotice}
          onRemove={(id) => setRemoveId({ kind: "salary", id })}
        />
      ) : null}
      <ConfirmationDialog
        open={Boolean(removeId)}
        title="Delete this payment?"
        description="Use this only for a payment recorded by mistake. The pending amount will go up again."
        confirmLabel="Delete payment"
        tone="danger"
        loading={removing}
        onCancel={() => setRemoveId(null)}
        onConfirm={() => void remove()}
      />
    </>
  );
}

function ManagerFinance({
  data,
  onReload,
  onNotice,
  onRemove,
}: {
  data: PersonFinance;
  onReload: () => Promise<void>;
  onNotice: (message: string) => void;
  onRemove: (id: string) => void;
}) {
  const earnings = data.manager!;
  const currency = earnings.currency;
  const [values, setValues] = useState(() => ({
    ...emptyPayment(),
    amount: Number(earnings.pending) > 0 ? earnings.pending : "",
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!values.amount || Number(values.amount) <= 0) return setError("Enter an amount greater than zero.");
    if (!values.date) return setError("Enter the date it was paid.");
    setSaving(true);
    setError("");
    try {
      await api("/api/company/finance/manager-payouts", {
        method: "POST",
        json: {
          manager_user_id: data.person.id,
          amount: values.amount,
          paid_on: values.date,
          method: values.method,
          reference: values.reference.trim(),
          note: values.note.trim(),
        },
      });
      onNotice(`${money(values.amount, currency)} paid to ${data.person.name} recorded.`);
      setValues({ ...emptyPayment(), amount: "" });
      await onReload();
    } catch (requestError) {
      setError(errorText(requestError, "Unable to record the payout."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="services-pricing-summary-grid production-summary">
        <article>
          <span>Earned</span>
          <strong>{money(earnings.earned, currency)}</strong>
          <small>Commission on approved and completed tasks</small>
        </article>
        <article>
          <span>Coming</span>
          <strong>{money(earnings.upcoming, currency)}</strong>
          <small>Assigned tasks not yet approved</small>
        </article>
        <article>
          <span>Paid</span>
          <strong>{money(earnings.paid, currency)}</strong>
          <small>All payouts recorded</small>
        </article>
        <article>
          <span>Pending</span>
          <strong className={Number(earnings.pending) > 0 ? "negative" : undefined}>
            {money(earnings.pending, currency)}
          </strong>
          <small>Earned minus paid</small>
        </article>
      </div>
      <div className="production-detail">
        <div>
          <Panel
            icon={<ClipboardList />}
            eyebrow="COMMISSION"
            title="Tasks"
            description="Commission is earned when you approve a task."
          >
            <div className="production-panel-body">
              {earnings.tasks.length === 0 ? (
                <p className="production-muted">No tasks assigned yet.</p>
              ) : (
                <ul className="production-list">
                  {earnings.tasks.map((task) => (
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
          <Panel icon={<History />} eyebrow="PAYOUTS" title="Paid to this manager">
            <div className="production-panel-body">
              {earnings.payouts.length === 0 ? (
                <p className="production-muted">No payouts recorded yet.</p>
              ) : (
                <ul className="production-list">
                  {earnings.payouts.map((payout) => (
                    <li key={payout.id}>
                      <div>
                        <strong>{formatDate(payout.paid_on)}</strong>
                        <small>
                          {methodLabel(payout.method)}
                          {payout.reference ? ` · ${payout.reference}` : ""}
                          {payout.note ? ` · ${payout.note}` : ""}
                        </small>
                      </div>
                      <span className="production-inline-actions">
                        <b>{money(payout.amount, payout.currency)}</b>
                        <CrudActionButtons remove={{ label: "Delete payout", onClick: () => onRemove(payout.id) }} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </div>
        <div>
          <Panel
            icon={<HandCoins />}
            eyebrow="RECORD PAYOUT"
            title={`Pay ${data.person.name}`}
            description="The amount is filled with what is pending. Change it for part payments."
          >
            <form className="management-form" noValidate onSubmit={save}>
              {error && <div className="management-form-message">{error}</div>}
              <PaymentFields
                values={values}
                dateLabel="Paid on"
                onChange={(key, value) => setValues((current) => ({ ...current, [key]: value }))}
              />
              <FormFooter saving={saving} label="Record payout" />
            </form>
          </Panel>
        </div>
      </div>
    </>
  );
}

function EmployeeFinance({
  data,
  onReload,
  onNotice,
  onRemove,
}: {
  data: PersonFinance;
  onReload: () => Promise<void>;
  onNotice: (message: string) => void;
  onRemove: (id: string) => void;
}) {
  const salary = data.employee!;
  const currency = salary.currency;
  const currentMonth = firstOfMonth();
  const monthLine = useMemo(
    () => salary.months.find((line) => line.month === currentMonth),
    [salary.months, currentMonth],
  );
  const [salaryValues, setSalaryValues] = useState({
    amount: salary.current_monthly_salary ?? "",
    from: currentMonth,
    note: "",
  });
  const [payment, setPayment] = useState(() => ({
    ...emptyPayment(),
    month: currentMonth.slice(0, 7),
    amount: monthLine && Number(monthLine.pending) > 0 ? monthLine.pending : "",
  }));
  const [savingSalary, setSavingSalary] = useState(false);
  const [savingPayment, setSavingPayment] = useState(false);
  const [salaryError, setSalaryError] = useState("");
  const [paymentError, setPaymentError] = useState("");

  async function saveSalary(event: FormEvent) {
    event.preventDefault();
    if (salaryValues.amount === "" || Number(salaryValues.amount) < 0)
      return setSalaryError("Enter the monthly salary.");
    if (!salaryValues.from) return setSalaryError("Enter the date it starts from.");
    setSavingSalary(true);
    setSalaryError("");
    try {
      await api(`/api/company/finance/people/${data.person.id}/salary`, {
        method: "PUT",
        json: {
          monthly_amount: salaryValues.amount,
          effective_from: salaryValues.from,
          note: salaryValues.note.trim(),
        },
      });
      onNotice(`Salary for ${data.person.name} set to ${money(salaryValues.amount, currency)} a month.`);
      await onReload();
    } catch (requestError) {
      setSalaryError(errorText(requestError, "Unable to save the salary."));
    } finally {
      setSavingSalary(false);
    }
  }

  async function savePayment(event: FormEvent) {
    event.preventDefault();
    if (!payment.month) return setPaymentError("Choose the month this payment is for.");
    if (!payment.amount || Number(payment.amount) <= 0) return setPaymentError("Enter an amount greater than zero.");
    if (!payment.date) return setPaymentError("Enter the date it was paid.");
    setSavingPayment(true);
    setPaymentError("");
    try {
      await api("/api/company/finance/salary-payments", {
        method: "POST",
        json: {
          user_id: data.person.id,
          period_month: `${payment.month}-01`,
          amount: payment.amount,
          paid_on: payment.date,
          method: payment.method,
          reference: payment.reference.trim(),
          note: payment.note.trim(),
        },
      });
      onNotice(`${money(payment.amount, currency)} salary paid to ${data.person.name} recorded.`);
      await onReload();
    } catch (requestError) {
      setPaymentError(errorText(requestError, "Unable to record the salary payment."));
    } finally {
      setSavingPayment(false);
    }
  }

  return (
    <>
      <div className="services-pricing-summary-grid production-summary">
        <article>
          <span>Monthly salary</span>
          <strong>{salary.current_monthly_salary ? money(salary.current_monthly_salary, currency) : "Not set"}</strong>
          <small>Current rate</small>
        </article>
        <article>
          <span>Total due</span>
          <strong>{money(salary.total_due, currency)}</strong>
          <small>All months up to this one</small>
        </article>
        <article>
          <span>Paid</span>
          <strong>{money(salary.total_paid, currency)}</strong>
          <small>All salary payments</small>
        </article>
        <article>
          <span>Pending</span>
          <strong className={Number(salary.pending) > 0 ? "negative" : undefined}>
            {money(salary.pending, currency)}
          </strong>
          <small>Due minus paid</small>
        </article>
      </div>
      <div className="production-detail">
        <div>
          <Panel icon={<CalendarDays />} eyebrow="MONTHS" title="Salary by month" description="Newest first.">
            <div className="production-panel-body">
              {salary.months.length === 0 ? (
                <p className="production-muted">Set a salary to start tracking months.</p>
              ) : (
                <ul className="production-list">
                  {salary.months.map((line) => (
                    <li key={line.month}>
                      <div>
                        <strong>{formatMonth(line.month)}</strong>
                        <small>
                          Due {money(line.due, currency)} · paid {money(line.paid, currency)}
                        </small>
                      </div>
                      <b className={Number(line.pending) > 0 ? "production-overdue" : undefined}>
                        {Number(line.pending) > 0 ? `${money(line.pending, currency)} pending` : "Paid"}
                      </b>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
          <Panel icon={<History />} eyebrow="PAYMENTS" title="Salary payments">
            <div className="production-panel-body">
              {salary.payments.length === 0 ? (
                <p className="production-muted">No salary payments recorded yet.</p>
              ) : (
                <ul className="production-list">
                  {salary.payments.map((item) => (
                    <li key={item.id}>
                      <div>
                        <strong>{formatMonth(item.period_month)}</strong>
                        <small>
                          Paid {formatDate(item.paid_on)} · {methodLabel(item.method)}
                          {item.reference ? ` · ${item.reference}` : ""}
                        </small>
                      </div>
                      <span className="production-inline-actions">
                        <b>{money(item.amount, item.currency)}</b>
                        <CrudActionButtons
                          remove={{ label: "Delete salary payment", onClick: () => onRemove(item.id) }}
                        />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </div>
        <div>
          <Panel icon={<Banknote />} eyebrow="RECORD PAYMENT" title={`Pay ${data.person.name}`}>
            <form className="management-form" noValidate onSubmit={savePayment}>
              {paymentError && <div className="management-form-message">{paymentError}</div>}
              <Field label="For month" wide>
                <span className="management-input">
                  <CalendarDays aria-hidden="true" />
                  <input
                    type="month"
                    value={payment.month}
                    onChange={(event) => setPayment({ ...payment, month: event.target.value })}
                  />
                </span>
              </Field>
              <PaymentFields
                values={payment}
                dateLabel="Paid on"
                onChange={(key, value) => setPayment((current) => ({ ...current, [key]: value }))}
              />
              <FormFooter saving={savingPayment} label="Record salary payment" />
            </form>
          </Panel>
          <Panel
            icon={<Wallet />}
            eyebrow="SALARY"
            title="Set monthly salary"
            description="A new salary starts from the date you choose. Earlier months keep their old salary."
          >
            <form className="management-form" noValidate onSubmit={saveSalary}>
              {salaryError && <div className="management-form-message">{salaryError}</div>}
              <Field label={`Monthly salary (${currency})`} wide>
                <span className="management-input">
                  <Wallet aria-hidden="true" />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={salaryValues.amount}
                    onChange={(event) => setSalaryValues({ ...salaryValues, amount: event.target.value })}
                    placeholder="0.00"
                  />
                </span>
              </Field>
              <Field label="Starts from" wide>
                <span className="management-input">
                  <CalendarDays aria-hidden="true" />
                  <input
                    type="date"
                    value={salaryValues.from}
                    onChange={(event) => setSalaryValues({ ...salaryValues, from: event.target.value })}
                  />
                </span>
              </Field>
              <Field label="Note" wide>
                <span className="management-input">
                  <FileText aria-hidden="true" />
                  <input
                    value={salaryValues.note}
                    onChange={(event) => setSalaryValues({ ...salaryValues, note: event.target.value })}
                    placeholder="For example: yearly raise"
                    maxLength={500}
                  />
                </span>
              </Field>
              <FormFooter saving={savingSalary} label="Save salary" />
              {data.salary_history.length > 0 && (
                <ul className="production-list wide" style={{ gridColumn: "1 / -1" }}>
                  {data.salary_history.map((record) => (
                    <li key={record.id}>
                      <div>
                        <strong>{money(record.monthly_amount, record.currency)} a month</strong>
                        <small>
                          From {formatDate(record.effective_from)}
                          {record.effective_to ? ` to ${formatDate(record.effective_to)}` : " · current"}
                          {record.note ? ` · ${record.note}` : ""}
                        </small>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </form>
          </Panel>
        </div>
      </div>
    </>
  );
}
