"use client";

/*
 * Documents (owner requests 2026-11-15), Admin only.
 * Clients: a new client gets a welcome email with an onboarding form and the service agreement
 * the moment they are added (if they have an email). Within 60 hours the admin can send it again;
 * after that it cannot be sent. Employees: offer letter, joining letter, welcome and agreement,
 * filled with the job details. Templates: change any document's text. Email campaigns: coming soon.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BadgeCheck,
  Clock3,
  Contact,
  Download,
  FileSignature,
  Mail,
  Megaphone,
  RotateCcw,
  Send,
  UsersRound,
  X,
} from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { api, errorText } from "@/lib/production/client";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";
import "@/styles/organization.css";
import "@/styles/production.css";
import "@/styles/documents.css";

type Status = "SENT" | "OPENED" | "COMPLETED" | "CANCELLED" | "EXPIRED";
type Packet = {
  id: string;
  audience: "CLIENT" | "EMPLOYEE";
  client_id: string | null;
  user_id: string | null;
  recipient_name: string;
  recipient_email: string;
  documents: string[];
  fields: Record<string, string | number>;
  status: Status;
  expires_at: string;
  opened_at: string | null;
  signed_name: string | null;
  signed_at: string | null;
  signed_ip: string | null;
  form_data: Record<string, string>;
  sent_count: number;
  created_by_name: string | null;
  created_at: string;
};
type ClientRow = {
  client_id: string;
  name: string;
  email: string | null;
  created_at: string;
  window_ends_at: string;
  can_send: boolean;
  packet: Packet | null;
};
type Template = {
  kind: string;
  audience: "CLIENT" | "EMPLOYEE";
  label: string;
  signable: boolean;
  subject: string;
  body: string;
  customised: boolean;
  placeholders: string[];
};
type Overview = {
  window_hours: number;
  clients: ClientRow[];
  employees: Packet[];
  staff: { id: string; name: string; email: string; role: "MANAGER" | "EMPLOYEE" }[];
  templates: Template[];
};
type Tab = "CLIENTS" | "EMPLOYEES" | "TEMPLATES" | "CAMPAIGNS";

const STATUS: Record<Status, string> = {
  SENT: "Sent",
  OPENED: "Opened",
  COMPLETED: "Accepted",
  CANCELLED: "Cancelled",
  EXPIRED: "Expired",
};
const EMPLOYEE_DOCS = [
  { key: "EMPLOYEE_OFFER", label: "Offer letter" },
  { key: "EMPLOYEE_JOINING", label: "Joining letter" },
  { key: "EMPLOYEE_AGREEMENT", label: "Employment agreement" },
  { key: "EMPLOYEE_WELCOME", label: "Welcome email" },
] as const;

function utc(value: string): Date {
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
}

function day(value: string): string {
  return utc(value).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

function timeLeft(value: string): string {
  const ms = utc(value).getTime() - Date.now();
  if (ms <= 0) return "Closed";
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  return hours > 0 ? `${hours} h ${minutes} m left` : `${minutes} m left`;
}

export function DocumentsPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("CLIENTS");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [viewing, setViewing] = useState<Packet | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api<Overview>("/api/company/onboarding"));
      setError("");
    } catch (reason) {
      setError(errorText(reason, "Unable to load documents."));
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    const tick = window.setInterval(() => setData((current) => (current ? { ...current } : current)), 60_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(tick);
    };
  }, [load]);

  async function act(key: string, action: () => Promise<unknown>, done: string) {
    setBusy(key);
    setNotice("");
    try {
      await action();
      setNotice(done);
      await load();
    } catch (reason) {
      setNotice(errorText(reason, "That did not work."));
    } finally {
      setBusy("");
    }
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "CLIENTS", label: "Client onboarding", icon: <Contact /> },
    { id: "EMPLOYEES", label: "Employee documents", icon: <UsersRound /> },
    { id: "TEMPLATES", label: "Templates", icon: <FileSignature /> },
    { id: "CAMPAIGNS", label: "Email campaigns", icon: <Megaphone /> },
  ];

  return (
    <>
      <DashboardHero
        title=""
        highlight="Documents"
        description="Welcome emails, onboarding forms, agreements and letters for new clients and team members. They read and accept them online."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace documents-page" aria-live="polite">
          <nav className="production-tabs" aria-label="Document sections">
            {tabs.map((item) => (
              <button
                key={item.id}
                type="button"
                className={tab === item.id ? "active" : ""}
                aria-pressed={tab === item.id}
                onClick={() => setTab(item.id)}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>

          {notice && (
            <p className="documents-notice" role="status">
              {notice}
              <button type="button" aria-label="Dismiss" onClick={() => setNotice("")}>
                <X />
              </button>
            </p>
          )}

          {error ? (
            <div className="organization-state">
              <h3>{error}</h3>
              <button type="button" onClick={() => void load()}>
                Retry
              </button>
            </div>
          ) : !data ? (
            <div className="orbit-loader-block">
              <OrbitLoader size={56} label="Loading documents" />
            </div>
          ) : tab === "CLIENTS" ? (
            <ClientsTab
              data={data}
              busy={busy}
              onSend={(row) =>
                void act(
                  row.client_id,
                  () => api(`/api/company/onboarding/clients/${row.client_id}`, { method: "POST" }),
                  `Onboarding sent to ${row.email}.`,
                )
              }
              onView={setViewing}
            />
          ) : tab === "EMPLOYEES" ? (
            <EmployeesTab
              data={data}
              busy={busy}
              onSent={(message) => {
                setNotice(message);
                void load();
              }}
              onResend={(packet) =>
                void act(
                  packet.id,
                  () => api(`/api/company/onboarding/packets/${packet.id}/resend`, { method: "POST" }),
                  `Sent again to ${packet.recipient_email}.`,
                )
              }
              onCancel={(packet) =>
                void act(
                  packet.id,
                  () => api(`/api/company/onboarding/packets/${packet.id}/cancel`, { method: "POST" }),
                  "The link was cancelled.",
                )
              }
              onView={setViewing}
            />
          ) : tab === "TEMPLATES" ? (
            <TemplatesTab templates={data.templates} onSaved={(message) => (setNotice(message), void load())} />
          ) : (
            <CampaignsTab />
          )}
        </section>
      </div>

      {viewing && <PacketView packet={viewing} onClose={() => setViewing(null)} />}
    </>
  );
}

function StatusChip({ status }: { status: Status | "NOT_SENT" }) {
  return (
    <em className={`documents-status ${status.toLowerCase()}`}>
      {status === "NOT_SENT" ? "Not sent" : STATUS[status]}
    </em>
  );
}

function ClientsTab({
  data,
  busy,
  onSend,
  onView,
}: {
  data: Overview;
  busy: string;
  onSend: (row: ClientRow) => void;
  onView: (packet: Packet) => void;
}) {
  const done = data.clients.filter((row) => row.packet?.status === "COMPLETED").length;
  return (
    <>
      <header className="management-toolbar">
        <div>
          <span>Sent automatically when a client with an email is added</span>
          <strong>
            {done} of {data.clients.length} clients onboarded
          </strong>
        </div>
        <span className="documents-rule">
          <Clock3 aria-hidden="true" /> Can be sent only within {data.window_hours} hours of adding the client
        </span>
      </header>
      {data.clients.length === 0 ? (
        <div className="organization-state">
          <Contact />
          <h3>No clients yet</h3>
          <p>Add a client with an email and their welcome, onboarding form and agreement go out at once.</p>
        </div>
      ) : (
        <div className="organization-table documents-table" role="table" aria-label="Client onboarding">
          <div className="organization-table-head" role="row">
            <span>Client</span>
            <span>Added</span>
            <span>Window</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
          {data.clients.map((row) => {
            const packet = row.packet;
            return (
              <article key={row.client_id} role="row">
                <div className="production-cell">
                  <strong>{row.name}</strong>
                  <small>{row.email ?? "No email yet"}</small>
                </div>
                <span>{day(row.created_at)}</span>
                <span className={timeLeft(row.window_ends_at) === "Closed" ? "documents-closed" : "documents-open"}>
                  {timeLeft(row.window_ends_at)}
                </span>
                <span>
                  <StatusChip status={packet ? packet.status : "NOT_SENT"} />
                  {packet?.opened_at && packet.status === "OPENED" && <small> · {day(packet.opened_at)}</small>}
                </span>
                <span className="documents-actions">
                  {packet && (
                    <button type="button" className="management-secondary-action" onClick={() => onView(packet)}>
                      View
                    </button>
                  )}
                  <button
                    type="button"
                    className="management-primary-action"
                    disabled={!row.can_send || busy === row.client_id}
                    title={
                      !row.email
                        ? "Add the client's email first"
                        : !row.can_send
                          ? packet?.status === "COMPLETED"
                            ? "Already accepted"
                            : `More than ${data.window_hours} hours since the client was added`
                          : undefined
                    }
                    onClick={() => onSend(row)}
                  >
                    <Send /> {packet ? "Send again" : "Send"}
                  </button>
                </span>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}

function EmployeesTab({
  data,
  busy,
  onSent,
  onResend,
  onCancel,
  onView,
}: {
  data: Overview;
  busy: string;
  onSent: (message: string) => void;
  onResend: (packet: Packet) => void;
  onCancel: (packet: Packet) => void;
  onView: (packet: Packet) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <header className="management-toolbar">
        <div>
          <span>Offer letter, joining letter, agreement and welcome email</span>
          <strong>
            {data.employees.length} {data.employees.length === 1 ? "set" : "sets"} sent ·{" "}
            {data.employees.filter((item) => item.status === "COMPLETED").length} accepted
          </strong>
        </div>
        <button type="button" onClick={() => setOpen((value) => !value)}>
          <Mail /> {open ? "Close" : "Send documents"}
        </button>
      </header>
      {open && (
        <EmployeeForm
          staff={data.staff}
          onSent={(message) => {
            setOpen(false);
            onSent(message);
          }}
        />
      )}
      {data.employees.length === 0 ? (
        !open && (
          <div className="organization-state">
            <UsersRound />
            <h3>No documents sent yet</h3>
            <p>Send a new team member their offer letter, joining letter and agreement to accept online.</p>
          </div>
        )
      ) : (
        <div className="organization-table documents-table employees" role="table" aria-label="Employee documents">
          <div className="organization-table-head" role="row">
            <span>Person</span>
            <span>Documents</span>
            <span>Sent</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
          {data.employees.map((packet) => (
            <article key={packet.id} role="row">
              <div className="production-cell">
                <strong>{packet.recipient_name}</strong>
                <small>
                  {String(packet.fields.job_title ?? "")} · {packet.recipient_email}
                </small>
              </div>
              <span className="documents-kinds">
                {packet.documents
                  .map((kind) => EMPLOYEE_DOCS.find((item) => item.key === kind)?.label ?? kind)
                  .join(", ")}
              </span>
              <span>{day(packet.created_at)}</span>
              <span>
                <StatusChip status={packet.status} />
              </span>
              <span className="documents-actions">
                <button type="button" className="management-secondary-action" onClick={() => onView(packet)}>
                  View
                </button>
                {(packet.status === "SENT" || packet.status === "OPENED" || packet.status === "EXPIRED") && (
                  <>
                    <button
                      type="button"
                      className="management-secondary-action"
                      disabled={busy === packet.id}
                      onClick={() => onResend(packet)}
                    >
                      <RotateCcw /> Again
                    </button>
                    {packet.status !== "EXPIRED" && (
                      <button
                        type="button"
                        className="management-secondary-action"
                        disabled={busy === packet.id}
                        onClick={() => onCancel(packet)}
                      >
                        Cancel
                      </button>
                    )}
                  </>
                )}
              </span>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

function EmployeeForm({ staff, onSent }: { staff: Overview["staff"]; onSent: (message: string) => void }) {
  const [person, setPerson] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [documents, setDocuments] = useState<string[]>(["EMPLOYEE_OFFER", "EMPLOYEE_JOINING", "EMPLOYEE_AGREEMENT"]);
  const [jobTitle, setJobTitle] = useState("");
  const [salary, setSalary] = useState("");
  const [joining, setJoining] = useState("");
  const [reporting, setReporting] = useState("");
  const [location, setLocation] = useState("");
  const [probation, setProbation] = useState("3");
  const [notice, setNotice] = useState("30");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const packet = await api<Packet>("/api/company/onboarding/employees", {
        method: "POST",
        json: {
          user_id: person && person !== "NEW" ? person : null,
          name: person === "NEW" ? name.trim() : "",
          email: person === "NEW" ? email.trim() : null,
          documents: documents.length ? documents : ["EMPLOYEE_WELCOME"],
          job_title: jobTitle.trim(),
          monthly_salary: Number(salary || 0).toFixed(2),
          joining_date: joining,
          reporting_to: reporting.trim(),
          work_location: location.trim(),
          probation_months: Number(probation || 0),
          notice_days: Number(notice || 0),
        },
      });
      onSent(`Documents sent to ${packet.recipient_email}.`);
    } catch (reason) {
      setError(errorText(reason, "Could not send the documents."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="management-editor documents-form" onSubmit={(event) => void send(event)}>
      {error && <p className="documents-error">{error}</p>}
      <div className="documents-grid">
        <label className="management-field wide">
          <span>Who</span>
          <LooplessSelect
            value={person}
            onValueChange={setPerson}
            ariaLabel="Who"
            options={[
              { value: "", label: "Choose a person" },
              ...staff.map((item) => ({
                value: item.id,
                label: `${item.name} · ${item.role === "MANAGER" ? "Manager" : "Employee"}`,
              })),
              { value: "NEW", label: "Someone new (not on Adverse yet)" },
            ]}
          />
        </label>
        {person === "NEW" && (
          <>
            <label className="management-field">
              <span>Full name</span>
              <input className="management-input" required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="management-field">
              <span>Email</span>
              <input
                className="management-input"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          </>
        )}
        <fieldset className="documents-checks wide">
          <legend>Documents</legend>
          {EMPLOYEE_DOCS.map((item) => (
            <label key={item.key}>
              <input
                type="checkbox"
                checked={item.key === "EMPLOYEE_WELCOME" || documents.includes(item.key)}
                disabled={item.key === "EMPLOYEE_WELCOME"}
                onChange={(event) =>
                  setDocuments((current) =>
                    event.target.checked ? [...current, item.key] : current.filter((key) => key !== item.key),
                  )
                }
              />
              {item.label}
              {item.key === "EMPLOYEE_WELCOME" && <small> (always)</small>}
            </label>
          ))}
        </fieldset>
        <label className="management-field">
          <span>Job title</span>
          <input
            className="management-input"
            required
            value={jobTitle}
            placeholder="e.g. Video Editor"
            onChange={(e) => setJobTitle(e.target.value)}
          />
        </label>
        <label className="management-field">
          <span>Monthly salary</span>
          <input
            className="management-input"
            type="number"
            min={0}
            step={0.01}
            required
            value={salary}
            onChange={(e) => setSalary(e.target.value)}
          />
        </label>
        <label className="management-field">
          <span>Joining date</span>
          <input
            className="management-input"
            type="date"
            required
            value={joining}
            onChange={(e) => setJoining(e.target.value)}
          />
        </label>
        <label className="management-field">
          <span>Reports to</span>
          <input className="management-input" value={reporting} onChange={(e) => setReporting(e.target.value)} />
        </label>
        <label className="management-field">
          <span>Place of work</span>
          <input className="management-input" value={location} onChange={(e) => setLocation(e.target.value)} />
        </label>
        <label className="management-field">
          <span>Probation (months)</span>
          <input
            className="management-input"
            type="number"
            min={0}
            max={24}
            value={probation}
            onChange={(e) => setProbation(e.target.value)}
          />
        </label>
        <label className="management-field">
          <span>Notice (days)</span>
          <input
            className="management-input"
            type="number"
            min={0}
            max={180}
            value={notice}
            onChange={(e) => setNotice(e.target.value)}
          />
        </label>
      </div>
      <div className="documents-form-foot">
        <span>They get an email with a private link (works for 7 days) and the documents as a PDF.</span>
        <button type="submit" className="management-primary-action" disabled={busy || !person}>
          <Send /> {busy ? "Sending…" : "Send documents"}
        </button>
      </div>
    </form>
  );
}

function TemplatesTab({ templates, onSaved }: { templates: Template[]; onSaved: (message: string) => void }) {
  const [kind, setKind] = useState(templates[0]?.kind ?? "");
  const current = useMemo(() => templates.find((item) => item.kind === kind) ?? templates[0], [templates, kind]);
  const [subject, setSubject] = useState(current?.subject ?? "");
  const [body, setBody] = useState(current?.body ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function pick(next: Template) {
    setKind(next.kind);
    setSubject(next.subject);
    setBody(next.body);
    setError("");
  }

  async function save(reset: boolean) {
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      const list = await api<Template[]>(`/api/company/onboarding/templates/${current.kind}`, {
        method: reset ? "DELETE" : "PUT",
        ...(reset ? {} : { json: { subject, body } }),
      });
      const fresh = list.find((item) => item.kind === current.kind);
      if (fresh) pick(fresh);
      onSaved(reset ? `${current.label} is back to the standard text.` : `${current.label} saved.`);
    } catch (reason) {
      setError(errorText(reason, "Could not save the template."));
    } finally {
      setBusy(false);
    }
  }

  if (!current) return null;
  const groups: ["CLIENT" | "EMPLOYEE", string][] = [
    ["CLIENT", "Clients"],
    ["EMPLOYEE", "Employees"],
  ];
  return (
    <div className="documents-templates">
      <aside>
        {groups.map(([audience, label]) => (
          <div key={audience}>
            <h3>{label}</h3>
            {templates
              .filter((item) => item.audience === audience)
              .map((item) => (
                <button
                  key={item.kind}
                  type="button"
                  className={item.kind === current.kind ? "active" : undefined}
                  onClick={() => pick(item)}
                >
                  <span>{item.label}</span>
                  {item.customised && <em>Edited</em>}
                </button>
              ))}
          </div>
        ))}
      </aside>
      <div className="management-editor documents-editor">
        {error && <p className="documents-error">{error}</p>}
        <label className="management-field">
          <span>Subject / title</span>
          <input
            className="management-input"
            value={subject}
            maxLength={200}
            onChange={(e) => setSubject(e.target.value)}
          />
        </label>
        <label className="management-field">
          <span>Text</span>
          <textarea className="documents-body" value={body} rows={18} onChange={(e) => setBody(e.target.value)} />
        </label>
        <div className="documents-placeholders">
          <span>Fills in by itself:</span>
          {current.placeholders.map((item) => (
            <button
              key={item}
              type="button"
              title="Add to the end of the text"
              onClick={() => setBody((value) => `${value}{{${item}}}`)}
            >
              {`{{${item}}}`}
            </button>
          ))}
        </div>
        <div className="documents-form-foot">
          <span>
            {current.signable ? "People accept this online." : "For information; nothing to accept."}{" "}
            {current.customised ? "Your own version." : "Standard text."}
          </span>
          <span className="documents-actions">
            {current.customised && (
              <button
                type="button"
                className="management-secondary-action"
                disabled={busy}
                onClick={() => void save(true)}
              >
                <RotateCcw /> Standard text
              </button>
            )}
            <button
              type="button"
              className="management-primary-action"
              disabled={busy || (subject === current.subject && body === current.body)}
              onClick={() => void save(false)}
            >
              <BadgeCheck /> Save
            </button>
          </span>
        </div>
      </div>
    </div>
  );
}

function CampaignsTab() {
  return (
    <div className="documents-campaigns">
      <div className="documents-soon">
        <Megaphone aria-hidden="true" />
        <h3>Email campaigns are coming soon</h3>
        <p>Send newsletters, festival offers and updates to all your clients at once, with opens and clicks.</p>
      </div>
      <article className="documents-preview" aria-label="Campaign template preview">
        <header>
          <span>Template preview</span>
          <strong>Monthly update</strong>
        </header>
        <div>
          <h4>This month at {"{{company_name}}"}</h4>
          <p>Hello {"{{client_name}}"}, here is what we made for you this month and what is coming next.</p>
          <ul>
            <li>Videos delivered: {"{{videos_delivered}}"}</li>
            <li>Top performing reel: {"{{top_video}}"}</li>
            <li>Next month&apos;s plan: {"{{next_plan}}"}</li>
          </ul>
          <span className="documents-preview-button">See your calendar</span>
        </div>
        <footer>
          <button type="button" className="management-primary-action" disabled>
            <Send /> Create campaign · soon
          </button>
        </footer>
      </article>
    </div>
  );
}

function PacketView({ packet, onClose }: { packet: Packet; onClose: () => void }) {
  const answers = Object.entries(packet.form_data).filter(([, value]) => value);
  return (
    <div className="documents-backdrop" onClick={onClose}>
      <section
        className="documents-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={`Documents for ${packet.recipient_name}`}
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <span>{packet.audience === "CLIENT" ? "Client onboarding" : "Employee documents"}</span>
            <h3>{packet.recipient_name}</h3>
            <small>{packet.recipient_email}</small>
          </div>
          <button type="button" className="management-secondary-action" aria-label="Close" onClick={onClose}>
            <X />
          </button>
        </header>
        <dl className="documents-facts">
          <div>
            <dt>Status</dt>
            <dd>
              <StatusChip status={packet.status} />
            </dd>
          </div>
          <div>
            <dt>Sent</dt>
            <dd>
              {day(packet.created_at)}
              {packet.sent_count > 1 ? ` · sent ${packet.sent_count} times` : ""}
            </dd>
          </div>
          <div>
            <dt>Link works until</dt>
            <dd>{day(packet.expires_at)}</dd>
          </div>
          {packet.opened_at && (
            <div>
              <dt>Opened</dt>
              <dd>{day(packet.opened_at)}</dd>
            </div>
          )}
          {packet.signed_at && (
            <div>
              <dt>Accepted</dt>
              <dd>
                &quot;{packet.signed_name}&quot; · {day(packet.signed_at)} · IP {packet.signed_ip}
              </dd>
            </div>
          )}
        </dl>
        {answers.length > 0 && (
          <>
            <h4>Their answers</h4>
            <dl className="documents-answers">
              {answers.map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replace(/_/g, " ")}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
        <a
          className="management-primary-action documents-pdf"
          href={`/api/company/onboarding/packets/${packet.id}/pdf`}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Download /> {packet.signed_at ? "Signed documents (PDF)" : "Documents (PDF)"}
        </a>
      </section>
    </div>
  );
}
