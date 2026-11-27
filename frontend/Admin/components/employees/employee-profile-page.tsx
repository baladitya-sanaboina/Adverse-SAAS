"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Building2, Pencil, RefreshCw, Save, ShieldCheck, UserRound, X } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import type { CurrentUser } from "@/lib/auth/types";
import { PhoneInput } from "@loopless-shared/forms/phone-input";
import "@/styles/profile.css";
import "@/styles/employee-directory.css";

type Employee = {
  id: string;
  user_name: string;
  user_email: string;
  first_name: string | null;
  last_name: string | null;
  phone_number: string | null;
  user_status: string;
  employee_code: string;
  department_id: string | null;
  department_name: string | null;
  branch_id: string | null;
  branch_name: string | null;
  role_id: string;
  role_name: string;
  status: string;
};
type Option = { id: string; name: string };
type Options = { roles: Option[]; departments: Option[]; branches: Option[] };
type Form = {
  first_name: string;
  last_name: string;
  phone_number: string;
  employee_code: string;
  department_id: string;
  branch_id: string;
  role_id: string;
  status: string;
};
type Tab = "personal" | "organization" | "account";

const asOptions = (items: Option[]) => items.map((item) => ({ value: item.id, label: item.name }));
const toForm = (employee: Employee): Form => ({
  first_name: employee.first_name ?? "",
  last_name: employee.last_name ?? "",
  phone_number: employee.phone_number ?? "",
  employee_code: employee.employee_code,
  department_id: employee.department_id ?? "",
  branch_id: employee.branch_id ?? "",
  role_id: employee.role_id,
  status: employee.status,
});

export function EmployeeProfilePage({ employeeId }: { employeeId: string }) {
  const searchParams = useSearchParams();
  const editRequested = searchParams.get("mode") === "edit";
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [options, setOptions] = useState<Options>({ roles: [], departments: [], branches: [] });
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [tab, setTab] = useState<Tab>("personal");
  const [editing, setEditing] = useState(false);
  const [confirmSave, setConfirmSave] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [employeeResponse, optionsResponse, meResponse] = await Promise.all([
        fetch(`/api/company/employees/${employeeId}`, { cache: "no-store" }),
        fetch("/api/company/users/assignment-options", { cache: "no-store" }),
        fetch("/api/auth/me", { cache: "no-store" }),
      ]);
      const [employeeData, optionsData, meData] = await Promise.all([
        employeeResponse.json(),
        optionsResponse.json(),
        meResponse.json(),
      ]);
      if (!employeeResponse.ok) throw new Error("Unable to load this employee profile.");
      if (!optionsResponse.ok) throw new Error("Unable to load organization options.");
      setEmployee(employeeData);
      setOptions(optionsData);
      setForm(toForm(employeeData));
      if (meResponse.ok) {
        setCurrentUser(meData);
        const mayEdit = meData.permissions.some(
          (permission: { module: string; action: string }) =>
            permission.module === "EMPLOYEES" && permission.action === "EDIT",
        );
        if (editRequested && mayEdit) setEditing(true);
      }
    } catch {
      setError("Unable to load this employee profile. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [editRequested, employeeId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const canEdit = currentUser?.permissions.some(
    (permission) => permission.module === "EMPLOYEES" && permission.action === "EDIT",
  );
  const heading = useMemo(
    () =>
      ({
        personal: [
          "Personal information",
          "Employee details",
          "Review the employee's identity and contact information.",
        ],
        organization: [
          "Organization",
          "Company assignment",
          "Manage the employee's role assignment and employee code.",
        ],
        account: ["Account", "Employment status", "Review and update the employee's current status."],
      })[tab],
    [tab],
  );

  function selectTab(nextTab: Tab) {
    if (employee) setForm(toForm(employee));
    setTab(nextTab);
    setEditing(false);
    setError("");
    setMessage("");
  }

  function cancelEdit() {
    if (employee) setForm(toForm(employee));
    setEditing(false);
    setError("");
  }

  function requestSave(event: FormEvent) {
    event.preventDefault();
    if (!form?.employee_code.trim() || !form.role_id) {
      setError("Employee code and role are required.");
      return;
    }
    setConfirmSave(true);
  }

  async function save() {
    if (!form) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`/api/company/employees/${employeeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          department_id: form.department_id || null,
          branch_id: form.branch_id || null,
          first_name: form.first_name || null,
          last_name: form.last_name || null,
          phone_number: form.phone_number || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error("Unable to update this employee.");
      setEmployee(data);
      setForm(toForm(data));
      setEditing(false);
      setMessage("Employee details updated successfully.");
    } catch {
      setError("Unable to update this employee. Review the fields and try again.");
    } finally {
      setSaving(false);
      setConfirmSave(false);
    }
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight="Employee Profile"
        description="Review employee identity, organization, and account information."
        compact
      />
      <div className="dash-content profile-page employee-record-page">
        <div className="employee-profile-navigation">
          <Link href="/employees">
            <ArrowLeft /> Back to employees
          </Link>
        </div>

        {loading ? (
          <div className="employee-profile-loading" aria-label="Loading employee profile">
            <i />
            <i />
            <i />
          </div>
        ) : error && !employee ? (
          <div className="employee-directory-state employee-profile-error">
            <UserRound />
            <strong>Employee profile unavailable</strong>
            <p>{error}</p>
            <div>
              <button type="button" onClick={() => void load()}>
                <RefreshCw /> Retry
              </button>
              <Link href="/employees">Back to employees</Link>
            </div>
          </div>
        ) : employee && form ? (
          <div className="profile-workspace employee-profile-workspace">
            <aside className="profile-section-nav">
              <span>Employee record</span>
              <nav>
                {(
                  [
                    ["personal", UserRound, "Personal details", "Identity and contact information"],
                    ["organization", Building2, "Organization", "Role assignment and employee code"],
                    ["account", ShieldCheck, "Account", "Employment and account status"],
                  ] as const
                ).map(([key, Icon, label, description]) => (
                  <button
                    key={key}
                    type="button"
                    className={tab === key ? "active" : ""}
                    onClick={() => selectTab(key)}
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

              <section className="profile-identity employee-record-identity">
                <div className="profile-avatar employee-record-avatar">
                  <b>{employee.user_name.trim().charAt(0).toUpperCase()}</b>
                </div>
                <div className="profile-meta">
                  <h2>{employee.user_name}</h2>
                  <p>
                    {employee.role_name} · {employee.employee_code}
                  </p>
                  <span>{employee.user_email}</span>
                </div>
                <span className={`employee-status ${employee.status.toLowerCase()}`}>{employee.status}</span>
              </section>

              <section className="profile-card employee-record-card">
                <form onSubmit={requestSave}>
                  <div className="profile-card-heading employee-record-heading">
                    <div>
                      <span>{heading[0]}</span>
                      <h3>{heading[1]}</h3>
                    </div>
                    <div className="employee-record-heading-actions">
                      <p>{heading[2]}</p>
                      {canEdit &&
                        (editing ? (
                          <button type="button" className="employee-record-cancel" onClick={cancelEdit}>
                            <X /> Cancel
                          </button>
                        ) : (
                          <button type="button" onClick={() => setEditing(true)}>
                            <Pencil /> Edit employee
                          </button>
                        ))}
                    </div>
                  </div>

                  {tab === "personal" &&
                    (editing ? (
                      <div className="profile-grid">
                        <label>
                          First name
                          <input
                            value={form.first_name}
                            onChange={(event) => setForm({ ...form, first_name: event.target.value })}
                          />
                        </label>
                        <label>
                          Last name
                          <input
                            value={form.last_name}
                            onChange={(event) => setForm({ ...form, last_name: event.target.value })}
                          />
                        </label>
                        <label>
                          Email
                          <input value={employee.user_email} disabled />
                        </label>
                        <label>
                          Phone number
                          <PhoneInput
                            value={form.phone_number}
                            onChange={(phone_number) => setForm({ ...form, phone_number })}
                          >
                            {(phone) => <input {...phone} placeholder="98765 43210" />}
                          </PhoneInput>
                        </label>
                      </div>
                    ) : (
                      <div className="employee-record-details">
                        <div>
                          <span>First name</span>
                          <b>{employee.first_name || "Not provided"}</b>
                        </div>
                        <div>
                          <span>Last name</span>
                          <b>{employee.last_name || "Not provided"}</b>
                        </div>
                        <div>
                          <span>Email address</span>
                          <b>{employee.user_email}</b>
                        </div>
                        <div>
                          <span>Phone number</span>
                          <b>{employee.phone_number || "Not provided"}</b>
                        </div>
                      </div>
                    ))}

                  {tab === "organization" &&
                    (editing ? (
                      <div className="profile-grid">
                        <label>
                          Employee code
                          <input
                            value={form.employee_code}
                            onChange={(event) => setForm({ ...form, employee_code: event.target.value })}
                          />
                        </label>
                        <label>
                          Role
                          <LooplessSelect
                            value={form.role_id}
                            options={asOptions(options.roles)}
                            onValueChange={(value) => setForm({ ...form, role_id: value })}
                            ariaLabel="Employee role"
                          />
                        </label>
                      </div>
                    ) : (
                      <div className="employee-record-details">
                        <div>
                          <span>Employee code</span>
                          <b>{employee.employee_code}</b>
                        </div>
                        <div>
                          <span>Role</span>
                          <b>{employee.role_name}</b>
                        </div>
                      </div>
                    ))}

                  {tab === "account" &&
                    (editing ? (
                      <div className="profile-grid one">
                        <label>
                          Employee status
                          <LooplessSelect
                            value={form.status}
                            options={[
                              { value: "ACTIVE", label: "Active" },
                              { value: "PENDING", label: "Pending" },
                              { value: "INACTIVE", label: "Inactive" },
                            ]}
                            onValueChange={(value) => setForm({ ...form, status: value })}
                            ariaLabel="Employee status"
                          />
                        </label>
                      </div>
                    ) : (
                      <div className="employee-record-details">
                        <div>
                          <span>Employee status</span>
                          <b>{employee.status}</b>
                        </div>
                        <div>
                          <span>User account status</span>
                          <b>{employee.user_status}</b>
                        </div>
                      </div>
                    ))}

                  {editing && (
                    <button className="profile-save" type="submit" disabled={saving}>
                      <Save /> {saving ? "Saving…" : "Save changes"}
                    </button>
                  )}
                </form>
              </section>
            </main>
          </div>
        ) : null}
      </div>

      <ConfirmationDialog
        open={confirmSave}
        title="Save employee changes?"
        description="The updated employee details and company assignment will be saved immediately."
        confirmLabel="Save changes"
        loading={saving}
        onCancel={() => setConfirmSave(false)}
        onConfirm={() => void save()}
      />
    </>
  );
}
