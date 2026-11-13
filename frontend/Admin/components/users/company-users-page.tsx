"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, UserRoundCog } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { ManagementModal } from "@/components/foundation/management-modal";
import "@/styles/company-users.css";

type User = {
  id: string;
  name: string;
  email: string;
  status: string;
  role_id: string;
  role_name: string;
  department_id: string | null;
  department_name: string | null;
  branch_id: string | null;
  branch_name: string | null;
};
type Option = { id: string; name: string };
type Options = { roles: Option[]; departments: Option[]; branches: Option[] };

export function CompanyUsersPage() {
  const [users, setUsers] = useState<User[]>([]),
    [options, setOptions] = useState<Options>({ roles: [], departments: [], branches: [] });
  const [loading, setLoading] = useState(true),
    [saving, setSaving] = useState(false),
    [selected, setSelected] = useState<User | null>(null);
  const [dialogMode, setDialogMode] = useState<"view" | "edit">("edit");
  const [form, setForm] = useState({ role_id: "", department_id: "", branch_id: "" }),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [usersResponse, optionsResponse] = await Promise.all([
        fetch("/api/company/users", { cache: "no-store" }),
        fetch("/api/company/users/assignment-options", { cache: "no-store" }),
      ]);
      const [usersData, optionsData] = await Promise.all([usersResponse.json(), optionsResponse.json()]);
      if (!usersResponse.ok) throw new Error(usersData.detail);
      if (!optionsResponse.ok) throw new Error(optionsData.detail);
      setUsers(usersData.items);
      setOptions(optionsData);
    } catch {
      setError("Unable to load company users and assignment options.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  const edit = (user: User) => {
    setDialogMode("edit");
    setSelected(user);
    setForm({ role_id: user.role_id, department_id: user.department_id ?? "", branch_id: user.branch_id ?? "" });
    setError("");
  };
  const view = (user: User) => {
    setDialogMode("view");
    setSelected(user);
    setForm({ role_id: user.role_id, department_id: user.department_id ?? "", branch_id: user.branch_id ?? "" });
    setError("");
  };
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || !form.role_id) return setError("Role is required.");
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/company/users/${selected.id}/organization`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role_id: form.role_id,
          department_id: form.department_id || null,
          branch_id: form.branch_id || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail);
      setMessage("User assignment updated successfully.");
      setSelected(null);
      await load();
    } catch {
      setError("Unable to update user assignment. Please try again.");
    } finally {
      setSaving(false);
    }
  }
  const selectOptions = (items: Option[], unassigned?: string) => [
    ...(unassigned ? [{ value: "", label: unassigned }] : []),
    ...items.map((item) => ({ value: item.id, label: item.name })),
  ];
  return (
    <>
      <DashboardHero
        title=""
        highlight="Company Users"
        description="Review and update tenant-safe role assignments for company users."
        compact
      />
      <div className="dash-content">
        <section className="company-users-workspace" aria-live="polite">
          {message && <div className="company-users-notice">{message}</div>}
          {error && <div className="company-users-error">{error}</div>}
          {loading ? (
            <div className="company-users-state">
              <i /> Loading company users…
            </div>
          ) : users.length === 0 ? (
            <div className="company-users-state">
              <UserRoundCog />
              <strong>No company users found</strong>
            </div>
          ) : (
            <div className="company-users-table" role="table">
              <div className="company-users-head" role="row">
                <span>User</span>
                <span>Role</span>
                <span>Action</span>
              </div>
              {users.map((user) => (
                <article key={user.id} role="row">
                  <div>
                    <strong>{user.name}</strong>
                    <small>{user.email}</small>
                  </div>
                  <span>{user.role_name}</span>
                  <CrudActionButtons
                    view={{ label: `View assignment for ${user.name}`, onClick: () => view(user) }}
                    edit={{ label: `Edit assignment for ${user.name}`, onClick: () => edit(user) }}
                  />
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
      <ManagementModal
        open={Boolean(selected)}
        eyebrow={dialogMode === "edit" ? "Edit assignment" : "Assignment details"}
        title={selected?.name ?? "Company user"}
        subtitle={selected?.email}
        icon={<UserRoundCog />}
        busy={saving}
        onClose={() => setSelected(null)}
        footer={
          <>
            <button type="button" className="management-secondary-action" onClick={() => setSelected(null)}>
              {dialogMode === "view" ? "Close" : "Cancel"}
            </button>
            {dialogMode === "view" ? (
              <button type="button" className="management-primary-action" onClick={() => setDialogMode("edit")}>
                Edit assignment
              </button>
            ) : (
              <button
                type="submit"
                form="company-user-assignment-form"
                className="management-primary-action"
                disabled={saving}
              >
                {saving ? (
                  <>
                    <RefreshCw className="spin" /> Saving…
                  </>
                ) : (
                  "Save assignment"
                )}
              </button>
            )}
          </>
        }
      >
        {selected && (
          <>
            {error && <div className="management-form-message">{error}</div>}
            <form id="company-user-assignment-form" className="company-users-fields" onSubmit={save}>
              <label className="management-field">
                <span>Role</span>
                <LooplessSelect
                  value={form.role_id}
                  options={selectOptions(options.roles)}
                  onValueChange={(value) => setForm({ ...form, role_id: value })}
                  ariaLabel="Role"
                  disabled={dialogMode === "view"}
                />
              </label>
            </form>
          </>
        )}
      </ManagementModal>
    </>
  );
}
