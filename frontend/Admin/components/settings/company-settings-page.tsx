"use client";

import { ChangeEvent, FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  BellRing,
  Building2,
  Check,
  Clock3,
  Contact,
  CircleDollarSign,
  ImageIcon,
  PlugZap,
  Settings2,
  Trash2,
  Upload,
  Workflow,
} from "lucide-react";
import Image from "next/image";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { IntegrationsSettings, WorkflowSettings } from "@/components/settings/integrations-workflow-settings";
import { ServicesPricingSettings } from "@/components/settings/services-pricing-settings";
import { PhoneInput } from "@loopless-shared/forms/phone-input";

type Settings = {
  company_id: string;
  company_code: string;
  updated_at: string;
  general: { company_name: string; description: string | null };
  branding: {
    logo_url: string | null;
    favicon_url: string | null;
    primary_color: string;
    secondary_color: string;
    accent_color: string;
    info_color: string;
    success_color: string;
    warning_color: string;
    danger_color: string;
    email_footer: string;
  };
  contact: {
    business_email: string | null;
    support_email: string | null;
    phone: string | null;
    support_phone: string | null;
    website: string | null;
    address: string | null;
    gst_tax_id: string | null;
    registration_number: string | null;
  };
  regional: { timezone: string; language: string; currency: string; date_format: string; time_format: string };
  notifications: { email: boolean; system: boolean; maintenance: boolean; security: boolean };
  preferences: { working_days: string[]; business_hours_start: string; business_hours_end: string; theme: string };
};
const tabs = [
  ["general", Building2, "Profile", "Identity and company profile"],
  ["branding", ImageIcon, "Branding", "Logo and color system"],
  ["contact", Contact, "Contact", "Business and legal details"],
  ["regional", Clock3, "Regional", "Locale and display formats"],
  ["notifications", BellRing, "Notifications", "Company-wide alerts"],
  ["preferences", Settings2, "Preferences", "Schedule and appearance"],
  ["services", CircleDollarSign, "Services & Pricing", "Catalog and pricing controls"],
  ["integrations", PlugZap, "Integrations", "External service configuration"],
  ["workflows", Workflow, "Workflows", "Company workflow switches"],
] as const;
const weekdays = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"];
const timezones = [
  "UTC",
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Singapore",
  "Europe/London",
  "America/New_York",
  "America/Los_Angeles",
];
export function CompanySettingsPage() {
  const [data, setData] = useState<Settings | null>(null);
  const [savedData, setSavedData] = useState<Settings | null>(null);
  const [tab, setTab] = useState<(typeof tabs)[number][0]>("general");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [confirm, setConfirm] = useState<"save" | "logo" | "favicon" | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    void fetch("/api/company/settings", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Settings could not be loaded.");
        setData(body);
        setSavedData(body);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Settings could not be loaded."))
      .finally(() => setLoading(false));
  }, []);
  const dirty = useMemo(
    () => Boolean(data && savedData && JSON.stringify(data) !== JSON.stringify(savedData)),
    [data, savedData],
  );
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(""), 3200);
    return () => window.clearTimeout(timer);
  }, [message]);
  const change = (
    section: Exclude<keyof Settings, "company_id" | "company_code" | "updated_at">,
    key: string,
    value: unknown,
  ) =>
    setData((current) =>
      current ? ({ ...current, [section]: { ...(current[section] as object), [key]: value } } as Settings) : current,
    );
  function publishBranding(settings: Settings, overrides: Partial<Settings["branding"]> = {}) {
    const branding = { ...settings.branding, ...overrides };
    window.dispatchEvent(
      new CustomEvent("loopless-company-branding", {
        detail: {
          company_id: settings.company_id,
          company_name: settings.general.company_name,
          logo_url: branding.logo_url,
          favicon_url: branding.favicon_url,
          primary_color: branding.primary_color,
          secondary_color: branding.secondary_color,
          accent_color: branding.accent_color,
          info_color: branding.info_color,
          success_color: branding.success_color,
          warning_color: branding.warning_color,
          danger_color: branding.danger_color,
        },
      }),
    );
  }
  async function save(nextData: Settings | null = data, successMessage = "Company settings saved successfully.") {
    if (!nextData) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/company/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          general: nextData.general,
          branding: nextData.branding,
          contact: nextData.contact,
          regional: nextData.regional,
          notifications: nextData.notifications,
          preferences: nextData.preferences,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Settings could not be saved.");
      setData(body);
      setSavedData(body);
      publishBranding(body);
      setMessage(successMessage);
      setConfirm(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Settings could not be saved.");
      setConfirm(null);
    } finally {
      setSaving(false);
    }
  }
  async function upload(asset: "logo" | "favicon", event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 2 * 1024 * 1024) {
      setError("Use a PNG, JPG or WebP image up to 2 MB.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/company/settings/branding/${asset}`, { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Upload failed.");
      change("branding", asset === "logo" ? "logo_url" : "favicon_url", body.url);
      setSavedData((current) =>
        current
          ? {
              ...current,
              branding: { ...current.branding, [asset === "logo" ? "logo_url" : "favicon_url"]: body.url },
            }
          : current,
      );
      if (data) publishBranding(data, { [asset === "logo" ? "logo_url" : "favicon_url"]: body.url });
      setMessage(`${asset === "logo" ? "Logo" : "Favicon"} uploaded successfully.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
    } finally {
      setSaving(false);
      event.target.value = "";
    }
  }
  async function removeAsset(asset: "logo" | "favicon") {
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/company/settings/branding/${asset}`, { method: "DELETE" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Asset could not be removed.");
      change("branding", asset === "logo" ? "logo_url" : "favicon_url", null);
      setSavedData((current) =>
        current
          ? {
              ...current,
              branding: { ...current.branding, [asset === "logo" ? "logo_url" : "favicon_url"]: null },
            }
          : current,
      );
      if (data) publishBranding(data, { [asset === "logo" ? "logo_url" : "favicon_url"]: null });
      setMessage(`${asset === "logo" ? "Logo" : "Favicon"} removed successfully.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Asset could not be removed.");
    } finally {
      setSaving(false);
      setConfirm(null);
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (dirty) setConfirm("save");
  }
  return (
    <>
      <DashboardHero
        title="Company"
        highlight="Settings"
        description="Manage your company identity, regional defaults and workspace preferences."
      />
      <div className="dash-content company-settings-page">
        {loading ? (
          <div className="company-settings-loading">
            <i />
            <span>Loading company settings…</span>
          </div>
        ) : (
          data && (
            <form onSubmit={submit}>
              <header className="company-settings-heading">
                <div>
                  <span>Company configuration</span>
                  <h2>{tabs.find((item) => item[0] === tab)?.[2]}</h2>
                  <p>Changes apply only to {data.general.company_name}.</p>
                </div>
                <small>Company code · {data.company_code}</small>
              </header>
              <nav className="company-settings-tabs" aria-label="Company settings sections">
                <span className="company-settings-nav-label">Company controls</span>
                {tabs.map(([key, Icon, label, description]) => (
                  <button
                    type="button"
                    key={key}
                    className={tab === key ? "active" : ""}
                    onClick={() => {
                      setTab(key);
                      setMessage("");
                    }}
                  >
                    <i>
                      <Icon />
                    </i>
                    <span>
                      <b>{label}</b>
                      <small>{description}</small>
                    </span>
                  </button>
                ))}
              </nav>
              <section className="company-settings-panel">
                {tab === "general" && (
                  <>
                    <SectionTitle
                      title="Company profile"
                      text="The authoritative identity used across this company workspace."
                    />
                    <Fields>
                      <Field label="Company name">
                        <input
                          required
                          minLength={2}
                          value={data.general.company_name}
                          onChange={(e) => change("general", "company_name", e.target.value)}
                        />
                      </Field>
                      <Field label="Company code">
                        <input value={data.company_code} disabled />
                      </Field>
                      <Field label="Company description" wide>
                        <textarea
                          rows={4}
                          maxLength={1000}
                          placeholder="Describe your company, its purpose and services."
                          value={data.general.description ?? ""}
                          onChange={(e) => change("general", "description", e.target.value || null)}
                        />
                      </Field>
                    </Fields>
                  </>
                )}
                {tab === "branding" && (
                  <>
                    <SectionTitle
                      title="Branding"
                      text="Company-specific assets and colors. Global platform branding is not changed."
                    />
                    <div className="branding-coming-soon">
                      <span>Coming soon</span>
                      <div>
                        <b>Advanced color system</b>
                        <small>
                          Dashboard, navigation, buttons, alerts and status colors will launch together as one
                          consistent design system.
                        </small>
                      </div>
                    </div>
                    <div className="branding-upload-grid">
                      <Asset
                        label="Company logo"
                        url={data.branding.logo_url}
                        onChange={(e) => void upload("logo", e)}
                        onRemove={() => setConfirm("logo")}
                      />
                      <Asset
                        label="Browser favicon"
                        url={data.branding.favicon_url}
                        onChange={(e) => void upload("favicon", e)}
                        onRemove={() => setConfirm("favicon")}
                      />
                    </div>
                    <Fields>
                      <Field label="Email footer" wide>
                        <textarea
                          rows={3}
                          maxLength={500}
                          value={data.branding.email_footer}
                          onChange={(e) => change("branding", "email_footer", e.target.value)}
                        />
                      </Field>
                    </Fields>
                  </>
                )}
                {tab === "contact" && (
                  <>
                    <SectionTitle
                      title="Contact & legal"
                      text="Business contact and statutory information for this company."
                    />
                    <Fields>
                      {(
                        [
                          ["Business email", "business_email", "email"],
                          ["Support email", "support_email", "email"],
                          ["Phone", "phone", "tel"],
                          ["Support phone", "support_phone", "tel"],
                          ["Website", "website", "url"],
                          ["GST / Tax ID", "gst_tax_id", "text"],
                          ["Registration number", "registration_number", "text"],
                        ] as const
                      ).map(([label, key, type]) => (
                        <Field label={label} key={key}>
                          {type === "tel" ? (
                            <PhoneInput
                              value={data.contact[key] ?? ""}
                              onChange={(value) => change("contact", key, value || null)}
                            >
                              {(phone) => <input {...phone} />}
                            </PhoneInput>
                          ) : (
                            <input
                              type={type}
                              value={data.contact[key] ?? ""}
                              onChange={(e) => change("contact", key, e.target.value || null)}
                            />
                          )}
                        </Field>
                      ))}
                      <Field label="Business address" wide>
                        <textarea
                          rows={3}
                          value={data.contact.address ?? ""}
                          onChange={(e) => change("contact", "address", e.target.value || null)}
                        />
                      </Field>
                    </Fields>
                  </>
                )}
                {tab === "regional" && (
                  <>
                    <SectionTitle
                      title="Regional settings"
                      text="Defaults used for dates, time and financial display."
                    />
                    <Fields>
                      <Field label="Timezone">
                        <LooplessSelect
                          value={data.regional.timezone}
                          onValueChange={(value) => change("regional", "timezone", value)}
                          ariaLabel="Company timezone"
                          options={[
                            ...(!timezones.includes(data.regional.timezone) ? [data.regional.timezone] : []),
                            ...timezones,
                          ].map((value) => ({ value, label: value }))}
                        />
                      </Field>
                      <Field label="Language">
                        <LooplessSelect
                          value={data.regional.language}
                          onValueChange={(value) => change("regional", "language", value)}
                          ariaLabel="Company language"
                          options={[
                            { value: "en", label: "English" },
                            { value: "te-IN", label: "తెలుగు" },
                            { value: "hi-IN", label: "हिन्दी" },
                          ]}
                        />
                      </Field>
                      <Field label="Currency">
                        <LooplessSelect
                          value={data.regional.currency}
                          onValueChange={(value) => change("regional", "currency", value)}
                          ariaLabel="Company currency"
                          options={["USD", "INR", "EUR", "GBP"].map((value) => ({ value, label: value }))}
                        />
                      </Field>
                      <Field label="Date format">
                        <LooplessSelect
                          value={data.regional.date_format}
                          onValueChange={(value) => change("regional", "date_format", value)}
                          ariaLabel="Date format"
                          options={["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"].map((value) => ({ value, label: value }))}
                        />
                      </Field>
                      <Field label="Time format">
                        <LooplessSelect
                          value={data.regional.time_format}
                          onValueChange={(value) => change("regional", "time_format", value)}
                          ariaLabel="Time format"
                          options={[
                            { value: "12_HOUR", label: "12 hour" },
                            { value: "24_HOUR", label: "24 hour" },
                          ]}
                        />
                      </Field>
                    </Fields>
                  </>
                )}
                {tab === "notifications" && (
                  <>
                    <SectionTitle
                      title="Notification preferences"
                      text="Choose which company-wide notifications are enabled."
                    />
                    <div className="settings-switch-list">
                      {(
                        [
                          ["email", "Email notifications", "Transactional and company email updates"],
                          ["system", "System notifications", "Important activity inside the workspace"],
                          ["maintenance", "Maintenance notifications", "Planned maintenance and service updates"],
                          ["security", "Security alerts", "Account and tenant security events"],
                        ] as const
                      ).map(([key, label, text]) => (
                        <label key={key}>
                          <span>
                            <b>{label}</b>
                            <small>{text}</small>
                          </span>
                          <input
                            type="checkbox"
                            checked={data.notifications[key]}
                            onChange={(e) => change("notifications", key, e.target.checked)}
                          />
                          <i />
                        </label>
                      ))}
                    </div>
                  </>
                )}
                {tab === "preferences" && (
                  <>
                    <SectionTitle
                      title="Workspace preferences"
                      text="Set the default working schedule and appearance."
                    />
                    <Fields>
                      <Field label="Business hours start">
                        <input
                          type="time"
                          value={data.preferences.business_hours_start}
                          onChange={(e) => change("preferences", "business_hours_start", e.target.value)}
                        />
                      </Field>
                      <Field label="Business hours end">
                        <input
                          type="time"
                          value={data.preferences.business_hours_end}
                          onChange={(e) => change("preferences", "business_hours_end", e.target.value)}
                        />
                      </Field>
                      <Field label="Default theme">
                        <LooplessSelect
                          value={data.preferences.theme}
                          onValueChange={(value) => change("preferences", "theme", value)}
                          ariaLabel="Default theme"
                          options={[
                            { value: "system", label: "System" },
                            { value: "light", label: "Light" },
                            { value: "dark", label: "Dark" },
                          ]}
                        />
                      </Field>
                      <Field label="Working days" wide>
                        <div className="working-days">
                          {weekdays.map((day) => (
                            <button
                              type="button"
                              key={day}
                              className={data.preferences.working_days.includes(day) ? "active" : ""}
                              onClick={() =>
                                change(
                                  "preferences",
                                  "working_days",
                                  data.preferences.working_days.includes(day)
                                    ? data.preferences.working_days.filter((item) => item !== day)
                                    : [...data.preferences.working_days, day],
                                )
                              }
                            >
                              {day.slice(0, 3)}
                            </button>
                          ))}
                        </div>
                      </Field>
                    </Fields>
                  </>
                )}
                {tab === "services" && data && <ServicesPricingSettings currency={data.regional.currency} />}
                {tab === "integrations" && <IntegrationsSettings />}
                {tab === "workflows" && <WorkflowSettings />}
                {tab !== "integrations" && tab !== "workflows" && tab !== "services" && (
                  <footer>
                    <span className={dirty ? "settings-dirty active" : "settings-dirty"}>
                      {dirty ? "Unsaved changes" : "All changes saved"}
                    </span>
                    <button
                      className="cancel-company-settings"
                      type="button"
                      disabled={!dirty || saving}
                      onClick={() => savedData && setData(structuredClone(savedData))}
                    >
                      Cancel
                    </button>
                    <button className="save-company-settings" type="submit" disabled={!dirty || saving}>
                      {saving && <i />}Save changes
                    </button>
                  </footer>
                )}
              </section>
            </form>
          )
        )}
      </div>
      {message && (
        <div className="company-settings-toast" role="status">
          <Check /> {message}
        </div>
      )}
      {error && (
        <div className="company-settings-toast error" role="alert">
          {error}
        </div>
      )}
      <ConfirmationDialog
        open={confirm !== null}
        title={confirm === "save" ? "Save company settings?" : `Remove company ${confirm}?`}
        description={
          confirm === "save"
            ? "These changes apply only to your company workspace."
            : "The current asset will be removed and the default company identity will be shown."
        }
        confirmLabel={confirm === "save" ? "Save settings" : "Remove asset"}
        loading={saving}
        onCancel={() => setConfirm(null)}
        onConfirm={() => (confirm === "save" ? void save() : confirm ? void removeAsset(confirm) : undefined)}
      />
    </>
  );
}
function SectionTitle({ title, text }: { title: string; text: string }) {
  return (
    <header className="settings-section-title">
      <div>
        <span>Company settings</span>
        <h3>{title}</h3>
      </div>
      <p>{text}</p>
    </header>
  );
}
function Fields({ children }: { children: ReactNode }) {
  return <div className="company-settings-fields">{children}</div>;
}
function Field({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <label className={wide ? "wide" : ""}>
      <span>{label}</span>
      {children}
    </label>
  );
}
function Asset({
  label,
  url,
  onChange,
  onRemove,
}: {
  label: string;
  url: string | null;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="settings-asset">
      <div>
        {url ? (
          <Image
            unoptimized
            width={76}
            height={76}
            src={`/api/company/settings/branding/file?path=${encodeURIComponent(url)}`}
            alt={`${label} preview`}
          />
        ) : (
          <ImageIcon />
        )}
      </div>
      <span>
        <b>{label}</b>
        <small>PNG, JPG or WebP · maximum 2 MB</small>
        <label>
          <Upload />
          Upload
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={onChange} />
        </label>
        {url && (
          <button type="button" className="remove-brand-asset" onClick={onRemove}>
            <Trash2 /> Remove
          </button>
        )}
      </span>
    </div>
  );
}
