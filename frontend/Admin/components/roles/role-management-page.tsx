"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, FileText, Plus, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { PermissionSelector, type PermissionModule } from "@/components/roles/permission-selector";
import type { CurrentUser } from "@/lib/auth/types";
import "@/styles/role-management.css";

type Role = {
  id: string;
  name: string;
  code: string;
  description: string;
  status: "ACTIVE" | "INACTIVE";
  is_system: boolean;
  user_count: number;
  permission_count: number;
  created_at: string;
  updated_at: string;
};
type RoleDetail = Role & { permissions: string[] };
type FormMode = "create" | "view" | "edit";

export function RoleManagementPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [modules, setModules] = useState<PermissionModule[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [openingRoleId, setOpeningRoleId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState<FormMode | null>(null);
  const [activeRole, setActiveRole] = useState<RoleDetail | null>(null);
  const [form, setForm] = useState({ name: "", description: "", permissions: [] as string[] });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState<{ type: "status" | "delete"; role: Role } | null>(null);

  const query = useMemo(
    () => new URLSearchParams({ ...(search ? { search } : {}), ...(status ? { status } : {}) }).toString(),
    [search, status],
  );
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [rolesResponse, permissionsResponse, meResponse] = await Promise.all([
        fetch(`/api/company/roles${query ? `?${query}` : ""}`, { cache: "no-store" }),
        fetch("/api/company/roles/permissions", { cache: "no-store" }),
        fetch("/api/auth/me", { cache: "no-store" }),
      ]);
      const [rolesData, permissionData, meData] = await Promise.all([
        rolesResponse.json(),
        permissionsResponse.json(),
        meResponse.json(),
      ]);
      if (!rolesResponse.ok) throw new Error(rolesData.detail);
      if (!permissionsResponse.ok) throw new Error(permissionData.detail);
      setRoles(rolesData.items);
      setModules(permissionData.modules);
      if (meResponse.ok) setCurrentUser(meData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load roles.");
    } finally {
      setLoading(false);
    }
  }, [query]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  const hasPermission = useCallback(
    (action: string) =>
      Boolean(
        currentUser?.permissions.some((permission) => permission.module === "ROLES" && permission.action === action),
      ),
    [currentUser],
  );
  const canCreate = hasPermission("CREATE");
  const canEdit = hasPermission("EDIT");
  const canDelete = hasPermission("DELETE");

  function createRole() {
    if (!canCreate) return;
    setMode("create");
    setActiveRole(null);
    setForm({ name: "", description: "", permissions: [] });
    setFieldErrors({});
  }
  async function openRole(role: Role, nextMode: FormMode) {
    setOpeningRoleId(role.id);
    setError("");
    try {
      const response = await fetch(`/api/company/roles/${role.id}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail);
      setActiveRole(data);
      setForm({ name: data.name, description: data.description, permissions: data.permissions });
      setMode(nextMode);
      setFieldErrors({});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open role.");
    } finally {
      setOpeningRoleId(null);
    }
  }
  function updateName(value: string) {
    setForm((current) => ({ ...current, name: value }));
    setFieldErrors((current) => ({
      ...current,
      name: !value.trim()
        ? "Role name is required."
        : !/^[A-Za-z][A-Za-z0-9 &()/_-]{1,79}$/.test(value.trim())
          ? "Use 2–80 valid characters and begin with a letter."
          : "",
    }));
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    const name = form.name.trim();
    const errors = {
      name: !name
        ? "Role name is required."
        : !/^[A-Za-z][A-Za-z0-9 &()/_-]{1,79}$/.test(name)
          ? "Use 2–80 valid characters and begin with a letter."
          : "",
    };
    setFieldErrors(errors);
    if (errors.name) return;
    setSaving(true);
    setError("");
    try {
      const editing = mode === "edit" && activeRole;
      const response = await fetch(editing ? `/api/company/roles/${activeRole.id}` : "/api/company/roles", {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: form.description.trim(), permissions: form.permissions }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail);
      setMode(null);
      setActiveRole(null);
      setNotice(`Role ${editing ? "updated" : "created"} successfully.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save role.");
    } finally {
      setSaving(false);
    }
  }
  async function runConfirmedAction() {
    if (!confirm) return;
    setSaving(true);
    setError("");
    try {
      const deleting = confirm.type === "delete";
      const response = await fetch(`/api/company/roles/${confirm.role.id}`, {
        method: deleting ? "DELETE" : "PATCH",
        ...(deleting
          ? {}
          : {
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ status: confirm.role.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" }),
            }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail);
      setNotice(deleting ? "Role deleted successfully." : `Role ${data.status.toLowerCase()} successfully.`);
      setConfirm(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update role.");
      setConfirm(null);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight="Roles"
        description="Create and manage tenant-scoped roles and permissions."
        compact
      />
      <div className="dash-content">
        <section className="role-workspace" aria-live="polite">
          {notice && <div className="role-notice">{notice}</div>}
          {error && (
            <div className="role-error">
              <span>{error}</span>
              <button type="button" onClick={() => void load()}>
                Retry
              </button>
            </div>
          )}
          {mode ? (
            <>
              <header className="management-toolbar">
                <button type="button" className="management-back" onClick={() => setMode(null)}>
                  <ArrowLeft /> Back to roles
                </button>
                <span>{mode === "create" ? "New Role" : mode === "edit" ? "Edit Role" : "Role Details"}</span>
              </header>
              <section className="management-editor role-form-card">
                <header>
                  <i aria-hidden="true">
                    <ShieldCheck />
                  </i>
                  <div>
                    <span>{mode === "create" ? "NEW ROLE" : mode === "edit" ? "EDIT ROLE" : "ROLE DETAILS"}</span>
                    <h2>{mode === "create" ? "Create company role" : activeRole?.name}</h2>
                    <p>
                      {mode === "view"
                        ? "Review this role and its assigned permissions."
                        : "Configure the role details and only the access it requires."}
                    </p>
                  </div>
                </header>
                <form className="management-form role-form-body" noValidate onSubmit={save}>
                  <div className="role-fields">
                    <label className="management-field">
                      <span>Role name</span>
                      <span className="management-input">
                        <ShieldCheck aria-hidden="true" />
                        <input
                          value={form.name}
                          disabled={mode === "view"}
                          onChange={(event) => updateName(event.target.value)}
                          aria-invalid={Boolean(fieldErrors.name)}
                        />
                      </span>
                      {fieldErrors.name && <small>{fieldErrors.name}</small>}
                    </label>
                    <label className="management-field">
                      <span>Description</span>
                      <span className="management-input role-textarea-shell">
                        <FileText aria-hidden="true" />
                        <textarea
                          value={form.description}
                          disabled={mode === "view"}
                          onChange={(event) => setForm({ ...form, description: event.target.value })}
                          maxLength={500}
                        />
                      </span>
                    </label>
                  </div>
                  <PermissionSelector
                    modules={modules}
                    selected={form.permissions}
                    onChange={(permissions) => setForm({ ...form, permissions })}
                    disabled={mode === "view"}
                  />
                  <div className="management-form-footer">
                    <button type="button" className="management-secondary-action" onClick={() => setMode(null)}>
                      {mode === "view" ? "Back to roles" : "Cancel"}
                    </button>
                    {mode !== "view" && (
                      <button type="submit" className="management-primary-action" disabled={saving}>
                        {saving ? (
                          <>
                            <RefreshCw className="spin" /> Saving…
                          </>
                        ) : mode === "edit" ? (
                          "Save changes"
                        ) : (
                          "Create role"
                        )}
                      </button>
                    )}
                  </div>
                </form>
              </section>
            </>
          ) : loading ? (
            <div className="role-state">
              <i /> Loading roles…
            </div>
          ) : roles.length === 0 ? (
            <div className="role-state">
              <ShieldCheck />
              <strong>No roles found</strong>
              {canCreate && (
                <button type="button" onClick={createRole}>
                  Create role
                </button>
              )}
            </div>
          ) : (
            <>
              {canCreate && (
                <header className="management-toolbar">
                  <div>
                    <span>Company access</span>
                    <strong>{roles.length} Roles</strong>
                  </div>
                  <button type="button" onClick={createRole}>
                    <Plus /> Create role
                  </button>
                </header>
              )}
              <div className="role-tools">
                <label>
                  <Search />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search roles"
                  />
                </label>
                <LooplessSelect
                  value={status}
                  onValueChange={setStatus}
                  ariaLabel="Filter roles by status"
                  options={[
                    { value: "", label: "All statuses" },
                    { value: "ACTIVE", label: "Active" },
                    { value: "INACTIVE", label: "Inactive" },
                  ]}
                />
              </div>
              <div className="role-table" role="table">
                <div className="role-table-head" role="row">
                  <span>Role</span>
                  <span>Users</span>
                  <span>Permissions</span>
                  <span>Status</span>
                  <span>Actions</span>
                </div>
                {roles.map((role) => (
                  <article key={role.id} role="row">
                    <div>
                      <strong>{role.name}</strong>
                      <small>
                        {role.description || (role.is_system ? "Protected system role" : "Custom company role")}
                      </small>
                    </div>
                    <span>{role.user_count}</span>
                    <span>{role.permission_count}</span>
                    <em className={role.status.toLowerCase()}>{role.status}</em>
                    <CrudActionButtons
                      view={{
                        label: `View ${role.name}`,
                        onClick: () => void openRole(role, "view"),
                        disabled: openingRoleId === role.id,
                        loading: openingRoleId === role.id,
                      }}
                      edit={
                        !role.is_system && canEdit
                          ? {
                              label: `Edit ${role.name}`,
                              onClick: () => void openRole(role, "edit"),
                              disabled: openingRoleId === role.id,
                              loading: openingRoleId === role.id,
                            }
                          : undefined
                      }
                      toggle={
                        !role.is_system && canEdit
                          ? {
                              label: `${role.status === "ACTIVE" ? "Disable" : "Enable"} ${role.name}`,
                              onClick: () => setConfirm({ type: "status", role }),
                            }
                          : undefined
                      }
                      remove={
                        !role.is_system && canDelete
                          ? { label: `Delete ${role.name}`, onClick: () => setConfirm({ type: "delete", role }) }
                          : undefined
                      }
                      active={role.status === "ACTIVE"}
                    />
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
      <ConfirmationDialog
        open={Boolean(confirm)}
        title={
          confirm?.type === "delete"
            ? "Delete this role?"
            : `${confirm?.role.status === "ACTIVE" ? "Disable" : "Enable"} this role?`
        }
        description={
          confirm?.type === "delete"
            ? "Assigned roles cannot be deleted. This action cannot be undone."
            : "The role status changes immediately for assigned users."
        }
        confirmLabel={
          confirm?.type === "delete"
            ? "Delete role"
            : confirm?.role.status === "ACTIVE"
              ? "Disable role"
              : "Enable role"
        }
        tone={confirm?.type === "delete" || confirm?.role.status === "ACTIVE" ? "danger" : "primary"}
        loading={saving}
        onCancel={() => setConfirm(null)}
        onConfirm={() => void runConfirmedAction()}
      />
    </>
  );
}
