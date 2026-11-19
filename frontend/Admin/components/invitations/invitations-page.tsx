"use client";

import { useCallback, useEffect, useState } from "react";
import { BriefcaseBusiness, Mail, MailPlus, Phone, RefreshCw, RotateCw, UserRound, X } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { ManagementModal } from "@/components/foundation/management-modal";
import "@/styles/invitations.css";
import { LooplessDate } from "@/components/foundation/loopless-date";

type InvitationRoleCode = "COMPANY_EMPLOYEE" | "COMPANY_MANAGER" | "COMPANY_CLIENT";
type Invitation = {
  id: string;
  email: string;
  notification_email: string;
  role_code: InvitationRoleCode;
  status: "PENDING" | "ACCEPTED" | "EXPIRED" | "REVOKED";
  expires_at: string;
  created_at: string;
};

const roleOptions = [
  { value: "COMPANY_EMPLOYEE", label: "Employee" },
  { value: "COMPANY_MANAGER", label: "Manager" },
  { value: "COMPANY_CLIENT", label: "Client" },
] as const;
const phonePattern = /^\+?[0-9 ()-]{7,24}$/;
// Logins are internal addresses that work only inside Adverse; outside mail goes to their Gmail
// (owner request 2026-11-19).
const INTERNAL_DOMAIN = "adverseindia.com";
const isInternal = (value: string) => value.trim().toLowerCase().endsWith(`@${INTERNAL_DOMAIN}`);
const withDomain = (value: string) => {
  const trimmed = value.trim().toLowerCase();
  return trimmed && !trimmed.includes("@") ? `${trimmed}@${INTERNAL_DOMAIN}` : trimmed;
};
const suggestLogin = (fullName: string) => {
  const parts = fullName
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z\s]/g, "")
    .split(/\s+/)
    .filter(Boolean);
  return parts.length ? `${parts.slice(0, 2).join(".")}@${INTERNAL_DOMAIN}` : "";
};
const loginError = (value: string) =>
  !value.trim()
    ? "Internal login email is required."
    : !/^\S+@\S+\.\S+$/.test(withDomain(value))
      ? "Please enter a valid email address."
      : !isInternal(withDomain(value))
        ? `The login must end with @${INTERNAL_DOMAIN}.`
        : "";
const gmailError = (value: string, login: string) =>
  !value.trim()
    ? "Their Gmail is required: the setup link goes there."
    : !/^\S+@\S+\.\S+$/.test(value.trim())
      ? "Please enter a valid email address."
      : isInternal(value)
        ? `Use their own Gmail, not an @${INTERNAL_DOMAIN} address.`
        : value.trim().toLowerCase() === withDomain(login)
          ? "The Gmail and the login must be different."
          : "";
type Department = { id: string; name: string; status: string };

const roleLabel = (roleCode: InvitationRoleCode) =>
  roleOptions.find((option) => option.value === roleCode)?.label ?? "User";

export function InvitationsPage() {
  const [items, setItems] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);
  const [roleCode, setRoleCode] = useState<InvitationRoleCode>("COMPANY_EMPLOYEE");
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState("");
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [notificationEmail, setNotificationEmail] = useState("");
  const [notificationEmailError, setNotificationEmailError] = useState("");
  const [phone, setPhone] = useState("");
  const [phoneError, setPhoneError] = useState("");
  const [loginTouched, setLoginTouched] = useState(false);
  const [designation, setDesignation] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [departments, setDepartments] = useState<Department[]>([]);
  const staffRole = roleCode !== "COMPANY_CLIENT";
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [action, setAction] = useState<{ item: Invitation; type: "resend" | "revoke" } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/company/invitations", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to load invitations.");
      setItems(data.items ?? []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load invitations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  // Departments for the invite form (employees and managers).
  useEffect(() => {
    if (!open) return;
    let live = true;
    fetch("/api/company/departments", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: { items?: Department[] } | null) => {
        if (live && data?.items) setDepartments(data.items.filter((item) => item.status === "ACTIVE"));
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [open]);

  async function invite(event: React.FormEvent) {
    event.preventDefault();
    const nextNameError = !name.trim()
      ? "Full name is required."
      : name.trim().length < 2
        ? "Enter at least 2 characters."
        : "";
    // Clients sign in with their Gmail; their Adverse ID is made from the name when empty.
    const nextEmailError = roleCode === "COMPANY_CLIENT" && !email.trim() ? "" : loginError(email);
    const nextNotificationEmailError = gmailError(notificationEmail, email);
    const nextPhoneError = !phone.trim()
      ? "Mobile number is required."
      : phonePattern.test(phone.trim())
        ? ""
        : "Please enter a valid mobile number.";
    setNameError(nextNameError);
    setEmailError(nextEmailError);
    setNotificationEmailError(nextNotificationEmailError);
    setPhoneError(nextPhoneError);
    if (nextNameError || nextEmailError || nextNotificationEmailError || nextPhoneError) return;

    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/company/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          ...(email.trim() ? { email: withDomain(email) } : {}),
          notification_email: notificationEmail.trim().toLowerCase(),
          phone_number: phone.trim(),
          role_code: roleCode,
          ...(staffRole
            ? {
                designation: designation.trim() || null,
                department_id: departmentId || null,
                joining_date: joiningDate || null,
              }
            : {}),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to send invitation.");
      setOpen(false);
      setRoleCode("COMPANY_EMPLOYEE");
      setName("");
      setEmail("");
      setNotificationEmail("");
      setPhone("");
      setLoginTouched(false);
      setDesignation("");
      setDepartmentId("");
      setJoiningDate("");
      setNameError("");
      setEmailError("");
      setNotificationEmailError("");
      setPhoneError("");
      const sentTo =
        typeof data.notification_email === "string" && data.notification_email
          ? data.notification_email
          : notificationEmail.trim();
      const loginEmail = typeof data.email === "string" && data.email ? data.email : email.trim();
      setNotice(
        `Setup link sent to ${sentTo}. Their login is ${loginEmail}; they choose their own password from the link.`,
      );
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to send invitation.");
    } finally {
      setSaving(false);
    }
  }

  async function runAction() {
    if (!action) return;
    setSaving(true);
    try {
      const response = await fetch(`/api/company/invitations/${action.item.id}/${action.type}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to update invitation.");
      setNotice(data.message);
      setAction(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update invitation.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight="User Invitations"
        description="Invite employees, managers and clients through secure, tenant-bound account setup links."
        compact
      />
      <div className="dash-content">
        <section className="registration-workspace invite-workspace" aria-live="polite">
          <header className="registration-workspace-header registration-workspace-actions invite-actions">
            <button
              type="button"
              className="registration-primary-action"
              onClick={() => {
                setError("");
                setNameError("");
                setEmailError("");
                setNotificationEmailError("");
                setPhoneError("");
                setOpen(true);
              }}
            >
              <MailPlus /> Invite user
            </button>
          </header>
          {notice && <div className="invite-notice">{notice}</div>}
          {error && <div className="invite-error">{error}</div>}
          {loading ? (
            <div className="invite-state">
              <i className="registration-spinner" /> Loading invitations…
            </div>
          ) : !items.length ? (
            <div className="invite-state">
              <Mail /> No invitations yet
            </div>
          ) : (
            <div className="registration-table invite-table" role="table">
              <div className="registration-table-head invite-head" role="row">
                <span>Email</span>
                <span>Role</span>
                <span>Status</span>
                <span>Actions</span>
              </div>
              {items.map((item) => (
                <article key={item.id} role="row">
                  <div className="registration-row-identity">
                    <strong>{item.email}</strong>
                    <small>
                      {item.notification_email && item.notification_email !== item.email
                        ? `Sent to ${item.notification_email} · `
                        : ""}
                      Expires {new Date(item.expires_at).toLocaleString()}
                    </small>
                  </div>
                  <span>{roleLabel(item.role_code)}</span>
                  <div className="registration-row-meta">
                    <span>{item.status}</span>
                    <div className="registration-row-actions">
                      {item.status !== "ACCEPTED" && item.status !== "REVOKED" && (
                        <button
                          type="button"
                          title="Resend invitation"
                          aria-label={`Resend invitation to ${item.email}`}
                          onClick={() => setAction({ item, type: "resend" })}
                        >
                          <RotateCw />
                        </button>
                      )}
                      {item.status === "PENDING" && (
                        <button
                          type="button"
                          title="Revoke invitation"
                          aria-label={`Revoke invitation for ${item.email}`}
                          onClick={() => setAction({ item, type: "revoke" })}
                        >
                          <X />
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
      <ManagementModal
        open={open}
        eyebrow="Invite user"
        title="Send company invitation"
        subtitle="Set the internal login email first, then choose where the secure activation mail should be delivered."
        icon={<MailPlus />}
        busy={saving}
        onClose={() => setOpen(false)}
        footer={
          <>
            <button type="button" className="management-secondary-action" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" form="invite-user-form" className="management-primary-action" disabled={saving}>
              {saving ? (
                <>
                  <RefreshCw className="spin" /> Sending…
                </>
              ) : (
                "Send invite"
              )}
            </button>
          </>
        }
      >
        {error && <div className="management-form-message">{error}</div>}
        <form id="invite-user-form" onSubmit={invite}>
          <label className="management-field">
            <span>Access role</span>
            <LooplessSelect
              value={roleCode}
              onValueChange={(value) => setRoleCode(value as InvitationRoleCode)}
              ariaLabel="Select invitation role"
              options={roleOptions}
            />
          </label>
          <label className="management-field">
            <span>Full name</span>
            <span className="management-input">
              <UserRound aria-hidden="true" />
              <input
                autoFocus
                type="text"
                autoComplete="name"
                value={name}
                onChange={(event) => {
                  const value = event.target.value;
                  setName(value);
                  if (!loginTouched) {
                    const suggested = suggestLogin(value);
                    setEmail(suggested);
                    setEmailError("");
                  }
                  setNameError(
                    !value.trim()
                      ? "Full name is required."
                      : value.trim().length < 2
                        ? "Enter at least 2 characters."
                        : "",
                  );
                  setError("");
                }}
                aria-invalid={Boolean(nameError)}
                placeholder={`${roleLabel(roleCode)} full name`}
              />
            </span>
            {nameError && <small>{nameError}</small>}
          </label>
          <label className="management-field">
            <span>Internal login email</span>
            <span className="management-input">
              <Mail aria-hidden="true" />
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => {
                  const value = event.target.value;
                  setEmail(value);
                  setLoginTouched(true);
                  setEmailError(value.includes("@") ? loginError(value) : "");
                  setError("");
                }}
                onBlur={() => {
                  const value = withDomain(email);
                  setEmail(value);
                  setEmailError(value ? loginError(value) : "");
                }}
                aria-invalid={Boolean(emailError)}
                placeholder={`firstname.lastname@${INTERNAL_DOMAIN}`}
              />
            </span>
            {emailError ? (
              <small>{emailError}</small>
            ) : (
              <em className="invite-hint">
                {roleCode === "COMPANY_CLIENT"
                  ? "Optional for clients: made from the name if empty. They can also sign in with their Gmail."
                  : "They sign in with this. Work mail arrives in its Adverse mailbox."}
              </em>
            )}
          </label>
          <label className="management-field">
            <span>Their Gmail</span>
            <span className="management-input">
              <Mail aria-hidden="true" />
              <input
                type="email"
                autoComplete="email"
                value={notificationEmail}
                onChange={(event) => {
                  const value = event.target.value;
                  setNotificationEmail(value);
                  setNotificationEmailError(gmailError(value, email));
                  setError("");
                }}
                aria-invalid={Boolean(notificationEmailError)}
                placeholder="person@gmail.com"
              />
            </span>
            {notificationEmailError ? (
              <small>{notificationEmailError}</small>
            ) : (
              <em className="invite-hint">The setup link, password resets and account mail go here.</em>
            )}
          </label>
          <label className="management-field">
            <span>Mobile number</span>
            <span className="management-input">
              <Phone aria-hidden="true" />
              <input
                type="tel"
                autoComplete="tel"
                value={phone}
                onChange={(event) => {
                  const value = event.target.value;
                  setPhone(value);
                  setPhoneError(
                    !value.trim()
                      ? "Mobile number is required."
                      : phonePattern.test(value.trim())
                        ? ""
                        : "Please enter a valid mobile number.",
                  );
                  setError("");
                }}
                aria-invalid={Boolean(phoneError)}
                placeholder="+91 98765 43210"
              />
            </span>
            {phoneError && <small>{phoneError}</small>}
          </label>
          {staffRole && (
            <>
              <label className="management-field">
                <span>Designation</span>
                <span className="management-input">
                  <BriefcaseBusiness aria-hidden="true" />
                  <input
                    type="text"
                    value={designation}
                    maxLength={120}
                    onChange={(event) => setDesignation(event.target.value)}
                    placeholder={roleCode === "COMPANY_MANAGER" ? "Production Manager" : "Video Editor"}
                  />
                </span>
              </label>
              <label className="management-field">
                <span>Department</span>
                <LooplessSelect
                  value={departmentId}
                  onValueChange={setDepartmentId}
                  ariaLabel="Select department"
                  options={[
                    { value: "", label: departments.length ? "No department" : "No departments yet" },
                    ...departments.map((item) => ({ value: item.id, label: item.name })),
                  ]}
                />
              </label>
              <label className="management-field">
                <span>Joining date</span>
                <LooplessDate value={joiningDate} onValueChange={setJoiningDate} ariaLabel="Joining date" />
              </label>
            </>
          )}
        </form>
      </ManagementModal>
      <ConfirmationDialog
        open={Boolean(action)}
        title={`${action?.type === "revoke" ? "Revoke" : "Resend"} invitation?`}
        description={
          action
            ? `${action.item.email}${action.item.notification_email && action.item.notification_email !== action.item.email ? ` · sent to ${action.item.notification_email}` : ""}`
            : ""
        }
        confirmLabel={action?.type === "revoke" ? "Revoke invitation" : "Resend invitation"}
        tone={action?.type === "revoke" ? "danger" : "primary"}
        loading={saving}
        onCancel={() => setAction(null)}
        onConfirm={() => void runAction()}
      />
    </>
  );
}
