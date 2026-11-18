"use client";

import { useCallback, useEffect, useState } from "react";
import { Mail, MailPlus, Phone, RefreshCw, RotateCw, UserRound, X } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { ManagementModal } from "@/components/foundation/management-modal";
import "@/styles/invitations.css";

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

  async function invite(event: React.FormEvent) {
    event.preventDefault();
    const nextNameError = !name.trim()
      ? "Full name is required."
      : name.trim().length < 2
        ? "Enter at least 2 characters."
        : "";
    const nextEmailError = !email.trim()
      ? "Internal login email is required."
      : /^\S+@\S+\.\S+$/.test(email.trim())
        ? ""
        : "Please enter a valid email address.";
    const nextNotificationEmailError = !notificationEmail.trim()
      ? "Notification email is required."
      : /^\S+@\S+\.\S+$/.test(notificationEmail.trim())
        ? ""
        : "Please enter a valid email address.";
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
          email: email.trim(),
          notification_email: notificationEmail.trim(),
          phone_number: phone.trim(),
          role_code: roleCode,
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
      setNameError("");
      setEmailError("");
      setNotificationEmailError("");
      setPhoneError("");
      const sentTo =
        typeof data.notification_email === "string" && data.notification_email
          ? data.notification_email
          : notificationEmail.trim();
      const loginEmail = typeof data.email === "string" && data.email ? data.email : email.trim();
      setNotice(`Activation email sent to ${sentTo}. Login email: ${loginEmail}.`);
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
                  setEmailError(
                    !value.trim()
                      ? "Internal login email is required."
                      : /^\S+@\S+\.\S+$/.test(value.trim())
                        ? ""
                        : "Please enter a valid email address.",
                  );
                  setError("");
                }}
                aria-invalid={Boolean(emailError)}
                placeholder={`${roleLabel(roleCode).toLowerCase()}@adverseindia.com`}
              />
            </span>
            {emailError && <small>{emailError}</small>}
          </label>
          <label className="management-field">
            <span>Personal / notification email</span>
            <span className="management-input">
              <Mail aria-hidden="true" />
              <input
                type="email"
                autoComplete="email"
                value={notificationEmail}
                onChange={(event) => {
                  const value = event.target.value;
                  setNotificationEmail(value);
                  setNotificationEmailError(
                    !value.trim()
                      ? "Notification email is required."
                      : /^\S+@\S+\.\S+$/.test(value.trim())
                        ? ""
                        : "Please enter a valid email address.",
                  );
                  setError("");
                }}
                aria-invalid={Boolean(notificationEmailError)}
                placeholder="person@gmail.com"
              />
            </span>
            {notificationEmailError && <small>{notificationEmailError}</small>}
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
