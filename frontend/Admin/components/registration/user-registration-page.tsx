"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Eye, EyeOff, LockKeyhole, Mail, Pencil, Plus, UserRound, UsersRound } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
type Fields = { name: string; email: string; password: string; confirm_password: string };
const empty: Fields = { name: "", email: "", password: "", confirm_password: "" };
type RegisteredUser = { id: string; name: string; email: string; status: string };
const validate = (key: keyof Fields, value: string, values: Fields) => {
  if (!value.trim()) return "This field is required.";
  if (key === "name" && value.trim().length < 2) return "Enter at least 2 characters.";
  if (key === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Enter a valid email address.";
  if (
    key === "password" &&
    (value.length < 12 ||
      !/[a-z]/.test(value) ||
      !/[A-Z]/.test(value) ||
      !/\d/.test(value) ||
      !/[^A-Za-z0-9]/.test(value))
  )
    return "Use 12+ characters with uppercase, lowercase, number and symbol.";
  if (key === "confirm_password" && value !== values.password) return "Passwords do not match.";
  return "";
};
export function UserRegistrationPage({
  kind,
  initialMode = "list",
  returnHref,
}: {
  kind: "employee" | "client";
  initialMode?: "list" | "create";
  returnHref?: string;
}) {
  const router = useRouter();
  const title = kind === "employee" ? "Employee" : "Client";
  const invitationMode = kind === "employee";
  const [values, setValues] = useState(empty);
  const [errors, setErrors] = useState<Partial<Record<keyof Fields, string>>>({});
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<RegisteredUser[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [mode, setMode] = useState<"list" | "create">(initialMode);
  const [formLoading, setFormLoading] = useState(false);
  const [confirmCreate, setConfirmCreate] = useState(false);
  const [visiblePasswords, setVisiblePasswords] = useState<Record<"password" | "confirm_password", boolean>>({
    password: false,
    confirm_password: false,
  });
  const endpoint = kind === "employee" ? "employees" : "clients";
  const formFields = invitationMode
    ? (["name", "email"] as (keyof Fields)[])
    : (["name", "email", "password", "confirm_password"] as (keyof Fields)[]);
  const returnToList = () => (returnHref ? router.push(returnHref) : setMode("list"));
  const loadList = useCallback(async () => {
    setListLoading(true);
    try {
      const response = await fetch(`/api/registration/${endpoint}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`Unable to load ${endpoint}.`);
      setItems(await response.json());
    } catch (error) {
      setStatus(error instanceof Error ? error.message : `Unable to load ${endpoint}.`);
    } finally {
      setListLoading(false);
    }
  }, [endpoint]);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => void loadList());
    return () => window.cancelAnimationFrame(frame);
  }, [loadList]);
  const update = (key: keyof Fields, value: string) => {
    const next = { ...values, [key]: value };
    setValues(next);
    setErrors((current) => ({
      ...current,
      [key]: validate(key, value, next),
      ...(key === "password" && next.confirm_password
        ? { confirm_password: validate("confirm_password", next.confirm_password, next) }
        : {}),
    }));
  };
  const submit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const next = Object.fromEntries(
      formFields.map((key) => [key, validate(key, values[key], values)]),
    );
    setErrors(next);
    if (Object.values(next).some(Boolean)) return;
    if (event) {
      setConfirmCreate(true);
      return;
    }
    setLoading(true);
    setStatus("");
    try {
      const response = await fetch(invitationMode ? "/api/company/invitations" : `/api/registration/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          invitationMode
            ? { name: values.name.trim(), email: values.email.trim(), role_code: "COMPANY_EMPLOYEE" }
            : values,
        ),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? `${title} ${invitationMode ? "invitation" : "creation"} failed.`);
      setStatus(
        invitationMode ? `Activation email sent to ${data.email}.` : `${title} ${data.email} created successfully.`,
      );
      setValues(empty);
      if (invitationMode && returnHref) {
        router.push(`${returnHref}?invite=sent&email=${encodeURIComponent(data.email)}`);
        setConfirmCreate(false);
        return;
      }
      await loadList();
      returnToList();
      setConfirmCreate(false);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : `${title} ${invitationMode ? "invitation" : "creation"} failed.`);
      setConfirmCreate(false);
    } finally {
      setLoading(false);
    }
  };
  return (
    <>
      <DashboardHero
        title=""
        highlight={`${title}s`}
        description={`Manage ${title.toLowerCase()} accounts inside your company.`}
        compact
      />
      <div className="dash-content">
        <section className="registration-workspace" aria-live="polite">
          <header className="registration-workspace-header registration-workspace-actions">
            {mode === "list" ? (
              <button
                type="button"
                className="registration-primary-action"
                onClick={() => {
                  setStatus("");
                  setMode("create");
                  setFormLoading(true);
                  window.setTimeout(() => setFormLoading(false), 350);
                }}
              >
                <Plus aria-hidden="true" /> {invitationMode ? `Invite ${title.toLowerCase()}` : `Create ${title.toLowerCase()}`}
              </button>
            ) : (
              <button type="button" className="registration-back-action" onClick={returnToList}>
                <ArrowLeft aria-hidden="true" /> Back to {title.toLowerCase()}s
              </button>
            )}
          </header>
          {mode === "list" ? (
            <>
              {status && <div className="registration-status registration-list-status">{status}</div>}
              {listLoading ? (
                <div className="registration-list-loading">
                  <i className="registration-spinner" /> Loading {endpoint}…
                </div>
              ) : items.length ? (
                <div className="registration-table" role="table">
                  <div className="registration-table-head" role="row">
                    <span>Name</span>
                    <span>Email</span>
                    <span>Status</span>
                    <span>Actions</span>
                  </div>
                  {items.map((item) => (
                    <article key={item.id} role="row">
                      <div className="registration-row-identity">
                        <strong>{item.name}</strong>
                      </div>
                      <small>{item.email}</small>
                      <div className="registration-row-meta">
                        <span>{item.status}</span>
                        <div className="registration-row-actions">
                          <button
                            type="button"
                            aria-label={`View ${item.name}`}
                            title="View details (coming soon)"
                            disabled
                          >
                            <Eye aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            aria-label={`Edit ${item.name}`}
                            title="Edit account (coming soon)"
                            disabled
                          >
                            <Pencil aria-hidden="true" />
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="registration-empty">No {endpoint} found.</div>
              )}
            </>
          ) : formLoading ? (
            <div className="registration-form-loading" role="status">
              <i className="registration-spinner" aria-hidden="true" /> Preparing {title.toLowerCase()} form…
            </div>
          ) : (
            <div className="registration-card registration-card-embedded">
              <header className="registration-form-heading">
                <div className="registration-form-icon" aria-hidden="true">
                  <UsersRound />
                </div>
                <div>
                  <span>NEW {title.toUpperCase()}</span>
                  <h2>{invitationMode ? `Send ${title.toLowerCase()} activation email` : `Create ${title.toLowerCase()} account`}</h2>
                  <p>
                    {invitationMode
                      ? `Create the ${title.toLowerCase()} profile and send a secure email so they can set their own password.`
                      : "Add the account details below. Access is controlled by the company role and permissions."}
                  </p>
                </div>
              </header>
              <form noValidate onSubmit={submit}>
                {formFields.map((key) => {
                  const passwordField = key === "password" || key === "confirm_password";
                  const visible = passwordField ? visiblePasswords[key] : false;
                  const FieldIcon = key === "name" ? UserRound : key === "email" ? Mail : LockKeyhole;
                  return (
                    <label key={key}>
                      <span className="registration-field-label">
                        {key === "confirm_password" ? "Confirm password" : key[0].toUpperCase() + key.slice(1)}
                      </span>
                      <span className="registration-input-shell">
                        <FieldIcon aria-hidden="true" />
                        <input
                          type={passwordField && !visible ? "password" : key === "email" ? "email" : "text"}
                          autoComplete={key === "email" ? "email" : passwordField ? "new-password" : "name"}
                          placeholder={
                            key === "name"
                              ? `${title} full name`
                              : key === "email"
                                ? "name@company.com"
                                : key === "confirm_password"
                                  ? "Repeat the password"
                                  : "Create a secure password"
                          }
                          value={values[key]}
                          onChange={(event) => update(key, event.target.value)}
                          aria-invalid={Boolean(errors[key])}
                        />
                        {passwordField && (
                          <button
                            type="button"
                            className="registration-password-toggle"
                            aria-label={`${visible ? "Hide" : "Show"} ${key === "password" ? "password" : "confirmed password"}`}
                            onClick={() => setVisiblePasswords((current) => ({ ...current, [key]: !current[key] }))}
                          >
                            {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                          </button>
                        )}
                      </span>
                      {errors[key] && <small>{errors[key]}</small>}
                    </label>
                  );
                })}
                <div className="registration-form-footer">
                  <button type="button" className="registration-form-cancel" onClick={returnToList}>
                    Cancel
                  </button>
                  <button type="submit" className="registration-form-submit" disabled={loading}>
                    {loading && <i className="registration-spinner" aria-hidden="true" />}
                    {loading ? (invitationMode ? "Sending…" : "Creating…") : invitationMode ? "Send activation email" : `Create ${title}`}
                  </button>
                </div>
                {status && <div className="registration-status">{status}</div>}
              </form>
            </div>
          )}
        </section>
      </div>
      <ConfirmationDialog
        open={confirmCreate}
        title={invitationMode ? `Send ${title.toLowerCase()} activation email?` : `Create this ${title.toLowerCase()} account?`}
        description={
          invitationMode
            ? `The ${title.toLowerCase()} will receive a secure mail to activate the account and set a password.`
            : `The ${title.toLowerCase()} will receive the role and permissions defined for this company.`
        }
        confirmLabel={invitationMode ? "Send email" : `Create ${title}`}
        loading={loading}
        onCancel={() => setConfirmCreate(false)}
        onConfirm={() => void submit()}
      />
    </>
  );
}
