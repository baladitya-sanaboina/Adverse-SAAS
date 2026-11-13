"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Building2, FileText, Hash, MapPin, Plus, RefreshCw, Search } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import "@/styles/organization.css";

type Kind = "departments" | "branches";
type Item = {
  id: string;
  name: string;
  description?: string;
  code?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  status: "ACTIVE" | "INACTIVE";
  created_at: string;
  updated_at: string;
};
type Values = {
  name: string;
  description: string;
  code: string;
  address: string;
  city: string;
  state: string;
  country: string;
  status: "ACTIVE" | "INACTIVE";
};
const empty: Values = {
  name: "",
  description: "",
  code: "",
  address: "",
  city: "",
  state: "",
  country: "",
  status: "ACTIVE",
};

export function OrganizationPage({ kind }: { kind: Kind }) {
  const singular = kind === "departments" ? "Department" : "Branch";
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState<Item | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [values, setValues] = useState<Values>(empty);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [statusItem, setStatusItem] = useState<Item | null>(null);
  const endpoint = `/api/company/${kind}`;

  const query = useMemo(
    () => new URLSearchParams({ ...(search ? { search } : {}), ...(status ? { status } : {}) }).toString(),
    [search, status],
  );
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${endpoint}${query ? `?${query}` : ""}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail);
      setItems(data.items);
    } catch {
      setError(`Unable to load ${kind}.`);
    } finally {
      setLoading(false);
    }
  }, [endpoint, kind, query]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  function openForm(item?: Item) {
    setEditing(item ?? null);
    setFieldErrors({});
    setError("");
    setNotice("");
    setValues(
      item
        ? {
            ...empty,
            ...item,
            description: item.description ?? "",
            code: item.code ?? "",
            address: item.address ?? "",
            city: item.city ?? "",
            state: item.state ?? "",
            country: item.country ?? "",
          }
        : empty,
    );
    setFormOpen(true);
  }
  function closeForm() {
    setFormOpen(false);
    setEditing(null);
    setFieldErrors({});
    setError("");
  }
  function update(key: keyof Values, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    const required = key === "name" || (kind === "branches" && key === "code");
    setFieldErrors((current) => ({
      ...current,
      [key]:
        required && !value.trim()
          ? "This field is required."
          : key === "code" && value && !/^[A-Za-z0-9-]+$/.test(value)
            ? "Use letters, numbers or hyphens only."
            : "",
    }));
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (values.name.trim().length < 2) errors.name = "Enter at least 2 characters.";
    if (kind === "branches" && !/^[A-Za-z0-9-]{2,12}$/.test(values.code))
      errors.code = "Enter a valid 2–12 character code.";
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    setSaving(true);
    const payload =
      kind === "departments"
        ? { name: values.name, description: values.description, ...(editing ? { status: values.status } : {}) }
        : {
            name: values.name,
            code: values.code,
            address: values.address,
            city: values.city,
            state: values.state,
            country: values.country,
            ...(editing ? { status: values.status } : {}),
          };
    try {
      const response = await fetch(editing ? `${endpoint}/${editing.id}` : endpoint, {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? `Unable to save ${singular.toLowerCase()}.`);
      closeForm();
      setNotice(`${singular} ${editing ? "updated" : "created"} successfully.`);
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `Unable to save ${singular.toLowerCase()}.`);
    } finally {
      setSaving(false);
    }
  }
  async function updateStatus() {
    if (!statusItem) return;
    setSaving(true);
    setError("");
    const activating = statusItem.status === "INACTIVE";
    try {
      const response = await fetch(`${endpoint}/${statusItem.id}`, {
        method: activating ? "PATCH" : "DELETE",
        ...(activating
          ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "ACTIVE" }) }
          : {}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail);
      setNotice(`${singular} ${activating ? "enabled" : "disabled"} successfully.`);
      setStatusItem(null);
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : `Unable to update ${singular.toLowerCase()} status.`,
      );
      setStatusItem(null);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight={singular === "Department" ? "Departments" : "Branches"}
        description={`Manage tenant-scoped ${kind} for your company.`}
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace" aria-live="polite">
          {notice && <div className="organization-notice">{notice}</div>}
          {formOpen ? (
            <>
              <header className="management-toolbar">
                <button type="button" className="management-back" onClick={closeForm}>
                  <ArrowLeft /> Back to {kind}
                </button>
                <span>{editing ? `Edit ${singular}` : `New ${singular}`}</span>
              </header>
              <section className="management-editor organization-form-card">
                <header>
                  <i aria-hidden="true">{kind === "departments" ? <Building2 /> : <MapPin />}</i>
                  <div>
                    <span>{editing ? `EDIT ${singular.toUpperCase()}` : `NEW ${singular.toUpperCase()}`}</span>
                    <h2>{editing ? `Edit ${singular.toLowerCase()}` : `Create ${singular.toLowerCase()}`}</h2>
                    <p>
                      {kind === "departments"
                        ? "Keep department information clear for employee assignment and reporting."
                        : "Maintain the branch identity and location used across your company."}
                    </p>
                  </div>
                </header>
                <form className="management-form organization-form-grid" noValidate onSubmit={save}>
                  {error && <div className="management-form-message">{error}</div>}
                  <label className="management-field">
                    <span>{singular} name</span>
                    <span className="management-input">
                      <Building2 aria-hidden="true" />
                      <input
                        value={values.name}
                        onChange={(event) => update("name", event.target.value)}
                        aria-invalid={Boolean(fieldErrors.name)}
                      />
                    </span>
                    {fieldErrors.name && <small>{fieldErrors.name}</small>}
                  </label>
                  {kind === "departments" ? (
                    <label className="management-field wide organization-wide">
                      <span>Description</span>
                      <span className="management-input organization-textarea-shell">
                        <FileText aria-hidden="true" />
                        <textarea
                          value={values.description}
                          onChange={(event) => update("description", event.target.value)}
                          placeholder="Describe this department and its responsibility"
                        />
                      </span>
                    </label>
                  ) : (
                    <>
                      {(["code", "address", "city", "state", "country"] as const).map((key) => (
                        <label
                          className={`management-field ${key === "address" ? "wide organization-wide" : ""}`}
                          key={key}
                        >
                          <span>{key[0].toUpperCase() + key.slice(1)}</span>
                          <span className="management-input">
                            {key === "code" ? <Hash aria-hidden="true" /> : <MapPin aria-hidden="true" />}
                            <input
                              value={values[key]}
                              onChange={(event) => update(key, event.target.value)}
                              aria-invalid={Boolean(fieldErrors[key])}
                            />
                          </span>
                          {fieldErrors[key] && <small>{fieldErrors[key]}</small>}
                        </label>
                      ))}
                    </>
                  )}
                  {editing && (
                    <label className="management-field">
                      <span>Status</span>
                      <LooplessSelect
                        value={values.status}
                        onValueChange={(value) => update("status", value)}
                        ariaLabel={`${singular} status`}
                        options={[
                          { value: "ACTIVE", label: "Active" },
                          { value: "INACTIVE", label: "Inactive" },
                        ]}
                      />
                    </label>
                  )}
                  <div className="management-form-footer">
                    <button type="button" className="management-secondary-action" onClick={closeForm}>
                      Cancel
                    </button>
                    <button type="submit" className="management-primary-action" disabled={saving}>
                      {saving && <RefreshCw className="spin" />}
                      {saving ? "Saving…" : editing ? "Save changes" : `Create ${singular.toLowerCase()}`}
                    </button>
                  </div>
                </form>
              </section>
            </>
          ) : (
            <>
              <header className="management-toolbar">
                <div>
                  <span>Company organization</span>
                  <strong>
                    {items.length} {kind}
                  </strong>
                </div>
                <button onClick={() => openForm()}>
                  <Plus /> Create {singular.toLowerCase()}
                </button>
              </header>
              <div className="organization-tools">
                <label>
                  <Search />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder={`Search ${kind}`}
                  />
                </label>
                <LooplessSelect
                  value={status}
                  onValueChange={setStatus}
                  ariaLabel={`Filter ${kind} by status`}
                  options={[
                    { value: "", label: "All statuses" },
                    { value: "ACTIVE", label: "Active" },
                    { value: "INACTIVE", label: "Inactive" },
                  ]}
                />
              </div>
              {error ? (
                <div className="organization-state">
                  <h3>{error}</h3>
                  <button onClick={() => void load()}>Retry</button>
                </div>
              ) : loading ? (
                <div className="organization-skeleton">
                  {[1, 2, 3].map((row) => (
                    <i key={row} />
                  ))}
                </div>
              ) : items.length === 0 ? (
                <div className="organization-state">
                  {kind === "departments" ? <Building2 /> : <MapPin />}
                  <h3>No {kind} yet</h3>
                  <p>Create your first {singular.toLowerCase()}.</p>
                  <button onClick={() => openForm()}>
                    <Plus /> Add {singular.toLowerCase()}
                  </button>
                </div>
              ) : (
                <div className={`organization-table ${kind}`} role="table">
                  <div className="organization-table-head">
                    <span>Name</span>
                    <span>{kind === "departments" ? "Description" : "Code"}</span>
                    {kind === "branches" && <span>Location</span>}
                    <span>Status</span>
                    <span>Actions</span>
                  </div>
                  {items.map((item) => (
                    <article key={item.id}>
                      <strong>{item.name}</strong>
                      <span>{kind === "departments" ? item.description || "—" : item.code}</span>
                      {kind === "branches" && <span>{[item.city, item.state].filter(Boolean).join(", ") || "—"}</span>}
                      <em className={item.status.toLowerCase()}>{item.status}</em>
                      <CrudActionButtons
                        edit={{ label: `Edit ${item.name}`, onClick: () => openForm(item) }}
                        toggle={{
                          label: `${item.status === "ACTIVE" ? "Disable" : "Enable"} ${item.name}`,
                          onClick: () => setStatusItem(item),
                        }}
                        active={item.status === "ACTIVE"}
                      />
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
      <ConfirmationDialog
        open={Boolean(statusItem)}
        title={`${statusItem?.status === "ACTIVE" ? "Disable" : "Enable"} ${statusItem?.name ?? singular}?`}
        description={
          statusItem?.status === "ACTIVE"
            ? "It will remain in history but cannot be selected for future assignments."
            : "It will become available again for future assignments."
        }
        confirmLabel={`${statusItem?.status === "ACTIVE" ? "Disable" : "Enable"} ${singular.toLowerCase()}`}
        loading={saving}
        tone={statusItem?.status === "ACTIVE" ? "danger" : "primary"}
        onCancel={() => setStatusItem(null)}
        onConfirm={() => void updateStatus()}
      />
    </>
  );
}
