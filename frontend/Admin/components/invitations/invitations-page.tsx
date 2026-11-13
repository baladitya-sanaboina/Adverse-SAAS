"use client";
import { useCallback, useEffect, useState } from "react";
import { Mail, MailPlus, RefreshCw, RotateCw, X } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { ManagementModal } from "@/components/foundation/management-modal";
import "@/styles/invitations.css";

type Invitation = {
  id: string;
  email: string;
  status: "PENDING" | "ACCEPTED" | "EXPIRED" | "REVOKED";
  expires_at: string;
  created_at: string;
};
export function InvitationsPage() {
  const [items, setItems] = useState<Invitation[]>([]),
    [loading, setLoading] = useState(true),
    [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false),
    [email, setEmail] = useState(""),
    [emailError, setEmailError] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [action, setAction] = useState<{ item: Invitation; type: "resend" | "revoke" } | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch("/api/company/invitations", { cache: "no-store" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail);
      setItems(d.items);
    } catch {
      setError("Unable to load invitations.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  async function invite(e: React.FormEvent) {
    e.preventDefault();
    const validation = !email.trim()
      ? "Email is required."
      : !/^\S+@\S+\.\S+$/.test(email.trim())
        ? "Please enter a valid email address."
        : "";
    setEmailError(validation);
    if (validation) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      const r = await fetch("/api/company/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail);
      setOpen(false);
      setEmail("");
      setEmailError("");
      setNotice("Invitation sent successfully.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to send invitation.");
    } finally {
      setSaving(false);
    }
  }
  async function runAction() {
    if (!action) return;
    setSaving(true);
    try {
      const r = await fetch(`/api/company/invitations/${action.item.id}/${action.type}`, { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail);
      setNotice(d.message);
      setAction(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to update invitation.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <DashboardHero
        title=""
        highlight="User Invitations"
        description="Invite company users through secure, tenant-bound account setup links."
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
                setEmailError("");
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
              <i /> Loading invitations…
            </div>
          ) : items.length === 0 ? (
            <div className="invite-state">
              <MailPlus />
              <strong>No invitations yet</strong>
              <span>Invite your first company user.</span>
            </div>
          ) : (
            <div className="registration-table invite-table" role="table">
              <div className="registration-table-head invite-head" role="row">
                <span>Email</span>
                <span>Status</span>
                <span>Expires</span>
                <span>Actions</span>
              </div>
              {items.map((item) => (
                <article key={item.id} role="row">
                  <strong>{item.email}</strong>
                  <em className={item.status.toLowerCase()}>{item.status}</em>
                  <span>{new Date(item.expires_at).toLocaleDateString()}</span>
                  <div>
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
        subtitle="The secure invitation link is tenant-bound and expires automatically."
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
            <span>Email address</span>
            <span className="management-input">
              <Mail aria-hidden="true" />
              <input
                autoFocus
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  const value = e.target.value;
                  setEmail(value);
                  setEmailError(
                    !value.trim()
                      ? "Email is required."
                      : /^\S+@\S+\.\S+$/.test(value.trim())
                        ? ""
                        : "Please enter a valid email address.",
                  );
                  setError("");
                }}
                aria-invalid={Boolean(emailError)}
                placeholder="employee@company.com"
              />
            </span>
            {emailError && <small>{emailError}</small>}
          </label>
        </form>
      </ManagementModal>
      <ConfirmationDialog
        open={Boolean(action)}
        title={`${action?.type === "revoke" ? "Revoke" : "Resend"} invitation?`}
        description={action?.item.email ?? ""}
        confirmLabel={action?.type === "revoke" ? "Revoke invitation" : "Resend invitation"}
        tone={action?.type === "revoke" ? "danger" : "primary"}
        loading={saving}
        onCancel={() => setAction(null)}
        onConfirm={() => void runAction()}
      />
    </>
  );
}
