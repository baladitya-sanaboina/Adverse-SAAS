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
import { AdvanceWallet } from "@loopless-shared/workspace/advance-wallet";
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
  AssigneeOption,
  BudgetEntryType,
  ClientBudget,
  ClientPayment,
  ClientReportRow,
  ManagerPayout,
  NamedRef,
  Paged,
  PaymentList,
  PaymentMethod,
  PersonFinance,
  Report,
  SalaryPayment,
  SalaryRecord,
  TeamReportRow,
} from "@/lib/production/types";
import "@/styles/organization.css";
import "@/styles/service-pricing-settings.css";
import "@/styles/production.css";
import { LooplessDate } from "@/components/foundation/loopless-date";

type Tab = "client-payments" | "budgets" | "salaries" | "payouts";
type ChoiceItem = { id: string; name: string; status?: string };
type PaymentKind = "client" | "salary" | "payout";
type AnyPayment = ClientPayment | SalaryPayment | ManagerPayout;

const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: "client-payments", label: "Client payments", icon: <Wallet /> },
  { id: "budgets", label: "Budgets", icon: <PiggyBank /> },
  { id: "salaries", label: "Salaries", icon: <Banknote /> },
  { id: "payouts", label: "Manager top-ups", icon: <HandCoins /> },
];

const BUDGET_TYPE_OPTIONS: { value: BudgetEntryType; label: string }[] = [
  { value: "TOP_UP", label: "Top-up (add money)" },
  { value: "INITIAL", label: "Initial budget" },
  { value: "ADJUSTMENT", label: "Adjustment (can be negative)" },
];

/** Where each kind of payment lives in the API. */
const PAYMENT_API: Record<PaymentKind, { collection: string; remove: string }> = {
  client: { collection: "client-payments", remove: "client" },
  salary: { collection: "salary-payments", remove: "salary" },
  payout: { collection: "manager-payouts", remove: "payout" },
};

function firstOfMonth(): string {
  return `${today().slice(0, 7)}-01`;
}

function paymentDate(payment: AnyPayment): string {
  return "received_on" in payment ? payment.received_on : payment.paid_on;
}

function paymentSubject(payment: AnyPayment): string {
  if ("client" in payment) return payment.client.name;
  if ("employee_name" in payment) return payment.employee_name;
  return payment.manager_name;
}

export function PaymentsPage() {
  const [tab, setTab] = useState<Tab>("client-payments");
  const [notice, setNotice] = useState("");

  return (
    <>
      <DashboardHero
        title=""
        highlight="Payments"
        description="Money received from clients, client budgets, salaries and manager top-ups."
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
          {tab === "salaries" && <PeopleTab key="salaries" role="EMPLOYEE" onNotice={setNotice} />}
          {tab === "payouts" && <PeopleTab key="payouts" role="MANAGER" onNotice={setNotice} />}
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

type PaymentValues = { amount: string; date: string; method: PaymentMethod; reference: string; note: string };

function PaymentFields({
  values,
  onChange,
  dateLabel,
}: {
  values: PaymentValues;
  onChange: (key: keyof PaymentValues, value: string) => void;
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
        <LooplessDate value={values.date} onValueChange={(value) => onChange("date", value)} ariaLabel={dateLabel} />
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

const emptyPayment = (): PaymentValues => ({
  amount: "",
  date: today(),
  method: "BANK_TRANSFER",
  reference: "",
  note: "",
});

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

/* ------------------------------------------------------------------ shared payment editor */

/**
 * Create or edit any payment. For an edit, the employee or manager cannot change (delete and
 * re-record instead); a client payment can be moved to another client.
 */
function PaymentEditor({
  kind,
  payment,
  subjects,
  defaultSubject = "",
  defaultAmount = "",
  back,
  onCancel,
  onSaved,
}: {
  kind: PaymentKind;
  payment: AnyPayment | null;
  subjects: ChoiceItem[];
  defaultSubject?: string;
  defaultAmount?: string;
  back: string;
  onCancel: () => void;
  onSaved: (message: string) => void;
}) {
  const editing = Boolean(payment);
  const [subject, setSubject] = useState(() => {
    if (!payment) return defaultSubject;
    if ("client" in payment) return payment.client.id;
    if ("user_id" in payment) return payment.user_id;
    return payment.manager_user_id;
  });
  const [month, setMonth] = useState(() =>
    payment && "period_month" in payment ? payment.period_month.slice(0, 7) : firstOfMonth().slice(0, 7),
  );
  const [values, setValues] = useState<PaymentValues>(() =>
    payment
      ? {
          amount: payment.amount,
          date: paymentDate(payment),
          method: payment.method,
          reference: payment.reference,
          note: payment.note,
        }
      : { ...emptyPayment(), amount: defaultAmount },
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const subjectLabel = kind === "client" ? "Client" : kind === "salary" ? "Employee" : "Manager";
  const subjectLocked = editing && kind !== "client";
  const noun = kind === "client" ? "payment" : kind === "salary" ? "salary payment" : "payout";

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!subject) return setError(`Choose the ${subjectLabel.toLowerCase()}.`);
    if (kind === "salary" && !month) return setError("Choose the month this salary is for.");
    if (!values.amount || Number(values.amount) <= 0) return setError("Enter an amount greater than zero.");
    if (!values.date) return setError("Enter the date.");
    setSaving(true);
    setError("");
    const dateKey = kind === "client" ? "received_on" : "paid_on";
    const body: Record<string, unknown> = {
      amount: values.amount,
      [dateKey]: values.date,
      method: values.method,
      reference: values.reference.trim(),
      note: values.note.trim(),
      ...(kind === "salary" ? { period_month: `${month}-01` } : {}),
      ...(kind === "client" ? { client_id: subject } : {}),
    };
    if (!editing) {
      if (kind === "salary") body.user_id = subject;
      if (kind === "payout") body.manager_user_id = subject;
    }
    try {
      const path = `/api/company/finance/${PAYMENT_API[kind].collection}`;
      const saved = await api<AnyPayment>(editing && payment ? `${path}/${payment.id}` : path, {
        method: editing ? "PATCH" : "POST",
        json: body,
      });
      onSaved(
        `${money(saved.amount, saved.currency)} ${noun} ${editing ? "updated" : "recorded"} for ${paymentSubject(saved)}.`,
      );
    } catch (requestError) {
      setError(errorText(requestError, `Unable to save the ${noun}.`));
    } finally {
      setSaving(false);
    }
  }

  return (
    <EditorShell
      back={back}
      label={editing ? `Edit ${noun}` : `New ${noun}`}
      icon={kind === "client" ? <Wallet /> : kind === "salary" ? <Banknote /> : <HandCoins />}
      eyebrow={editing ? `EDIT ${noun.toUpperCase()}` : `RECORD ${noun.toUpperCase()}`}
      title={editing ? `Edit ${noun}` : kind === "client" ? "Payment received" : `Record ${noun}`}
      description={
        kind === "client"
          ? "Money from a client lowers their pending amount. It does not change their budget."
          : kind === "salary"
            ? "Salary paid lowers what is pending for that month."
            : "A top-up adds to the manager's advance; commission on approved work is taken from it."
      }
      onCancel={onCancel}
    >
      <form className="management-form organization-form-grid" noValidate onSubmit={save}>
        {error && <div className="management-form-message">{error}</div>}
        <Field
          label={subjectLabel}
          wide={kind !== "salary"}
          hint={subjectLocked ? `To pay someone else, delete this ${noun} and record a new one.` : undefined}
        >
          <LooplessSelect
            value={subject}
            onValueChange={setSubject}
            ariaLabel={subjectLabel}
            disabled={subjectLocked}
            options={[
              { value: "", label: `Choose ${subjectLabel.toLowerCase()}` },
              ...subjects.map((item) => ({ value: item.id, label: item.name })),
              // Keep a deactivated person visible on their own old payment.
              ...(payment && subject && !subjects.some((item) => item.id === subject)
                ? [{ value: subject, label: paymentSubject(payment) }]
                : []),
            ]}
          />
        </Field>
        {kind === "salary" && (
          <Field label="For month">
            <LooplessDate value={month} onValueChange={setMonth} ariaLabel="For month" mode="month" />
          </Field>
        )}
        <PaymentFields
          values={values}
          dateLabel={kind === "client" ? "Received on" : "Paid on"}
          onChange={(key, value) => setValues((current) => ({ ...current, [key]: value }))}
        />
        <FormFooter saving={saving} label={editing ? "Save changes" : `Record ${noun}`} onCancel={onCancel} />
      </form>
    </EditorShell>
  );
}

/** Set a new salary rate, or correct an existing one (amount and note). */
function SalaryEditor({
  record,
  employees,
  defaultEmployee = "",
  defaultAmount = "",
  back,
  onCancel,
  onSaved,
}: {
  record: SalaryRecord | null;
  employees: ChoiceItem[];
  defaultEmployee?: string;
  defaultAmount?: string;
  back: string;
  onCancel: () => void;
  onSaved: (message: string) => void;
}) {
  const editing = Boolean(record);
  const [employee, setEmployee] = useState(defaultEmployee);
  const [values, setValues] = useState({
    amount: record?.monthly_amount ?? defaultAmount,
    from: record?.effective_from ?? firstOfMonth(),
    note: record?.note ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!editing && !employee) return setError("Choose the employee.");
    if (values.amount === "" || Number(values.amount) < 0) return setError("Enter the monthly salary.");
    if (!values.from) return setError("Enter the date it starts from.");
    setSaving(true);
    setError("");
    try {
      if (record) {
        await api(`/api/company/finance/salary-records/${record.id}`, {
          method: "PATCH",
          json: { monthly_amount: values.amount, note: values.note.trim() },
        });
      } else {
        await api(`/api/company/finance/people/${employee}/salary`, {
          method: "PUT",
          json: { monthly_amount: values.amount, effective_from: values.from, note: values.note.trim() },
        });
      }
      onSaved(`Salary ${editing ? "updated" : "set"} to ${money(values.amount, record?.currency)} a month.`);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to save the salary."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <EditorShell
      back={back}
      label={editing ? "Edit salary" : "Set salary"}
      icon={<Banknote />}
      eyebrow={editing ? "EDIT SALARY" : "SET SALARY"}
      title={editing ? "Correct this salary" : "Set monthly salary"}
      description={
        editing
          ? "Fix the amount or note. To change the start date, delete this salary and set it again."
          : "A new salary starts from the date you choose. Earlier months keep their old salary."
      }
      onCancel={onCancel}
    >
      <form className="management-form organization-form-grid" noValidate onSubmit={save}>
        {error && <div className="management-form-message">{error}</div>}
        {!editing && (
          <Field label="Employee" wide>
            <LooplessSelect
              value={employee}
              onValueChange={setEmployee}
              ariaLabel="Employee"
              options={[
                { value: "", label: "Choose employee" },
                ...employees.map((item) => ({ value: item.id, label: item.name })),
              ]}
            />
          </Field>
        )}
        <Field label="Monthly salary">
          <span className="management-input">
            <Wallet aria-hidden="true" />
            <input
              type="number"
              min="0"
              step="0.01"
              value={values.amount}
              onChange={(event) => setValues({ ...values, amount: event.target.value })}
              placeholder="0.00"
            />
          </span>
        </Field>
        <Field label="Starts from">
          <LooplessDate
            value={values.from}
            onValueChange={(value) => setValues({ ...values, from: value })}
            ariaLabel="Starts from"
            disabled={editing}
          />
        </Field>
        <Field label="Note" wide>
          <span className="management-input">
            <FileText aria-hidden="true" />
            <input
              value={values.note}
              onChange={(event) => setValues({ ...values, note: event.target.value })}
              placeholder="For example: yearly raise"
              maxLength={500}
            />
          </span>
        </Field>
        <FormFooter saving={saving} label={editing ? "Save changes" : "Save salary"} onCancel={onCancel} />
      </form>
    </EditorShell>
  );
}

/** Row table for a list of payments with Edit and Delete actions. */
function PaymentTable({
  kind,
  items,
  onEdit,
  onDelete,
}: {
  kind: PaymentKind;
  items: AnyPayment[];
  onEdit: (payment: AnyPayment) => void;
  onDelete: (payment: AnyPayment) => void;
}) {
  return (
    <div className="organization-table production-client-payments" role="table">
      <div className="organization-table-head">
        <span>{kind === "client" ? "Received" : "Paid on"}</span>
        <span>{kind === "client" ? "Client" : kind === "salary" ? "Employee" : "Manager"}</span>
        <span>Method</span>
        <span>Reference</span>
        <span className="production-money">Amount</span>
        <span>Actions</span>
      </div>
      {items.map((item) => (
        <article key={item.id}>
          <span>{formatDate(paymentDate(item))}</span>
          <div className="production-cell">
            <strong>{paymentSubject(item)}</strong>
            {"period_month" in item ? (
              <small>For {formatMonth(item.period_month)}</small>
            ) : (
              item.note && <small>{item.note}</small>
            )}
          </div>
          <span>{methodLabel(item.method)}</span>
          <span>{item.reference || "—"}</span>
          <span className="production-money">{money(item.amount, item.currency)}</span>
          <CrudActionButtons
            edit={{ label: `Edit ${paymentSubject(item)} payment`, onClick: () => onEdit(item) }}
            remove={{ label: `Delete ${paymentSubject(item)} payment`, onClick: () => onDelete(item) }}
          />
        </article>
      ))}
    </div>
  );
}

function DeletePaymentDialog({
  kind,
  payment,
  onCancel,
  onDeleted,
  onError,
}: {
  kind: PaymentKind;
  payment: AnyPayment | null;
  onCancel: () => void;
  onDeleted: () => void;
  onError: (message: string) => void;
}) {
  const [removing, setRemoving] = useState(false);
  async function remove() {
    if (!payment) return;
    setRemoving(true);
    try {
      await api(`/api/company/finance/${PAYMENT_API[kind].remove}/${payment.id}`, { method: "DELETE" });
      onDeleted();
    } catch (requestError) {
      onError(errorText(requestError, "Unable to delete the payment."));
      onCancel();
    } finally {
      setRemoving(false);
    }
  }
  return (
    <ConfirmationDialog
      open={Boolean(payment)}
      title="Delete this payment?"
      description={`${payment ? money(payment.amount, payment.currency) : ""} for ${
        payment ? paymentSubject(payment) : ""
      } will be removed and the pending amount will go up again. Use this only for a mistake.`}
      confirmLabel="Delete payment"
      tone="danger"
      loading={removing}
      onCancel={onCancel}
      onConfirm={() => void remove()}
    />
  );
}

/* ------------------------------------------------------------------ client payments */

function ClientPaymentsTab({ onNotice }: { onNotice: (message: string) => void }) {
  const [data, setData] = useState<PaymentList<ClientPayment> | null>(null);
  const [clients, setClients] = useState<ChoiceItem[]>([]);
  const [client, setClient] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<{ payment: ClientPayment | null } | null>(null);
  const [removeItem, setRemoveItem] = useState<AnyPayment | null>(null);

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

  if (editor) {
    return (
      <PaymentEditor
        kind="client"
        payment={editor.payment}
        subjects={clients}
        defaultSubject={client}
        back="Back to payments"
        onCancel={() => setEditor(null)}
        onSaved={(message) => {
          setEditor(null);
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
        <button type="button" onClick={() => setEditor({ payment: null })}>
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
          <button type="button" onClick={() => setEditor({ payment: null })}>
            <Plus /> Record payment
          </button>
        </div>
      ) : (
        <PaymentTable
          kind="client"
          items={data.items}
          onEdit={(payment) => setEditor({ payment: payment as ClientPayment })}
          onDelete={setRemoveItem}
        />
      )}
      <DeletePaymentDialog
        kind="client"
        payment={removeItem}
        onCancel={() => setRemoveItem(null)}
        onError={setError}
        onDeleted={() => {
          setRemoveItem(null);
          onNotice("Payment deleted.");
          void load();
        }}
      />
    </>
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

type PeopleView =
  | { mode: "list" }
  | { mode: "person"; userId: string }
  | { mode: "payment"; payment: AnyPayment | null; subject?: string; amount?: string }
  | { mode: "salary"; record: SalaryRecord | null; employee?: string; amount?: string };

function PeopleTab({ role, onNotice }: { role: "EMPLOYEE" | "MANAGER"; onNotice: (message: string) => void }) {
  const isManager = role === "MANAGER";
  const kind: PaymentKind = isManager ? "payout" : "salary";
  const [rows, setRows] = useState<TeamReportRow[]>([]);
  const [history, setHistory] = useState<AnyPayment[]>([]);
  const [people, setPeople] = useState<ChoiceItem[]>([]);
  const [currency, setCurrency] = useState("INR");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<PeopleView>({ mode: "list" });
  const [removeItem, setRemoveItem] = useState<AnyPayment | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [report, payments, options] = await Promise.all([
        api<Report<TeamReportRow>>("/api/company/finance/reports/team?period=all"),
        api<PaymentList<AnyPayment>>(`/api/company/finance/${PAYMENT_API[kind].collection}?page_size=100`),
        api<AssigneeOption[]>("/api/company/tasks/assignee-options"),
      ]);
      setRows(report.rows.filter((row) => row.person.role === role));
      setCurrency(report.currency);
      setHistory(payments.items);
      setPeople(
        options.filter((person) => person.role === role).map((person) => ({ id: person.id, name: person.name })),
      );
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load the team."));
    } finally {
      setLoading(false);
    }
  }, [role, kind]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const backToList = (message?: string) => {
    setView({ mode: "list" });
    if (message) onNotice(message);
    void load();
  };
  const backLabel = isManager ? "Back to manager top-ups" : "Back to salaries";

  if (view.mode === "person") {
    return (
      <PersonDetail
        userId={view.userId}
        people={people}
        backLabel={backLabel}
        onBack={() => backToList()}
        onNotice={onNotice}
      />
    );
  }
  if (view.mode === "payment") {
    return (
      <PaymentEditor
        kind={kind}
        payment={view.payment}
        subjects={people}
        defaultSubject={view.subject}
        defaultAmount={view.amount}
        back={backLabel}
        onCancel={() => setView({ mode: "list" })}
        onSaved={backToList}
      />
    );
  }
  if (view.mode === "salary") {
    return (
      <SalaryEditor
        record={view.record}
        employees={people}
        defaultEmployee={view.employee}
        defaultAmount={view.amount}
        back={backLabel}
        onCancel={() => setView({ mode: "list" })}
        onSaved={backToList}
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
        <span className="production-toolbar-actions">
          {!isManager && (
            <button type="button" className="management-back" onClick={() => setView({ mode: "salary", record: null })}>
              <Banknote /> Set salary
            </button>
          )}
          <button type="button" onClick={() => setView({ mode: "payment", payment: null })}>
            <Plus /> {isManager ? "Add top-up" : "Record payment"}
          </button>
        </span>
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
        <>
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
                <CrudActionButtons
                  view={{
                    label: `Open ${row.person.name}`,
                    onClick: () => setView({ mode: "person", userId: row.person.id }),
                  }}
                  edit={
                    isManager
                      ? {
                          label: `Add top-up for ${row.person.name}`,
                          onClick: () =>
                            setView({
                              mode: "payment",
                              payment: null,
                              subject: row.person.id,
                              amount: Number(row.pending) > 0 ? row.pending : "",
                            }),
                        }
                      : {
                          label: `Set salary for ${row.person.name}`,
                          onClick: () => setView({ mode: "salary", record: null, employee: row.person.id }),
                        }
                  }
                />
              </article>
            ))}
          </div>
          <div className="production-section-title">
            <span>{isManager ? "Top-up history" : "Salary payment history"}</span>
            <small>Edit or delete a payment recorded by mistake.</small>
          </div>
          {history.length === 0 ? (
            <p className="production-muted">No {isManager ? "top-ups" : "salary payments"} recorded yet.</p>
          ) : (
            <PaymentTable
              kind={kind}
              items={history}
              onEdit={(payment) => setView({ mode: "payment", payment })}
              onDelete={setRemoveItem}
            />
          )}
        </>
      )}
      <DeletePaymentDialog
        kind={kind}
        payment={removeItem}
        onCancel={() => setRemoveItem(null)}
        onError={setError}
        onDeleted={() => {
          setRemoveItem(null);
          onNotice("Payment deleted.");
          void load();
        }}
      />
    </>
  );
}

type PersonView =
  | { mode: "detail" }
  | { mode: "payment"; payment: AnyPayment | null; amount?: string }
  | { mode: "salary"; record: SalaryRecord | null; amount?: string };

function PersonDetail({
  userId,
  people,
  backLabel,
  onBack,
  onNotice,
}: {
  userId: string;
  people: ChoiceItem[];
  backLabel: string;
  onBack: () => void;
  onNotice: (message: string) => void;
}) {
  const [data, setData] = useState<PersonFinance | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<PersonView>({ mode: "detail" });
  const [removePayment, setRemovePayment] = useState<AnyPayment | null>(null);
  const [removeRecord, setRemoveRecord] = useState<SalaryRecord | null>(null);
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

  const isManager = data?.person.role === "MANAGER";
  const kind: PaymentKind = isManager ? "payout" : "salary";
  const backToDetail = (message: string) => {
    setView({ mode: "detail" });
    onNotice(message);
    void load();
  };

  async function deleteRecord() {
    if (!removeRecord) return;
    setRemoving(true);
    try {
      setData(await api<PersonFinance>(`/api/company/finance/salary-records/${removeRecord.id}`, { method: "DELETE" }));
      onNotice("Salary deleted. The previous salary now continues until the next one.");
      setRemoveRecord(null);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to delete the salary."));
      setRemoveRecord(null);
    } finally {
      setRemoving(false);
    }
  }

  if (data && view.mode === "payment") {
    return (
      <PaymentEditor
        kind={kind}
        payment={view.payment}
        subjects={people.length ? people : [{ id: data.person.id, name: data.person.name }]}
        defaultSubject={data.person.id}
        defaultAmount={view.amount}
        back={`Back to ${data.person.name}`}
        onCancel={() => setView({ mode: "detail" })}
        onSaved={backToDetail}
      />
    );
  }
  if (data && view.mode === "salary") {
    return (
      <SalaryEditor
        record={view.record}
        employees={[{ id: data.person.id, name: data.person.name }]}
        defaultEmployee={data.person.id}
        defaultAmount={view.amount}
        back={`Back to ${data.person.name}`}
        onCancel={() => setView({ mode: "detail" })}
        onSaved={backToDetail}
      />
    );
  }

  return (
    <>
      <header className="management-toolbar">
        <button type="button" className="management-back" onClick={onBack}>
          <ArrowLeft /> {backLabel}
        </button>
        {data && (
          <span className="production-toolbar-actions">
            {!isManager && (
              <button
                type="button"
                className="management-back"
                onClick={() =>
                  setView({ mode: "salary", record: null, amount: data.employee?.current_monthly_salary ?? "" })
                }
              >
                <Banknote /> Set salary
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                const pending = isManager
                  ? data.manager?.pending
                  : data.employee?.months.find((line) => line.month === firstOfMonth())?.pending;
                setView({ mode: "payment", payment: null, amount: pending && Number(pending) > 0 ? pending : "" });
              }}
            >
              <Plus /> {isManager ? "Add top-up" : "Record payment"}
            </button>
          </span>
        )}
      </header>
      {error ? (
        <StateBlock error={error} onRetry={() => void load()} />
      ) : !data ? (
        <TableSkeleton />
      ) : data.manager ? (
        <ManagerFinance
          data={data}
          onEdit={(payment) => setView({ mode: "payment", payment })}
          onRemove={setRemovePayment}
        />
      ) : data.employee ? (
        <EmployeeFinance
          data={data}
          onEdit={(payment) => setView({ mode: "payment", payment })}
          onRemove={setRemovePayment}
          onEditRecord={(record) => setView({ mode: "salary", record })}
          onRemoveRecord={setRemoveRecord}
        />
      ) : null}
      <DeletePaymentDialog
        kind={kind}
        payment={removePayment}
        onCancel={() => setRemovePayment(null)}
        onError={setError}
        onDeleted={() => {
          setRemovePayment(null);
          onNotice("Payment deleted.");
          void load();
        }}
      />
      <ConfirmationDialog
        open={Boolean(removeRecord)}
        title="Delete this salary?"
        description={`${removeRecord ? money(removeRecord.monthly_amount, removeRecord.currency) : ""} a month from ${
          removeRecord ? formatDate(removeRecord.effective_from) : ""
        } will be removed. The salary before it will continue until the next change.`}
        confirmLabel="Delete salary"
        tone="danger"
        loading={removing}
        onCancel={() => setRemoveRecord(null)}
        onConfirm={() => void deleteRecord()}
      />
    </>
  );
}

function PaymentList({
  items,
  currency,
  onEdit,
  onRemove,
  empty,
}: {
  items: AnyPayment[];
  currency: string;
  onEdit: (payment: AnyPayment) => void;
  onRemove: (payment: AnyPayment) => void;
  empty: string;
}) {
  if (items.length === 0) return <p className="production-muted">{empty}</p>;
  return (
    <ul className="production-list">
      {items.map((item) => (
        <li key={item.id}>
          <div>
            <strong>{"period_month" in item ? formatMonth(item.period_month) : formatDate(paymentDate(item))}</strong>
            <small>
              {"period_month" in item ? `Paid ${formatDate(item.paid_on)} · ` : ""}
              {methodLabel(item.method)}
              {item.reference ? ` · ${item.reference}` : ""}
              {item.note ? ` · ${item.note}` : ""}
            </small>
          </div>
          <span className="production-inline-actions">
            <b>{money(item.amount, currency)}</b>
            <CrudActionButtons
              edit={{ label: "Edit payment", onClick: () => onEdit(item) }}
              remove={{ label: "Delete payment", onClick: () => onRemove(item) }}
            />
          </span>
        </li>
      ))}
    </ul>
  );
}

function ManagerFinance({
  data,
  onEdit,
  onRemove,
}: {
  data: PersonFinance;
  onEdit: (payment: AnyPayment) => void;
  onRemove: (payment: AnyPayment) => void;
}) {
  const earnings = data.manager!;
  const currency = earnings.currency;
  return (
    <>
      {earnings.wallet && (
        <AdvanceWallet
          wallet={earnings.wallet}
          currency={currency}
          money={money}
          viewer="ADMIN"
          statementUrl={(index) => `/api/company/finance/sheets/managers/${data.person.id}/${index}/statement.pdf`}
        />
      )}
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
        </div>
        <div>
          <Panel icon={<History />} eyebrow="TOP-UPS" title="Sent to this manager">
            <div className="production-panel-body">
              <PaymentList
                items={earnings.payouts}
                currency={currency}
                onEdit={onEdit}
                onRemove={onRemove}
                empty="No top-ups recorded yet."
              />
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}

function EmployeeFinance({
  data,
  onEdit,
  onRemove,
  onEditRecord,
  onRemoveRecord,
}: {
  data: PersonFinance;
  onEdit: (payment: AnyPayment) => void;
  onRemove: (payment: AnyPayment) => void;
  onEditRecord: (record: SalaryRecord) => void;
  onRemoveRecord: (record: SalaryRecord) => void;
}) {
  const salary = data.employee!;
  const currency = salary.currency;
  const months = useMemo(() => salary.months, [salary.months]);
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
              {months.length === 0 ? (
                <p className="production-muted">Set a salary to start tracking months.</p>
              ) : (
                <ul className="production-list">
                  {months.map((line) => (
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
              <PaymentList
                items={salary.payments}
                currency={currency}
                onEdit={onEdit}
                onRemove={onRemove}
                empty="No salary payments recorded yet."
              />
            </div>
          </Panel>
        </div>
        <div>
          <Panel
            icon={<Wallet />}
            eyebrow="SALARY HISTORY"
            title="Salary rates"
            description="Each rate applies from its start date until the next one."
          >
            <div className="production-panel-body">
              {data.salary_history.length === 0 ? (
                <p className="production-muted">No salary set yet. Use “Set salary” above.</p>
              ) : (
                <ul className="production-list">
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
                      <CrudActionButtons
                        edit={{ label: "Edit salary", onClick: () => onEditRecord(record) }}
                        remove={{ label: "Delete salary", onClick: () => onRemoveRecord(record) }}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
