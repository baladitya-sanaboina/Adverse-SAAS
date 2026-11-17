"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Eye, Pencil, Plus, Power, RefreshCw, RotateCcw, Search, Trash2, UserRound } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import type { CurrentUser } from "@/lib/auth/types";
import "@/styles/employee-directory.css";

type Employee = {
  id: string;
  user_name: string;
  user_email: string;
  user_status: string;
  employee_code: string;
  department_name: string | null;
  branch_name: string | null;
  role_name: string;
  status: string;
};
type DirectoryResponse = { items: Employee[]; page: number; page_size: number; total: number; total_pages: number };
type Option = { id: string; name: string };
type Options = { roles: Option[]; departments: Option[]; branches: Option[] };

const initialOptions: Options = { roles: [], departments: [], branches: [] };
const selectOptions = (label: string, options: Option[]) => [
  { value: "", label },
  ...options.map((item) => ({ value: item.id, label: item.name })),
];

export function EmployeeDirectoryPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [data, setData] = useState<DirectoryResponse | null>(null);
  const [options, setOptions] = useState(initialOptions);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [statusEmployee, setStatusEmployee] = useState<Employee | null>(null);
  const [deleteEmployee, setDeleteEmployee] = useState<Employee | null>(null);

  const query = useMemo(
    () => ({
      search: searchParams.get("search") ?? "",
      role: searchParams.get("role") ?? "",
      status: searchParams.get("status") ?? "",
      page: Math.max(1, Number(searchParams.get("page") ?? 1) || 1),
    }),
    [searchParams],
  );

  const setQuery = useCallback(
    (updates: Record<string, string | number>) => {
      const next = new URLSearchParams(searchParams.toString());
      Object.entries(updates).forEach(([key, value]) => {
        if (value === "" || value === 1) next.delete(key);
        else next.set(key, String(value));
      });
      router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (search !== query.search) setQuery({ search: search.trim(), page: 1 });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [query.search, search, setQuery]);

  useEffect(() => {
    const invite = searchParams.get("invite");
    const email = searchParams.get("email");
    const login = searchParams.get("login");
    if (invite !== "sent" || !email) return;
    setNotice(login ? `Activation email sent to ${email}. Login email: ${login}.` : `Activation email sent to ${email}.`);
    const next = new URLSearchParams(searchParams.toString());
    next.delete("invite");
    next.delete("email");
    next.delete("login");
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }, [pathname, router, searchParams]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ page: String(query.page), page_size: "20" });
    if (query.search) params.set("search", query.search);
    if (query.role) params.set("role_id", query.role);
    if (query.status) params.set("status", query.status);
    try {
      const [employeesResponse, optionsResponse, meResponse] = await Promise.all([
        fetch(`/api/company/employees?${params}`, { cache: "no-store" }),
        fetch("/api/company/users/assignment-options", { cache: "no-store" }),
        fetch("/api/auth/me", { cache: "no-store" }),
      ]);
      const [employeesData, optionsData, meData] = await Promise.all([
        employeesResponse.json(),
        optionsResponse.json(),
        meResponse.json(),
      ]);
      if (!employeesResponse.ok) throw new Error("Unable to load employees.");
      if (!optionsResponse.ok) throw new Error("Unable to load employee filters.");
      setData(employeesData);
      setOptions(optionsData);
      if (meResponse.ok) setCurrentUser(meData);
    } catch {
      setError("Unable to load employees. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const canCreate = currentUser?.permissions.some(
    (permission) => permission.module === "EMPLOYEES" && permission.action === "CREATE",
  );
  const canEdit = currentUser?.permissions.some(
    (permission) => permission.module === "EMPLOYEES" && permission.action === "EDIT",
  );
  const canDelete = currentUser?.permissions.some(
    (permission) => permission.module === "EMPLOYEES" && permission.action === "DELETE",
  );
  const hasActiveFilters = Boolean(query.search || query.role || query.status);
  const start = data && data.total ? (data.page - 1) * data.page_size + 1 : 0;
  const end = data ? Math.min(data.page * data.page_size, data.total) : 0;
  const pageNumbers = useMemo(() => {
    const totalPages = data?.total_pages ?? 0;
    if (!totalPages) return [];
    const visiblePages = Math.min(5, totalPages);
    const firstPage = Math.min(Math.max(1, query.page - 2), Math.max(1, totalPages - visiblePages + 1));
    return Array.from({ length: visiblePages }, (_, index) => firstPage + index);
  }, [data?.total_pages, query.page]);

  function clearFilters() {
    setSearch("");
    setNotice("");
    router.replace(pathname, { scroll: false });
  }

  async function updateEmployeeStatus() {
    if (!statusEmployee) return;
    setUpdating(true);
    setError("");
    setNotice("");
    const nextStatus = statusEmployee.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    try {
      const response = await fetch(`/api/company/employees/${statusEmployee.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      const responseData = await response.json();
      if (!response.ok) throw new Error(responseData.detail ?? "Unable to update employee status.");
      setNotice(`${statusEmployee.user_name} is now ${nextStatus.toLowerCase()}.`);
      setStatusEmployee(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update employee status.");
      setStatusEmployee(null);
    } finally {
      setUpdating(false);
    }
  }

  async function removeEmployee() {
    if (!deleteEmployee) return;
    setUpdating(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/company/employees/${deleteEmployee.id}`, { method: "DELETE" });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(typeof data?.detail === "string" ? data.detail : "Unable to delete employee.");
      }
      setNotice(`${deleteEmployee.user_name} deleted successfully.`);
      setDeleteEmployee(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete employee.");
      setDeleteEmployee(null);
    } finally {
      setUpdating(false);
    }
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight="Employees"
        description="Search and manage your company employee and manager directory."
        compact
      />
      <div className="dash-content employee-directory-page">
        <section className="employee-directory-shell" aria-live="polite">
          {canCreate && (
            <header className="employee-directory-actions">
              <Link href="/employees/new" className="employee-primary-action">
                <Plus /> Add employee / manager
              </Link>
            </header>
          )}
          <div className="employee-directory-tools">
            <label>
              <Search />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search name, code or email"
                aria-label="Search employees"
              />
            </label>
            <LooplessSelect
              value={query.role}
              options={selectOptions("All roles", options.roles)}
              onValueChange={(value) => setQuery({ role: value, page: 1 })}
              ariaLabel="Role filter"
            />
            <LooplessSelect
              value={query.status}
              options={[
                { value: "", label: "All statuses" },
                { value: "ACTIVE", label: "Active" },
                { value: "PENDING", label: "Pending" },
                { value: "INACTIVE", label: "Inactive" },
              ]}
              onValueChange={(value) => setQuery({ status: value, page: 1 })}
              ariaLabel="Status filter"
            />
            <button
              type="button"
              className="employee-directory-reset"
              disabled={!hasActiveFilters}
              onClick={clearFilters}
            >
              <RotateCcw /> Reset
            </button>
          </div>
          {notice && <div className="employee-directory-notice">{notice}</div>}
          {loading ? (
            <div className="employee-directory-loading" aria-label="Loading employees">
              {[0, 1, 2, 3].map((item) => (
                <i key={item} />
              ))}
            </div>
          ) : error ? (
            <div className="employee-directory-state">
              <UserRound />
              <strong>Unable to load employees</strong>
              <p>{error}</p>
              <button type="button" onClick={() => void load()}>
                <RefreshCw /> Retry
              </button>
            </div>
          ) : !data?.items.length ? (
            <div className="employee-directory-state">
              <UserRound />
              <strong>No employees found</strong>
              <p>
                {query.search || query.role || query.status
                  ? "Try changing the search or filters."
                  : "Add your first employee to start building the directory."}
              </p>
              {canCreate && (
                <Link href="/employees/new">
                  <Plus /> Add employee
                </Link>
              )}
            </div>
          ) : (
            <div className="employee-directory-table" role="table">
              <div className="employee-directory-head" role="row">
                <span>Employee</span>
                <span>Code</span>
                <span>Role</span>
                <span>Status</span>
                <span>Action</span>
              </div>
              {data.items.map((employee) => (
                <article key={employee.id} role="row">
                  <div className="employee-directory-identity">
                    <b>{employee.user_name.slice(0, 1).toUpperCase()}</b>
                    <span>
                      <strong>{employee.user_name}</strong>
                      <small>{employee.user_email}</small>
                    </span>
                  </div>
                  <span data-label="Code">{employee.employee_code}</span>
                  <span data-label="Role">{employee.role_name}</span>
                  <span data-label="Status" className={`employee-status ${employee.status.toLowerCase()}`}>
                    {employee.status}
                  </span>
                  <div className="employee-directory-row-actions">
                    <Link
                      href={`/employees/${employee.id}`}
                      aria-label={`View ${employee.user_name}`}
                      title="View employee"
                    >
                      <Eye />
                    </Link>
                    {canEdit && (
                      <Link
                        href={`/employees/${employee.id}?mode=edit`}
                        aria-label={`Edit ${employee.user_name}`}
                        title="Edit employee"
                      >
                        <Pencil />
                      </Link>
                    )}
                    {canEdit && (
                      <button
                        type="button"
                        className={employee.status === "ACTIVE" ? "danger" : "success"}
                        aria-label={`${employee.status === "ACTIVE" ? "Disable" : "Enable"} ${employee.user_name}`}
                        title={employee.status === "ACTIVE" ? "Disable employee" : "Enable employee"}
                        onClick={() => setStatusEmployee(employee)}
                      >
                        <Power />
                      </button>
                    )}
                    {canDelete && (employee.user_status === "PENDING_VERIFICATION" || employee.status === "PENDING") && (
                      <button
                        type="button"
                        className="danger"
                        aria-label={`Delete ${employee.user_name}`}
                        title="Delete pending employee"
                        onClick={() => setDeleteEmployee(employee)}
                      >
                        <Trash2 />
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
          {!loading && !error && data && data.total > 0 && (
            <footer>
              <span>
                Showing {start}–{end} of {data.total}
              </span>
              <div>
                <button type="button" disabled={data.page <= 1} onClick={() => setQuery({ page: data.page - 1 })}>
                  <ArrowLeft /> Previous
                </button>
                <nav className="employee-directory-pages" aria-label="Employee directory pages">
                  {pageNumbers.map((pageNumber) => (
                    <button
                      type="button"
                      key={pageNumber}
                      className={pageNumber === data.page ? "active" : ""}
                      aria-current={pageNumber === data.page ? "page" : undefined}
                      onClick={() => setQuery({ page: pageNumber })}
                    >
                      {pageNumber}
                    </button>
                  ))}
                </nav>
                <button
                  type="button"
                  disabled={data.page >= data.total_pages}
                  onClick={() => setQuery({ page: data.page + 1 })}
                >
                  Next <ArrowRight />
                </button>
              </div>
            </footer>
          )}
        </section>
      </div>
      <ConfirmationDialog
        open={Boolean(statusEmployee)}
        title={`${statusEmployee?.status === "ACTIVE" ? "Disable" : "Enable"} this employee?`}
        description={
          statusEmployee?.status === "ACTIVE"
            ? "The employee record will be marked inactive. You can enable it again at any time."
            : "The employee record will return to active status with its current company assignments."
        }
        confirmLabel={statusEmployee?.status === "ACTIVE" ? "Disable employee" : "Enable employee"}
        tone={statusEmployee?.status === "ACTIVE" ? "danger" : "primary"}
        loading={updating}
        onCancel={() => setStatusEmployee(null)}
        onConfirm={() => void updateEmployeeStatus()}
      />
      <ConfirmationDialog
        open={Boolean(deleteEmployee)}
        title="Delete this pending employee?"
        description="This removes the pending employee profile, invitation and login before the invite is accepted."
        confirmLabel="Delete employee"
        tone="danger"
        loading={updating}
        onCancel={() => setDeleteEmployee(null)}
        onConfirm={() => void removeEmployee()}
      />
    </>
  );
}
