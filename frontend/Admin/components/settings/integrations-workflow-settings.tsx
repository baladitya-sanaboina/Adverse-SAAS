"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  BellRing,
  Check,
  ClipboardCheck,
  FolderKanban,
  LoaderCircle,
  MessageCircleMore,
  Plug,
  Unplug,
} from "lucide-react";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";

type Provider = "GOOGLE_DRIVE" | "SLACK" | "STRIPE";
type Configuration = {
  document_upload: boolean;
  document_download: boolean;
  project_notifications: boolean;
  task_notifications: boolean;
  important_alerts: boolean;
  billing_enabled: boolean;
};
type Integration = {
  provider: Provider;
  status: "NOT_CONFIGURED" | "CONFIGURED" | "CONNECTED" | "DISCONNECTED" | "ERROR";
  enabled: boolean;
  configuration: Configuration;
  connected_at: string | null;
  updated_at: string | null;
};
type Workflows = {
  task_notifications: boolean;
  project_updates: boolean;
  approval_flow: boolean;
  client_notifications: boolean;
  updated_at?: string | null;
};

const providers = {
  GOOGLE_DRIVE: {
    name: "Google Drive",
    description: "Prepare document upload and download access for the future connector.",
    options: [
      ["document_upload", "Allow document upload", "Permit company documents to be sent to Drive."],
      ["document_download", "Allow document download", "Permit company documents to be retrieved from Drive."],
    ],
  },
  SLACK: {
    name: "Slack",
    description: "Choose which company events can be delivered after Slack is connected.",
    options: [
      ["project_notifications", "Project notifications", "Notify configured channels about project updates."],
      ["task_notifications", "Task notifications", "Notify configured channels about task activity."],
      ["important_alerts", "Important alerts", "Allow security and high-priority company alerts."],
    ],
  },
  STRIPE: {
    name: "Stripe",
    description: "Prepare company billing configuration for the future payment connector.",
    options: [["billing_enabled", "Billing integration", "Allow billing workflows when Stripe becomes available."]],
  },
} as const;

function apiMessage(body: unknown, fallback: string) {
  if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") return body.detail;
  return fallback;
}

export function IntegrationsSettings() {
  const [items, setItems] = useState<Integration[]>([]);
  const [selected, setSelected] = useState<Integration | null>(null);
  const [draft, setDraft] = useState<Integration | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [disconnect, setDisconnect] = useState<Integration | null>(null);

  async function load() {
    try {
      const response = await fetch("/api/company/integrations", { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(apiMessage(body, "Unable to load integration settings."));
      setItems(body.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load integration settings.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void fetch("/api/company/integrations", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(apiMessage(body, "Unable to load integration settings."));
        setItems(body.items);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load integration settings."))
      .finally(() => setLoading(false));
  }, []);
  const dirty = useMemo(() => JSON.stringify(selected) !== JSON.stringify(draft), [selected, draft]);
  function open(item: Integration) {
    setSelected(structuredClone(item));
    setDraft(structuredClone(item));
    setNotice("");
    setError("");
  }
  async function save() {
    if (!draft) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/company/integrations?provider=${draft.provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: draft.enabled, configuration: draft.configuration }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(apiMessage(body, "Integration configuration could not be saved."));
      setItems((current) => current.map((item) => (item.provider === body.provider ? body : item)));
      setSelected(body);
      setDraft(body);
      setNotice(`${providers[body.provider as Provider].name} configuration saved.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Integration configuration could not be saved.");
    } finally {
      setSaving(false);
    }
  }
  async function confirmDisconnect() {
    if (!disconnect) return;
    setSaving(true);
    try {
      const response = await fetch(`/api/company/integrations?provider=${disconnect.provider}`, { method: "DELETE" });
      const body = await response.json();
      if (!response.ok) throw new Error(apiMessage(body, "Integration could not be disconnected."));
      setItems((current) => current.map((item) => (item.provider === body.provider ? body : item)));
      setSelected(null);
      setDraft(null);
      setNotice(`${providers[body.provider as Provider].name} disconnected.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Integration could not be disconnected.");
    } finally {
      setSaving(false);
      setDisconnect(null);
    }
  }
  if (loading) return <SettingsState loading text="Loading integrations..." />;
  if (error && !items.length)
    return (
      <SettingsState
        text={error}
        action={() => {
          setLoading(true);
          setError("");
          void load();
        }}
      />
    );
  return (
    <>
      <header className="settings-section-title day38-heading">
        <div>
          <span>{draft ? "Provider configuration" : "Connected services"}</span>
          <h3>{draft ? providers[draft.provider].name : "Manage integrations"}</h3>
        </div>
        <p>
          {draft
            ? "Configuration foundation only. Credentials and provider connections come later."
            : "Configure company-level integration behavior without storing provider secrets."}
        </p>
      </header>
      {notice && (
        <div className="day38-notice">
          <Check />
          {notice}
        </div>
      )}
      {error && <div className="day38-error">{error}</div>}
      {!draft ? (
        <div className="integration-grid">
          {items.map((item) => {
            const meta = providers[item.provider];
            return (
              <article key={item.provider} className="integration-card">
                <header>
                  <ProviderLogo provider={item.provider} />
                  <span>
                    <b>{meta.name}</b>
                    <small>{meta.description}</small>
                  </span>
                </header>
                <footer>
                  <em className={`integration-status ${item.status.toLowerCase()}`}>
                    {item.status.replaceAll("_", " ")}
                  </em>
                  <button type="button" onClick={() => open(item)}>
                    {item.status === "NOT_CONFIGURED" ? "Set up" : "Manage"}
                  </button>
                </footer>
              </article>
            );
          })}
          <article className="integration-card coming">
            <header>
              <i className="integration-generic-logo">
                <Plug />
              </i>
              <span>
                <b>Other integrations</b>
                <small>Additional providers will be introduced in the dedicated integration phase.</small>
              </span>
            </header>
            <footer>
              <em>COMING LATER</em>
            </footer>
          </article>
        </div>
      ) : (
        <div className="integration-config">
          <div className="integration-provider-summary">
            <ProviderLogo provider={draft.provider} />
            <span>
              <b>{providers[draft.provider].name}</b>
              <small>{providers[draft.provider].description}</small>
            </span>
            <button
              type="button"
              className="day38-back"
              onClick={() => {
                setDraft(null);
                setSelected(null);
              }}
            >
              <ArrowLeft />
              All integrations
            </button>
          </div>
          <div className="workflow-row">
            <span>
              <b>Configuration enabled</b>
              <small>Save these settings for this company only.</small>
            </span>
            <Toggle
              label="Configuration enabled"
              value={draft.enabled}
              onChange={(enabled) => setDraft({ ...draft, enabled })}
            />
          </div>
          {providers[draft.provider].options.map(([key, label, text]) => (
            <div className="workflow-row" key={key}>
              <span>
                <b>{label}</b>
                <small>{text}</small>
              </span>
              <Toggle
                label={label}
                value={draft.configuration[key]}
                onChange={(value) => setDraft({ ...draft, configuration: { ...draft.configuration, [key]: value } })}
              />
            </div>
          ))}
          <div className="day38-actions">
            <button
              type="button"
              disabled={!dirty || saving}
              onClick={() => selected && setDraft(structuredClone(selected))}
            >
              Cancel
            </button>
            {selected?.status !== "NOT_CONFIGURED" && (
              <button type="button" className="disconnect" disabled={saving} onClick={() => setDisconnect(selected)}>
                <Unplug />
                Disconnect
              </button>
            )}
            <button type="button" className="primary" disabled={!dirty || saving} onClick={() => void save()}>
              {saving && <LoaderCircle className="spin" />}Save changes
            </button>
          </div>
        </div>
      )}
      <ConfirmationDialog
        open={disconnect !== null}
        title="Disconnect integration?"
        description="The saved non-secret configuration remains available, but this integration will be disabled for the current company."
        confirmLabel="Disconnect"
        tone="danger"
        loading={saving}
        onCancel={() => setDisconnect(null)}
        onConfirm={() => void confirmDisconnect()}
      />
    </>
  );
}

export function WorkflowSettings() {
  const [saved, setSaved] = useState<Workflows | null>(null);
  const [draft, setDraft] = useState<Workflows | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    void fetch("/api/company/workflow-settings", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(apiMessage(body, "Unable to load workflow settings."));
        setSaved(body);
        setDraft(body);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load workflow settings."))
      .finally(() => setLoading(false));
  }, []);
  const options = [
    ["task_notifications", BellRing, "Task notifications", "Receive updates for assigned and changed tasks."],
    ["project_updates", FolderKanban, "Project updates", "Receive important project status updates."],
    ["approval_flow", ClipboardCheck, "Approval flow", "Enable the basic approval configuration boundary."],
    ["client_notifications", MessageCircleMore, "Client notifications", "Receive relevant client activity updates."],
  ] as const;
  async function save() {
    if (!draft) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/company/workflow-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(apiMessage(body, "Workflow settings could not be saved."));
      setSaved(body);
      setDraft(body);
      setNotice("Workflow settings updated.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Workflow settings could not be saved.");
    } finally {
      setSaving(false);
    }
  }
  if (loading) return <SettingsState loading text="Loading workflow settings..." />;
  if (!draft) return <SettingsState text={error || "Workflow settings are unavailable."} />;
  const dirty = JSON.stringify(saved) !== JSON.stringify(draft);
  return (
    <>
      <header className="settings-section-title day38-heading">
        <div>
          <span>Workflow controls</span>
          <h3>Company workflows</h3>
        </div>
        <p>Basic company workflow switches only. Automation rules and triggers are implemented later.</p>
      </header>
      {notice && (
        <div className="day38-notice">
          <Check />
          {notice}
        </div>
      )}
      {error && <div className="day38-error">{error}</div>}
      <div className="workflow-list">
        {options.map(([key, Icon, label, text]) => (
          <div className="workflow-row" key={key}>
            <i className="workflow-icon">
              <Icon />
            </i>
            <span>
              <b>{label}</b>
              <small>{text}</small>
            </span>
            <Toggle label={label} value={draft[key]} onChange={(value) => setDraft({ ...draft, [key]: value })} />
          </div>
        ))}
      </div>
      <div className="day38-actions">
        <button type="button" disabled={!dirty || saving} onClick={() => saved && setDraft(structuredClone(saved))}>
          Cancel
        </button>
        <button type="button" className="primary" disabled={!dirty || saving} onClick={() => void save()}>
          {saving && <LoaderCircle className="spin" />}Save changes
        </button>
      </div>
    </>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="day38-toggle">
      <input type="checkbox" checked={value} aria-label={label} onChange={(event) => onChange(event.target.checked)} />
      <i />
    </label>
  );
}
function SettingsState({ loading, text, action }: { loading?: boolean; text: string; action?: () => void }) {
  return (
    <div className="day38-state">
      {loading ? <LoaderCircle className="spin" /> : <Plug />}
      <b>{text}</b>
      {action && (
        <button type="button" onClick={action}>
          Try again
        </button>
      )}
    </div>
  );
}

function ProviderLogo({ provider }: { provider: Provider }) {
  if (provider === "GOOGLE_DRIVE") {
    return (
      <i className="provider-logo drive" aria-label="Google Drive">
        <svg viewBox="0 0 48 48" aria-hidden="true">
          <path fill="#0F9D58" d="M17.3 6h13.4L44 29H30.7z" />
          <path fill="#FFCD40" d="M17.3 6 4 29l6.7 11.5L24 17.5z" />
          <path fill="#4285F4" d="M10.7 40.5 17.3 29H44l-6.7 11.5z" />
        </svg>
      </i>
    );
  }
  if (provider === "SLACK") {
    return (
      <i className="provider-logo slack" aria-label="Slack">
        <svg viewBox="0 0 48 48" aria-hidden="true">
          <rect x="7" y="19" width="17" height="8" rx="4" fill="#36C5F0" />
          <rect x="19" y="7" width="8" height="17" rx="4" fill="#2EB67D" />
          <rect x="24" y="21" width="17" height="8" rx="4" fill="#ECB22E" />
          <rect x="21" y="24" width="8" height="17" rx="4" fill="#E01E5A" />
          <circle cx="11" cy="32" r="4" fill="#36C5F0" />
          <circle cx="32" cy="11" r="4" fill="#2EB67D" />
          <circle cx="37" cy="16" r="4" fill="#ECB22E" />
          <circle cx="16" cy="37" r="4" fill="#E01E5A" />
        </svg>
      </i>
    );
  }
  return (
    <i className="provider-logo stripe" aria-label="Stripe">
      <svg viewBox="0 0 56 40" aria-hidden="true">
        <rect width="56" height="40" rx="10" fill="#635BFF" />
        <text x="28" y="25" textAnchor="middle" fill="white" fontSize="13" fontWeight="800">
          stripe
        </text>
      </svg>
    </i>
  );
}
