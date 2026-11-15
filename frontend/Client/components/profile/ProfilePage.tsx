"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { Camera, Eye, EyeOff, LockKeyhole, Save, Settings, UserRound } from "lucide-react";
import Image from "next/image";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";

type Tab = "profile" | "settings" | "password";
type PasswordField = "current_password" | "new_password" | "confirm_password";
type Profile = {
  user: { name: string; email: string };
  role: { name: string };
  company: { name: string } | null;
  first_name: string | null;
  last_name: string | null;
  phone_number: string | null;
  profile_image_url: string | null;
  settings: { timezone: string; language: string; theme_preference: string; email_notifications: boolean };
};
const passwordError = (value: string) =>
  value.length >= 12 && /[a-z]/.test(value) && /[A-Z]/.test(value) && /\d/.test(value) && /[^A-Za-z0-9]/.test(value)
    ? ""
    : "Use 12+ characters with uppercase, lowercase, number and symbol.";

export function ProfilePage({ initialTab = "profile" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone_number: "",
    timezone: "UTC",
    language: "en",
    theme_preference: "system",
    email_notifications: true,
  });
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [visiblePasswords, setVisiblePasswords] = useState<Record<PasswordField, boolean>>({
    current_password: false,
    new_password: false,
    confirm_password: false,
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmAction, setConfirmAction] = useState<"profile" | "password" | null>(null);

  useEffect(() => {
    void load();
  }, []);
  async function load() {
    setLoading(true);
    try {
      const response = await fetch("/api/profile", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to load profile.");
      setProfile(data);
      setForm({
        first_name: data.first_name ?? "",
        last_name: data.last_name ?? "",
        phone_number: data.phone_number ?? "",
        ...data.settings,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load profile.");
    } finally {
      setLoading(false);
    }
  }
  async function save(event?: FormEvent) {
    if (event) {
      event.preventDefault();
      setConfirmAction("profile");
      return;
    }
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const response = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          first_name: form.first_name || null,
          last_name: form.last_name || null,
          phone_number: form.phone_number || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Profile update failed.");
      setProfile(data);
      setMessage("Profile updated successfully.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Profile update failed.");
    } finally {
      setLoading(false);
      setConfirmAction(null);
    }
  }
  async function changePassword(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    setMessage("");
    const validation = passwordError(passwords.new_password);
    if (validation) return setError(validation);
    if (passwords.new_password !== passwords.confirm_password) return setError("Passwords do not match.");
    if (event) {
      setConfirmAction("password");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch("/api/profile/change-password", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(passwords),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Password change failed.");
      setMessage(data.message);
      setTimeout(() => {
        // A full page load (not client navigation): the old session is gone after a password change.
        window.location.href = new URL("/login", window.location.origin).href;
      }, 900);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Password change failed.");
    } finally {
      setLoading(false);
      setConfirmAction(null);
    }
  }
  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const image = event.target.files?.[0];
    if (!image) return;
    setError("");
    if (!["image/jpeg", "image/png", "image/webp"].includes(image.type) || image.size > 5 * 1024 * 1024)
      return setError("Use a JPG, PNG or WEBP image up to 5 MB.");
    const body = new FormData();
    body.append("image", image);
    setLoading(true);
    try {
      const response = await fetch("/api/profile/image", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Image upload failed.");
      window.dispatchEvent(new CustomEvent("loopless-profile-image-updated", { detail: data.profile_image_url }));
      await load();
      setMessage(data.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Image upload failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight="My Profile"
        description="Manage your personal information, preferences, and account security."
        compact
      />
      <div className="dash-content profile-page">
        <div className="profile-workspace">
          <aside className="profile-section-nav">
            <span>Account settings</span>
            <nav>
              {(
                [
                  ["profile", UserRound, "Personal details", "Name and contact information"],
                  ["settings", Settings, "Preferences", "Language, timezone and theme"],
                  ["password", LockKeyhole, "Security", "Password and account access"],
                ] as const
              ).map(([key, Icon, label, description]) => (
                <button
                  key={key}
                  className={tab === key ? "active" : ""}
                  onClick={() => {
                    setTab(key);
                    setError("");
                    setMessage("");
                  }}
                >
                  <Icon />
                  <span>
                    <b>{label}</b>
                    <small>{description}</small>
                  </span>
                </button>
              ))}
            </nav>
          </aside>

          <main className="profile-main">
            {error && <div className="profile-alert error">{error}</div>}
            {message && <div className="profile-alert success">{message}</div>}
            {loading && !profile ? (
              <div className="profile-loading">Loading profile…</div>
            ) : (
              profile && (
                <>
                  <section className="profile-identity">
                    <div className="profile-avatar">
                      {profile.profile_image_url ? (
                        <Image
                          unoptimized
                          width={96}
                          height={96}
                          src={`/api/profile/image?path=${encodeURIComponent(profile.profile_image_url)}`}
                          alt="Profile"
                        />
                      ) : (
                        <b>{profile.user.name.slice(0, 2).toUpperCase()}</b>
                      )}
                      <label title="Upload profile image">
                        <Camera />
                        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={upload} />
                      </label>
                    </div>
                    <div className="profile-meta">
                      <h2>{profile.user.name}</h2>
                      <p>
                        {profile.role.name}
                        {profile.company ? ` · ${profile.company.name}` : ""}
                      </p>
                      <span>{profile.user.email}</span>
                    </div>
                  </section>

                  <section className="profile-card">
                    {tab === "profile" && (
                      <form onSubmit={save}>
                        <div className="profile-card-heading">
                          <div>
                            <span>General</span>
                            <h3>Contact details</h3>
                          </div>
                          <p>Update your personal information and contact number.</p>
                        </div>
                        <div className="profile-grid">
                          <label>
                            First name
                            <input
                              value={form.first_name}
                              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                            />
                          </label>
                          <label>
                            Last name
                            <input
                              value={form.last_name}
                              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                            />
                          </label>
                          <label>
                            Email
                            <input value={profile.user.email} disabled />
                          </label>
                          <label>
                            Phone number
                            <input
                              value={form.phone_number}
                              onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                              placeholder="+91 98765 43210"
                            />
                          </label>
                        </div>
                        <button className="profile-save" disabled={loading}>
                          <Save />
                          {loading ? "Saving…" : "Save changes"}
                        </button>
                      </form>
                    )}
                    {tab === "settings" && (
                      <form onSubmit={save}>
                        <div className="profile-card-heading">
                          <div>
                            <span>Preferences</span>
                            <h3>Account preferences</h3>
                          </div>
                          <p>Choose how Adverse appears and communicates with you.</p>
                        </div>
                        <div className="profile-settings-list">
                          <label className="profile-setting-row">
                            <span>
                              <b>Timezone</b>
                              <small>Used for dates, activity and reports.</small>
                            </span>
                            <LooplessSelect
                              value={form.timezone}
                              onValueChange={(value) => setForm({ ...form, timezone: value })}
                              ariaLabel="Timezone"
                              options={["UTC", "Asia/Kolkata", "America/New_York", "Europe/London"].map((value) => ({
                                value,
                                label: value,
                              }))}
                            />
                          </label>
                          <label className="profile-setting-row">
                            <span>
                              <b>Language</b>
                              <small>Choose your preferred display language.</small>
                            </span>
                            <LooplessSelect
                              value={form.language}
                              onValueChange={(value) => setForm({ ...form, language: value })}
                              ariaLabel="Language"
                              options={[
                                { value: "en", label: "English" },
                                { value: "te", label: "Telugu" },
                                { value: "hi", label: "Hindi" },
                              ]}
                            />
                          </label>
                          <label className="profile-setting-row">
                            <span>
                              <b>Appearance</b>
                              <small>Control how Adverse looks on this account.</small>
                            </span>
                            <LooplessSelect
                              value={form.theme_preference}
                              onValueChange={(value) => setForm({ ...form, theme_preference: value })}
                              ariaLabel="Appearance"
                              options={[
                                { value: "system", label: "System" },
                                { value: "light", label: "Light" },
                                { value: "dark", label: "Dark" },
                              ]}
                            />
                          </label>
                          <label className="profile-setting-row profile-notification-row">
                            <span>
                              <b>Email notifications</b>
                              <small>Receive important account and activity updates.</small>
                            </span>
                            <input
                              type="checkbox"
                              checked={form.email_notifications}
                              onChange={(e) => setForm({ ...form, email_notifications: e.target.checked })}
                            />
                          </label>
                        </div>
                        <button className="profile-save" disabled={loading}>
                          <Save />
                          {loading ? "Saving…" : "Save settings"}
                        </button>
                      </form>
                    )}
                    {tab === "password" && (
                      <form onSubmit={changePassword}>
                        <div className="profile-card-heading">
                          <div>
                            <span>Security</span>
                            <h3>Change password</h3>
                          </div>
                          <p>Use a strong password that you do not use elsewhere.</p>
                        </div>
                        <div className="profile-grid one">
                          <label>
                            Current password
                            <span className="profile-password-input">
                              <input
                                type={visiblePasswords.current_password ? "text" : "password"}
                                value={passwords.current_password}
                                onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })}
                              />
                              <button
                                type="button"
                                aria-label={
                                  visiblePasswords.current_password ? "Hide current password" : "Show current password"
                                }
                                onClick={() =>
                                  setVisiblePasswords((current) => ({
                                    ...current,
                                    current_password: !current.current_password,
                                  }))
                                }
                              >
                                {visiblePasswords.current_password ? <EyeOff /> : <Eye />}
                              </button>
                            </span>
                          </label>
                          <label>
                            New password
                            <span className="profile-password-input">
                              <input
                                type={visiblePasswords.new_password ? "text" : "password"}
                                value={passwords.new_password}
                                onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })}
                              />
                              <button
                                type="button"
                                aria-label={visiblePasswords.new_password ? "Hide new password" : "Show new password"}
                                onClick={() =>
                                  setVisiblePasswords((current) => ({
                                    ...current,
                                    new_password: !current.new_password,
                                  }))
                                }
                              >
                                {visiblePasswords.new_password ? <EyeOff /> : <Eye />}
                              </button>
                            </span>
                            <span
                              className={`profile-strength ${passwordError(passwords.new_password) ? "weak" : "strong"}`}
                            >
                              {passwords.new_password
                                ? passwordError(passwords.new_password) || "Strong password"
                                : "Enter a strong password"}
                            </span>
                          </label>
                          <label>
                            Confirm password
                            <span className="profile-password-input">
                              <input
                                type={visiblePasswords.confirm_password ? "text" : "password"}
                                value={passwords.confirm_password}
                                onChange={(e) => setPasswords({ ...passwords, confirm_password: e.target.value })}
                              />
                              <button
                                type="button"
                                aria-label={
                                  visiblePasswords.confirm_password ? "Hide confirm password" : "Show confirm password"
                                }
                                onClick={() =>
                                  setVisiblePasswords((current) => ({
                                    ...current,
                                    confirm_password: !current.confirm_password,
                                  }))
                                }
                              >
                                {visiblePasswords.confirm_password ? <EyeOff /> : <Eye />}
                              </button>
                            </span>
                          </label>
                        </div>
                        <button className="profile-save" disabled={loading}>
                          <LockKeyhole />
                          {loading ? "Changing…" : "Change password"}
                        </button>
                      </form>
                    )}
                  </section>
                </>
              )
            )}
          </main>
        </div>
      </div>
      <ConfirmationDialog
        open={Boolean(confirmAction)}
        title={confirmAction === "password" ? "Change your password?" : "Save account changes?"}
        description={
          confirmAction === "password"
            ? "Your current sessions will be revoked and you will need to sign in again."
            : tab === "settings"
              ? "Your language, timezone, appearance, and notification preferences will be updated."
              : "Your personal and contact information will be updated."
        }
        confirmLabel={confirmAction === "password" ? "Change password" : "Save changes"}
        tone={confirmAction === "password" ? "danger" : "primary"}
        loading={loading}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction === "password") void changePassword();
          else void save();
        }}
      />
    </>
  );
}
