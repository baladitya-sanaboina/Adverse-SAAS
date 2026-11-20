"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ClipboardList,
  Download,
  FileText,
  History,
  MessageSquare,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Upload,
  UserCheck,
  Wallet,
} from "lucide-react";
import {
  QuickFilters,
  SheetHeader,
  StatusProgress,
  TaskCard,
  TaskSheet,
  TasksHeader,
  matchesQuick,
  taskSummary,
  type QuickFilter,
  type TaskView,
} from "@loopless-shared/production/task-board-ui";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect, type LooplessSelectOption } from "@/components/foundation/loopless-select";
import { Field, Panel } from "@/components/production/production-ui";
import {
  PRIORITY_LABELS,
  PRIORITY_OPTIONS,
  STATUS_FILTER_OPTIONS,
  STATUS_LABELS,
  api,
  errorText,
  fileSize,
  formatDate,
  formatDateTime,
  money,
  query,
  statusTone,
} from "@/lib/production/client";
import type {
  AdminTask,
  AdminTaskDetail,
  AssigneeOption,
  BudgetCheck,
  Paged,
  PricingPreview,
  TaskPriority,
  TaskStatus,
  TaskWrite,
} from "@/lib/production/types";
import { useLiveRefresh } from "@loopless-shared/realtime/realtime";
import "@/styles/organization.css";
import "@/styles/service-pricing-settings.css";
import "@/styles/production.css";
import { LooplessDate } from "@/components/foundation/loopless-date";

type ChoiceItem = { id: string; name: string; code?: string; status?: string };
/** What the slide-in panel shows; null when it is closed and only the board is visible. */
/** Values passed in from a content calendar entry ("Create task", Phase 13). */
type Prefill = { client_id: string; title: string; description: string; due_date: string; calendar_entry_id: string };
type Sheet =
  | { mode: "create"; prefill?: Prefill }
  | { mode: "edit"; task: AdminTaskDetail }
  | { mode: "detail"; id: string }
  | null;

const BILLING_STATUSES: TaskStatus[] = ["APPROVED", "COMPLETED", "CANCELLED"];
const CLOSED_STATUSES: TaskStatus[] = ["APPROVED", "COMPLETED", "CANCELLED"];
const VIEW_STORAGE_KEY = "adverse-task-view";
const TASK_ID = /^[0-9a-f-]{36}$/i;

function BudgetBanner({ budget }: { budget: BudgetCheck | null }) {
  if (!budget) return null;
  return (
    <div className={budget.exceeds_with_new_task ? "organization-form-error" : "production-info"} role="status">
      {budget.message}
      {budget.has_budget && (
        <>
          {" "}
          Budget {money(budget.total, budget.currency)} · used {money(budget.used, budget.currency)} · in progress{" "}
          {money(budget.committed, budget.currency)}.
        </>
      )}
    </div>
  );
}

function peopleOptions(people: AssigneeOption[], empty: string, filter?: (person: AssigneeOption) => boolean) {
  return [
    { value: "", label: empty },
    ...people
      .filter((person) => (filter ? filter(person) : true))
      .map((person) => ({
        value: person.id,
        label: `${person.name} · ${person.role === "MANAGER" ? "Manager" : "Employee"}`,
      })),
  ];
}

/** Keep ?task=<id> / ?mode=create in the address bar so an open task can be shared or reloaded. */
function syncUrl(sheet: Sheet) {
  const url = new URL(window.location.href);
  for (const key of ["task", "mode", "title", "description", "due", "calendar"]) url.searchParams.delete(key);
  if (sheet?.mode === "detail") url.searchParams.set("task", sheet.id);
  else if (sheet?.mode === "create") url.searchParams.set("mode", "create");
  window.history.replaceState(null, "", `${url.pathname}${url.search}`);
}

const quickTask = (task: AdminTask) => ({ ...task, unassigned: !task.assignee });

export function TaskManagementPage() {
  const [sheet, setSheet] = useState<Sheet>(null);
  const [notice, setNotice] = useState("");
  const [clients, setClients] = useState<ChoiceItem[]>([]);
  const [services, setServices] = useState<ChoiceItem[]>([]);
  const [people, setPeople] = useState<AssigneeOption[]>([]);
  const [view, setView] = useState<TaskView>("board");
  const [items, setItems] = useState<AdminTask[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [client, setClient] = useState("");
  const [quick, setQuick] = useState<QuickFilter>("all");

  useEffect(() => {
    // Links from the dashboard and client page: ?mode=create, ?task=<id> (open it), ?status=<STATUS> or ?client=<id> (filter).
    const fromUrl = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const taskId = params.get("task");
      const statusFilter = params.get("status");
      const calendar = params.get("calendar");
      if (params.get("mode") === "create")
        setSheet({
          mode: "create",
          prefill:
            calendar && TASK_ID.test(calendar)
              ? {
                  client_id: params.get("client") ?? "",
                  title: (params.get("title") ?? "").slice(0, 200),
                  description: (params.get("description") ?? "").slice(0, 5000),
                  due_date: /^\d{4}-\d{2}-\d{2}$/.test(params.get("due") ?? "") ? (params.get("due") ?? "") : "",
                  calendar_entry_id: calendar,
                }
              : undefined,
        });
      else if (taskId && TASK_ID.test(taskId)) setSheet({ mode: "detail", id: taskId });
      if (statusFilter && statusFilter in STATUS_LABELS) setStatus(statusFilter);
      // ?client=<id>: from the client details page, show only that client's tasks.
      const clientFilter = params.get("client");
      if (clientFilter && TASK_ID.test(clientFilter)) setClient(clientFilter);
      try {
        const saved = window.localStorage.getItem(VIEW_STORAGE_KEY);
        if (saved === "board" || saved === "list") setView(saved);
      } catch {
        // Storage can be unavailable (private mode); the board stays the default.
      }
    }, 0);
    void (async () => {
      try {
        const [clientData, serviceData, peopleData] = await Promise.all([
          api<Paged<ChoiceItem> | ChoiceItem[]>("/api/company/clients?page_size=100"),
          api<Paged<ChoiceItem>>("/api/company/services?page_size=100"),
          api<AssigneeOption[]>("/api/company/tasks/assignee-options"),
        ]);
        setClients(Array.isArray(clientData) ? clientData : clientData.items);
        setServices(serviceData.items);
        setPeople(peopleData);
      } catch {
        // The board still works without these; the form shows its own error when they are missing.
      }
    })();
    return () => window.clearTimeout(fromUrl);
  }, []);

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      setError("");
      try {
        const data = await api<Paged<AdminTask>>(
          `/api/company/tasks${query({ search, status, client_id: client, page_size: 500 })}`,
        );
        setItems(data.items);
        setTotal(data.total);
      } catch (requestError) {
        setError(errorText(requestError, "Unable to load tasks."));
      } finally {
        setLoading(false);
      }
    },
    [search, status, client],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  // Submissions and status changes by the team show up live, without a page reload.
  useLiveRefresh(["task."], () => void load(true));

  const chooseView = (next: TaskView) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, next);
    } catch {
      // Ignore: the choice just will not be remembered.
    }
  };

  const openSheet = (next: Sheet, message = "") => {
    setNotice(message);
    setSheet(next);
    syncUrl(next);
  };
  const closeSheet = useCallback(() => {
    setSheet(null);
    syncUrl(null);
  }, []);
  const refresh = useCallback(() => void load(), [load]);

  const clientOptions: LooplessSelectOption[] = useMemo(
    () => [{ value: "", label: "All clients" }, ...clients.map((item) => ({ value: item.id, label: item.name }))],
    [clients],
  );
  const chips = useMemo(
    () =>
      (
        [
          ["all", "All"],
          ["overdue", "Overdue"],
          ["week", "Due this week"],
          ["review", "To review"],
          ["unassigned", "Unassigned"],
        ] as const
      ).map(([key, label]) => ({
        key,
        label,
        count: items.filter((task) => matchesQuick(quickTask(task), key)).length,
      })),
    [items],
  );
  const visible = useMemo(() => items.filter((task) => matchesQuick(quickTask(task), quick)), [items, quick]);
  const filtered = Boolean(search || status || client || quick !== "all");
  const summary =
    loading && items.length === 0
      ? "Loading tasks…"
      : `${taskSummary(items)}${total > items.length ? ` · showing ${items.length} of ${total}` : ""}`;

  return (
    <div className="dash-content production-tasks-content">
      <section className="organization-workspace production-workspace production-tasks-page" aria-live="polite">
        <TasksHeader
          title="Tasks"
          summary={summary}
          search={search}
          onSearch={setSearch}
          searchPlaceholder="Search by task, code or client"
          view={view}
          onView={chooseView}
          action={
            <button type="button" className="management-primary-action" onClick={() => openSheet({ mode: "create" })}>
              <Plus /> New task
            </button>
          }
        />
        <QuickFilters chips={chips} value={quick} onChange={setQuick}>
          <LooplessSelect
            value={status}
            onValueChange={setStatus}
            ariaLabel="Filter tasks by status"
            options={STATUS_FILTER_OPTIONS}
          />
          <LooplessSelect
            value={client}
            onValueChange={setClient}
            ariaLabel="Filter tasks by client"
            options={clientOptions}
          />
        </QuickFilters>
        {notice && !sheet && <div className="organization-notice">{notice}</div>}
        {error ? (
          <div className="organization-state">
            <h3>{error}</h3>
            <button type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : loading && items.length === 0 ? (
          <div className="organization-skeleton">
            {[1, 2, 3].map((row) => (
              <i key={row} />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <div className="organization-state">
            <ClipboardList />
            <h3>{filtered ? "No tasks match these filters" : "No tasks yet"}</h3>
            <p>
              {filtered
                ? "Try another filter, or clear the search."
                : "Create a task for a client and assign it to your team."}
            </p>
            {filtered ? (
              <button
                type="button"
                onClick={() => {
                  setQuick("all");
                  setSearch("");
                  setStatus("");
                  setClient("");
                }}
              >
                Clear filters
              </button>
            ) : (
              <button type="button" onClick={() => openSheet({ mode: "create" })}>
                <Plus /> New task
              </button>
            )}
          </div>
        ) : view === "board" ? (
          <TaskBoard
            items={visible}
            allColumns={quick === "all" && !status}
            onOpen={(id) => openSheet({ mode: "detail", id })}
            onMoved={(message) => {
              setNotice(message);
              void load();
            }}
          />
        ) : (
          <TaskTable items={visible} onOpen={(id) => openSheet({ mode: "detail", id })} />
        )}
        {sheet && (
          <TaskSheet
            label={sheet.mode === "create" ? "New task" : sheet.mode === "edit" ? `Edit ${sheet.task.code}` : "Task"}
            onClose={closeSheet}
          >
            {sheet.mode === "detail" ? (
              <TaskDetail
                key={sheet.id}
                id={sheet.id}
                people={people}
                notice={notice}
                onClose={closeSheet}
                onEdit={(task) => openSheet({ mode: "edit", task })}
                onNotice={setNotice}
                onChanged={refresh}
              />
            ) : (
              <TaskForm
                key={sheet.mode === "edit" ? sheet.task.id : "new"}
                task={sheet.mode === "edit" ? sheet.task : null}
                prefill={sheet.mode === "create" ? sheet.prefill : undefined}
                clients={clients}
                services={services}
                people={people}
                onClose={closeSheet}
                onCancel={() =>
                  sheet.mode === "edit" ? openSheet({ mode: "detail", id: sheet.task.id }) : closeSheet()
                }
                onSaved={(id, message) => {
                  openSheet({ mode: "detail", id }, message);
                  void load();
                }}
              />
            )}
          </TaskSheet>
        )}
      </section>
    </div>
  );
}

function TaskTable({ items, onOpen }: { items: AdminTask[]; onOpen: (id: string) => void }) {
  return (
    <div className="organization-table production-tasks" role="table">
      <div className="organization-table-head">
        <span>Task</span>
        <span>Client</span>
        <span>Assigned to</span>
        <span>Due</span>
        <span>Status</span>
        <span className="production-money">Client price</span>
        <span>Actions</span>
      </div>
      {items.map((task) => (
        <article key={task.id}>
          <div className="production-cell">
            <small>
              {task.code} · {task.service.name} · {PRIORITY_LABELS[task.priority]}
            </small>
            <strong>{task.title}</strong>
          </div>
          <span>{task.client.name}</span>
          <span>{task.assignee ? task.assignee.name : "Not assigned"}</span>
          <span className={task.is_overdue ? "production-overdue" : undefined}>
            {task.due_date ? formatDate(task.due_date) : "—"}
          </span>
          <em className={statusTone(task.status)}>{STATUS_LABELS[task.status]}</em>
          <span className="production-money">{money(task.client_price, task.currency)}</span>
          <CrudActionButtons view={{ label: `View ${task.code}`, onClick: () => onOpen(task.id) }} />
        </article>
      ))}
    </div>
  );
}

const BOARD_COLUMNS: TaskStatus[] = [
  "PENDING",
  "ASSIGNED",
  "IN_PROGRESS",
  "SUBMITTED",
  "REVIEW",
  "APPROVED",
  "COMPLETED",
  "CANCELLED",
];

/** Kanban board: one column per status. Cards can be dragged to any status the Admin may set. */
function TaskBoard({
  items,
  allColumns,
  onOpen,
  onMoved,
}: {
  items: AdminTask[];
  allColumns: boolean;
  onOpen: (id: string) => void;
  onMoved: (message: string) => void;
}) {
  const [dragging, setDragging] = useState<AdminTask | null>(null);
  const [hover, setHover] = useState<TaskStatus | null>(null);
  const [pending, setPending] = useState<{ task: AdminTask; target: TaskStatus } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Without a filter every workflow column shows (Cancelled only when it has work). With a quick
  // filter or a status filter, only the columns that hold matching tasks are shown.
  const columns = BOARD_COLUMNS.filter((status) =>
    allColumns && status !== "CANCELLED" ? true : items.some((task) => task.status === status),
  );
  const canDrop = (status: TaskStatus) =>
    Boolean(dragging && dragging.status !== status && dragging.allowed_statuses.includes(status));

  async function move(task: AdminTask, target: TaskStatus) {
    setSaving(true);
    setError("");
    try {
      const result = await api<TaskWrite>(`/api/company/tasks/${task.id}/status`, {
        method: "POST",
        json: { status: target, note: "" },
      });
      setPending(null);
      const warning = result.budget.exceeds_with_new_task ? ` ${result.budget.message}` : "";
      onMoved(`${task.code} moved to ${STATUS_LABELS[target]}.${warning}`);
    } catch (requestError) {
      setPending(null);
      setError(errorText(requestError, "Unable to move the task."));
    } finally {
      setSaving(false);
    }
  }

  function drop(target: TaskStatus) {
    const task = dragging;
    setDragging(null);
    setHover(null);
    if (!task || !canDropFor(task, target)) return;
    if (BILLING_STATUSES.includes(target)) setPending({ task, target });
    else void move(task, target);
  }

  return (
    <>
      {error && <div className="organization-form-error">{error}</div>}
      <div className="production-board" aria-label="Tasks by status">
        {columns.map((status) => {
          const tasks = items.filter((task) => task.status === status);
          const droppable = canDrop(status);
          return (
            <section
              key={status}
              className={`production-board-column${hover === status && droppable ? " drop-target" : ""}${
                dragging && !droppable && dragging.status !== status ? " drop-blocked" : ""
              }`}
              data-status={status}
              aria-label={`${STATUS_LABELS[status]}, ${tasks.length} tasks`}
              onDragOver={(event) => {
                if (!droppable) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                setHover(status);
              }}
              onDragLeave={() => setHover((current) => (current === status ? null : current))}
              onDrop={(event) => {
                event.preventDefault();
                drop(status);
              }}
            >
              <header>
                <em className={statusTone(status)}>{STATUS_LABELS[status]}</em>
                <span>{tasks.length}</span>
              </header>
              {tasks.length === 0 ? (
                <p className="production-board-empty">No tasks</p>
              ) : (
                tasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    code={task.code}
                    service={task.service.name}
                    title={task.title}
                    client={task.client.name}
                    priority={task.priority}
                    person={task.assignee?.name ?? null}
                    dueDate={task.due_date}
                    overdue={task.is_overdue}
                    closed={CLOSED_STATUSES.includes(task.status)}
                    amount={money(task.client_price, task.currency)}
                    files={task.files_count}
                    comments={task.comments_count}
                    dragging={dragging?.id === task.id}
                    draggable={!saving}
                    onOpen={() => onOpen(task.id)}
                    onDragStart={(event) => {
                      event.dataTransfer.effectAllowed = "move";
                      event.dataTransfer.setData("text/plain", task.id);
                      setDragging(task);
                    }}
                    onDragEnd={() => {
                      setDragging(null);
                      setHover(null);
                    }}
                  />
                ))
              )}
            </section>
          );
        })}
      </div>
      <p className="production-muted">Drag a card to another column to change its status, or open it for details.</p>
      <ConfirmationDialog
        open={Boolean(pending)}
        title={`Move ${pending?.task.code ?? "task"} to ${pending ? STATUS_LABELS[pending.target] : ""}?`}
        description={
          pending?.target === "CANCELLED"
            ? "The task will stop counting toward the budget, billing and commission."
            : `${pending ? money(pending.task.client_price, pending.task.currency) : ""} will be billed to ${
                pending?.task.client.name ?? "the client"
              }${pending?.task.commission ? " and the manager's commission recorded" : ""}.`
        }
        confirmLabel={`Move to ${pending ? STATUS_LABELS[pending.target] : ""}`}
        tone={pending?.target === "CANCELLED" ? "danger" : "primary"}
        loading={saving}
        onCancel={() => setPending(null)}
        onConfirm={() => pending && void move(pending.task, pending.target)}
      />
    </>
  );
}

function canDropFor(task: AdminTask, target: TaskStatus): boolean {
  return task.status !== target && task.allowed_statuses.includes(target);
}

type FormValues = {
  client_id: string;
  service_id: string;
  title: string;
  description: string;
  priority: TaskPriority;
  due_date: string;
  assignee_user_id: string;
  monitor_user_id: string;
  client_price: string;
  client_price_reason: string;
  commission: string;
  commission_reason: string;
};

function TaskForm({
  task,
  prefill,
  clients,
  services,
  people,
  onClose,
  onCancel,
  onSaved,
}: {
  task: AdminTaskDetail | null;
  prefill?: Prefill;
  clients: ChoiceItem[];
  services: ChoiceItem[];
  people: AssigneeOption[];
  onClose: () => void;
  onCancel: () => void;
  onSaved: (id: string, message: string) => void;
}) {
  const editing = Boolean(task);
  const [values, setValues] = useState<FormValues>({
    client_id: task?.client.id ?? prefill?.client_id ?? "",
    service_id: task?.service.id ?? "",
    title: task?.title ?? prefill?.title ?? "",
    description: task?.description ?? prefill?.description ?? "",
    priority: task?.priority ?? "MEDIUM",
    due_date: task?.due_date ?? prefill?.due_date ?? "",
    assignee_user_id: "",
    monitor_user_id: "",
    client_price: "",
    client_price_reason: "",
    commission: "",
    commission_reason: "",
  });
  const [touched, setTouched] = useState({ price: false, commission: false });
  const [errors, setErrors] = useState<Partial<Record<keyof FormValues, string>>>({});
  const [loadedPreview, setLoadedPreview] = useState<{ key: string; data: PricingPreview } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const assignee = people.find((person) => person.id === values.assignee_user_id) ?? null;
  const isManager = assignee?.role === "MANAGER";

  // Look up default rates and budget impact whenever client, service, assignee or price changes.
  const previewKey = `${values.client_id}|${values.service_id}|${values.assignee_user_id}`;
  const preview = !editing && loadedPreview?.key === previewKey ? loadedPreview.data : null;
  useEffect(() => {
    if (editing || !values.client_id || !values.service_id) return;
    const timer = window.setTimeout(async () => {
      try {
        const data = await api<PricingPreview>(
          `/api/company/tasks/pricing-preview${query({
            client_id: values.client_id,
            service_id: values.service_id,
            assignee_user_id: values.assignee_user_id,
            client_price: touched.price && values.client_price ? values.client_price : null,
          })}`,
        );
        setLoadedPreview({ key: previewKey, data });
        if (!touched.price) {
          setValues((current) => ({ ...current, client_price: data.client_price_default ?? "" }));
        }
        if (!touched.commission) {
          setValues((current) => ({ ...current, commission: data.commission_default ?? "" }));
        }
      } catch {
        setLoadedPreview(null);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [
    editing,
    previewKey,
    values.client_id,
    values.service_id,
    values.assignee_user_id,
    values.client_price,
    touched.price,
    touched.commission,
  ]);

  function update<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: validateField(key, value) }));
    if (key === "client_price") setTouched((current) => ({ ...current, price: true }));
    if (key === "commission") setTouched((current) => ({ ...current, commission: true }));
    if (key === "assignee_user_id") {
      setTouched((current) => ({ ...current, commission: false }));
      if (value === values.monitor_user_id) setValues((current) => ({ ...current, monitor_user_id: "" }));
    }
  }

  function validateField(key: keyof FormValues, value: string): string {
    if (key === "title" && value.trim().length < 2) return "Enter at least 2 characters.";
    if ((key === "client_id" || key === "service_id") && !value) return "This field is required.";
    if ((key === "client_price" || key === "commission") && value && Number(value) < 0)
      return "Amount cannot be negative.";
    return "";
  }

  const priceChanged =
    !editing &&
    values.client_price !== "" &&
    (preview?.client_price_default == null || Number(values.client_price) !== Number(preview.client_price_default));
  const commissionChanged =
    isManager &&
    values.commission !== "" &&
    (preview?.commission_default == null || Number(values.commission) !== Number(preview.commission_default));

  async function save(event: FormEvent) {
    event.preventDefault();
    const next: Partial<Record<keyof FormValues, string>> = {};
    for (const key of ["title", "client_id", "service_id"] as const) {
      const message = validateField(key, values[key]);
      if (message) next[key] = message;
    }
    if (!editing && !values.client_price) next.client_price = "Enter the price for this task.";
    if (!editing && !values.due_date) next.due_date = "Choose the due date.";
    if (!editing && isManager && !values.commission) next.commission = "Enter the commission for this manager.";
    setErrors(next);
    if (Object.values(next).some(Boolean)) return;
    setSaving(true);
    setError("");
    try {
      if (task) {
        await api(`/api/company/tasks/${task.id}`, {
          method: "PATCH",
          json: {
            title: values.title.trim(),
            description: values.description.trim(),
            priority: values.priority,
            due_date: values.due_date || null,
          },
        });
        onSaved(task.id, "Task details updated.");
        return;
      }
      const result = await api<TaskWrite>("/api/company/tasks", {
        method: "POST",
        json: {
          client_id: values.client_id,
          service_id: values.service_id,
          title: values.title.trim(),
          description: values.description.trim(),
          priority: values.priority,
          due_date: values.due_date || null,
          client_price: values.client_price,
          client_price_reason: values.client_price_reason.trim(),
          assignee_user_id: values.assignee_user_id || null,
          monitor_user_id: values.monitor_user_id || null,
          commission: isManager ? values.commission : null,
          commission_reason: isManager ? values.commission_reason.trim() : "",
        },
      });
      const warning = result.budget.exceeds_with_new_task ? ` ${result.budget.message}` : "";
      let linked = "";
      if (prefill?.calendar_entry_id) {
        // Link the new task to the calendar entry it came from, so Edited ticks on approval.
        try {
          await api(`/api/company/calendar/${prefill.calendar_entry_id}/task`, {
            method: "PUT",
            json: { task_id: result.task.id },
          });
          linked = " Linked to the calendar entry.";
        } catch {
          linked = " It could not be linked to the calendar entry; link it from the calendar.";
        }
      }
      onSaved(result.task.id, `Task ${result.task.code} created.${linked}${warning}`);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to save the task."));
    } finally {
      setSaving(false);
    }
  }

  const currency = preview?.currency ?? task?.currency ?? "INR";
  const clientOptions = [
    { value: "", label: "Choose a client" },
    ...clients.filter((item) => item.status !== "INACTIVE").map((item) => ({ value: item.id, label: item.name })),
  ];
  const serviceOptions = [
    { value: "", label: "Choose a service" },
    ...services.filter((item) => item.status !== "INACTIVE").map((item) => ({ value: item.id, label: item.name })),
  ];

  return (
    <>
      <SheetHeader
        eyebrow={editing ? `${task?.code} · Edit` : "New task"}
        title={editing ? "Edit task details" : "Create task"}
        onClose={onClose}
      />
      <section className="management-editor production-panel production-sheet-form">
        <header>
          <i aria-hidden="true">
            <ClipboardList />
          </i>
          <div>
            <span>{editing ? "DETAILS" : "TASK"}</span>
            <h2>{editing ? "Title, priority and due date" : "Work, assignment and price"}</h2>
            <p>
              {editing
                ? "Client, service, prices and assignment are changed from the task panel so every change is recorded."
                : "The client's rate fills in automatically. Change it here for special work, such as a long video."}
            </p>
          </div>
        </header>
        <form className="management-form organization-form-grid" noValidate onSubmit={save}>
          {error && <div className="management-form-message">{error}</div>}
          {!editing && (
            <>
              <Field label="Client" error={errors.client_id}>
                <LooplessSelect
                  value={values.client_id}
                  onValueChange={(value) => update("client_id", value)}
                  ariaLabel="Client"
                  options={clientOptions}
                />
              </Field>
              <Field label="Service" error={errors.service_id}>
                <LooplessSelect
                  value={values.service_id}
                  onValueChange={(value) => update("service_id", value)}
                  ariaLabel="Service"
                  options={serviceOptions}
                />
              </Field>
            </>
          )}
          <Field label="Task title" error={errors.title} wide>
            <span className="management-input">
              <ClipboardList aria-hidden="true" />
              <input
                value={values.title}
                onChange={(event) => update("title", event.target.value)}
                aria-invalid={Boolean(errors.title)}
                placeholder="For example: Diwali offer reel"
                maxLength={200}
              />
            </span>
          </Field>
          <Field label="Description" wide>
            <span className="management-input organization-textarea-shell">
              <FileText aria-hidden="true" />
              <textarea
                value={values.description}
                onChange={(event) => update("description", event.target.value)}
                placeholder="Requirements, length, style, references to follow"
                maxLength={5000}
              />
            </span>
          </Field>
          <Field label="Priority">
            <LooplessSelect
              value={values.priority}
              onValueChange={(value) => update("priority", value as TaskPriority)}
              ariaLabel="Priority"
              options={PRIORITY_OPTIONS}
            />
          </Field>
          <Field label="Due date" error={errors.due_date}>
            <LooplessDate
              value={values.due_date}
              onValueChange={(value) => update("due_date", value)}
              ariaLabel="Due date"
              clearable={editing}
            />
          </Field>
          {!editing && (
            <>
              <div className="production-section-title">
                <span>Assignment</span>
                <small>Leave it unassigned to plan the work first. Only managers can monitor a task.</small>
              </div>
              <Field label="Assign to">
                <LooplessSelect
                  value={values.assignee_user_id}
                  onValueChange={(value) => update("assignee_user_id", value)}
                  ariaLabel="Assign to"
                  options={peopleOptions(people, "Not assigned yet")}
                />
              </Field>
              <Field label="Monitor (optional)">
                <LooplessSelect
                  value={values.monitor_user_id}
                  onValueChange={(value) => update("monitor_user_id", value)}
                  ariaLabel="Monitoring manager"
                  options={peopleOptions(
                    people,
                    "No monitor",
                    (person) => person.role === "MANAGER" && person.id !== values.assignee_user_id,
                  )}
                />
              </Field>
              <div className="production-section-title">
                <span>Price</span>
                <small>Saved on this task. Later rate changes never alter it.</small>
              </div>
              <Field
                label={`Client price (${currency})`}
                error={errors.client_price}
                hint={
                  preview
                    ? preview.client_price_default
                      ? `Default rate for ${preview.client.name}: ${money(preview.client_price_default, currency)}`
                      : `No rate set for ${preview.client.name} on ${preview.service.name}. Enter the price.`
                    : "Choose a client and service to load the rate."
                }
              >
                <span className="management-input">
                  <Wallet aria-hidden="true" />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={values.client_price}
                    onChange={(event) => update("client_price", event.target.value)}
                    aria-invalid={Boolean(errors.client_price)}
                    placeholder="0.00"
                  />
                </span>
              </Field>
              {priceChanged ? (
                <Field label="Reason for this price">
                  <span className="management-input">
                    <Pencil aria-hidden="true" />
                    <input
                      value={values.client_price_reason}
                      onChange={(event) => update("client_price_reason", event.target.value)}
                      placeholder="For example: long video"
                      maxLength={500}
                    />
                  </span>
                </Field>
              ) : (
                <span aria-hidden="true" />
              )}
              {isManager && (
                <>
                  <Field
                    label={`Manager commission (${currency})`}
                    error={errors.commission}
                    hint={
                      preview?.commission_default
                        ? `Default for ${assignee?.name}: ${money(preview.commission_default, currency)}`
                        : `No commission set for ${assignee?.name} on this service. Enter it.`
                    }
                  >
                    <span className="management-input">
                      <Wallet aria-hidden="true" />
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={values.commission}
                        onChange={(event) => update("commission", event.target.value)}
                        aria-invalid={Boolean(errors.commission)}
                        placeholder="0.00"
                      />
                    </span>
                  </Field>
                  {commissionChanged ? (
                    <Field label="Reason for this commission">
                      <span className="management-input">
                        <Pencil aria-hidden="true" />
                        <input
                          value={values.commission_reason}
                          onChange={(event) => update("commission_reason", event.target.value)}
                          placeholder="For example: long video"
                          maxLength={500}
                        />
                      </span>
                    </Field>
                  ) : (
                    <span aria-hidden="true" />
                  )}
                </>
              )}
              {assignee?.role === "EMPLOYEE" && (
                <div className="production-info">
                  {assignee.name} is a salaried employee, so this task has no commission.
                </div>
              )}
              <BudgetBanner budget={preview?.budget ?? null} />
            </>
          )}
          <div className="management-form-footer">
            <button type="button" className="management-secondary-action" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="management-primary-action" disabled={saving}>
              {saving && <RefreshCw className="spin" />}
              {saving ? "Saving…" : editing ? "Save changes" : "Create task"}
            </button>
          </div>
        </form>
      </section>
    </>
  );
}

function TaskDetail({
  id,
  people,
  notice,
  onClose,
  onEdit,
  onNotice,
  onChanged,
}: {
  id: string;
  people: AssigneeOption[];
  notice: string;
  onClose: () => void;
  onEdit: (task: AdminTaskDetail) => void;
  onNotice: (message: string) => void;
  onChanged: () => void;
}) {
  const [task, setTask] = useState<AdminTaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setTask(await api<AdminTaskDetail>(`/api/company/tasks/${id}`));
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load the task."));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  // A submission, comment or file from the team refreshes the open task.
  useLiveRefresh(["task."], () => void load());

  const applyWrite = (result: TaskWrite | AdminTaskDetail, message: string) => {
    const detail = "task" in result ? result.task : result;
    const warning = "budget" in result && result.budget.exceeds_with_new_task ? ` ${result.budget.message}` : "";
    setTask(detail);
    onNotice(`${message}${warning}`);
    onChanged();
  };

  if (loading && !task) {
    return (
      <>
        <SheetHeader eyebrow="Task" title="Loading…" onClose={onClose} />
        <div className="organization-skeleton">
          {[1, 2, 3].map((row) => (
            <i key={row} />
          ))}
        </div>
      </>
    );
  }
  if (error || !task) {
    return (
      <>
        <SheetHeader eyebrow="Task" title="Task not available" onClose={onClose} />
        <div className="organization-state">
          <h3>{error || "Task not found."}</h3>
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <SheetHeader
        eyebrow={`${task.code} · ${task.service.name}`}
        title={task.title}
        onClose={onClose}
        badges={
          <>
            <em className={statusTone(task.status)}>{STATUS_LABELS[task.status]}</em>
            {task.is_overdue && <em className="overdue">Overdue</em>}
            {task.billable && <em className="active">Billable</em>}
            <em>{PRIORITY_LABELS[task.priority]} priority</em>
          </>
        }
        actions={
          <button type="button" className="management-secondary-action" onClick={() => onEdit(task)}>
            <Pencil /> Edit
          </button>
        }
      />
      <StatusProgress status={task.status} />
      {notice && <div className="organization-notice">{notice}</div>}
      <Panel icon={<FileText />} eyebrow="OVERVIEW" title="Task details">
        <div className="production-panel-body">
          <dl className="production-facts">
            <div>
              <dt>Client</dt>
              <dd>{task.client.name}</dd>
            </div>
            <div>
              <dt>Service</dt>
              <dd>{task.service.name}</dd>
            </div>
            <div>
              <dt>Due date</dt>
              <dd>{formatDate(task.due_date)}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>
                {formatDateTime(task.created_at)}
                <small>by {task.created_by_name}</small>
              </dd>
            </div>
            {task.approved_at && (
              <div>
                <dt>Approved</dt>
                <dd>{formatDateTime(task.approved_at)}</dd>
              </div>
            )}
            {task.completed_at && (
              <div>
                <dt>Completed</dt>
                <dd>{formatDateTime(task.completed_at)}</dd>
              </div>
            )}
          </dl>
          {task.description ? (
            <p className="production-description">{task.description}</p>
          ) : (
            <p className="production-muted">No description added.</p>
          )}
        </div>
      </Panel>
      <PricePanel key={`${task.client_price}|${task.commission}`} task={task} onSaved={applyWrite} />
      <AssignmentPanel
        key={`${task.assignee?.id ?? ""}|${task.monitor?.id ?? ""}`}
        task={task}
        people={people}
        onSaved={applyWrite}
      />
      <StatusPanel key={task.status} task={task} onSaved={applyWrite} />
      <FilesPanel
        task={task}
        onChange={(files) => {
          setTask({ ...task, files });
          onChanged();
        }}
        onNotice={onNotice}
      />
      <CommentsPanel
        task={task}
        onChange={(comments) => {
          setTask({ ...task, comments });
          onChanged();
        }}
      />
      <ActivityPanel task={task} />
    </>
  );
}

function StatusPanel({
  task,
  onSaved,
}: {
  task: AdminTaskDetail;
  onSaved: (result: TaskWrite, message: string) => void;
}) {
  const [target, setTarget] = useState("");
  const [note, setNote] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setSaving(true);
    setError("");
    try {
      const result = await api<TaskWrite>(`/api/company/tasks/${task.id}/status`, {
        method: "POST",
        json: { status: target, note: note.trim() },
      });
      setConfirming(false);
      onSaved(result, `Status changed to ${STATUS_LABELS[target as TaskStatus]}.`);
    } catch (requestError) {
      setConfirming(false);
      setError(errorText(requestError, "Unable to change the status."));
    } finally {
      setSaving(false);
    }
  }

  const options = [
    { value: "", label: "Choose new status" },
    ...task.allowed_statuses.map((status) => ({ value: status, label: STATUS_LABELS[status] })),
  ];
  const sensitive = BILLING_STATUSES.includes(target as TaskStatus);

  return (
    <Panel
      icon={<RefreshCw />}
      eyebrow="WORKFLOW"
      title={STATUS_LABELS[task.status]}
      description="Approving makes the task billable: it counts toward the client's budget and the manager's commission."
    >
      <div className="production-panel-body">
        {error && <div className="management-form-message">{error}</div>}
        {!task.assignee && <p className="production-muted">Assign someone before moving this task forward.</p>}
        <Field label="Move to">
          <LooplessSelect value={target} onValueChange={setTarget} ariaLabel="New status" options={options} />
        </Field>
        <Field label="Note (optional)">
          <span className="management-input">
            <MessageSquare aria-hidden="true" />
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={1000}
              placeholder="Why the status changed"
            />
          </span>
        </Field>
        <div className="production-inline-actions">
          <button
            type="button"
            className="management-primary-action"
            disabled={!target || saving}
            onClick={() => (sensitive ? setConfirming(true) : void submit())}
          >
            {saving && <RefreshCw className="spin" />}
            {saving ? "Saving…" : "Update status"}
          </button>
        </div>
      </div>
      <ConfirmationDialog
        open={confirming}
        title={`${target === "CANCELLED" ? "Cancel" : target === "COMPLETED" ? "Complete" : "Approve"} ${task.code}?`}
        description={
          target === "CANCELLED"
            ? "The task will stop counting toward the budget, billing and commission."
            : `${money(task.client_price, task.currency)} will be billed to ${task.client.name}${
                task.commission
                  ? ` and ${money(task.commission, task.currency)} commission recorded for ${task.assignee?.name}`
                  : ""
              }.`
        }
        confirmLabel={
          target === "CANCELLED" ? "Cancel task" : target === "COMPLETED" ? "Mark completed" : "Approve task"
        }
        tone={target === "CANCELLED" ? "danger" : "primary"}
        loading={saving}
        onCancel={() => setConfirming(false)}
        onConfirm={() => void submit()}
      />
    </Panel>
  );
}

function PricePanel({
  task,
  onSaved,
}: {
  task: AdminTaskDetail;
  onSaved: (result: TaskWrite, message: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState({
    price: task.client_price,
    priceReason: "",
    commission: task.commission ?? "",
    commissionReason: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const hasCommission = task.assignee?.role === "MANAGER";

  async function save(event: FormEvent) {
    event.preventDefault();
    if (values.price === "" || Number(values.price) < 0) return setError("Enter a valid client price.");
    if (hasCommission && (values.commission === "" || Number(values.commission) < 0))
      return setError("Enter a valid commission.");
    setSaving(true);
    setError("");
    try {
      const result = await api<TaskWrite>(`/api/company/tasks/${task.id}/prices`, {
        method: "POST",
        json: {
          client_price: values.price,
          client_price_reason: values.priceReason.trim(),
          ...(hasCommission
            ? { commission: values.commission, commission_reason: values.commissionReason.trim() }
            : {}),
        },
      });
      setEditing(false);
      onSaved(result, "Prices updated.");
    } catch (requestError) {
      setError(errorText(requestError, "Unable to update prices."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel
      icon={<Wallet />}
      eyebrow="MONEY"
      title={`Margin ${money(task.margin, task.currency)}`}
      description="Visible only to you."
    >
      {editing ? (
        <form className="management-form" noValidate onSubmit={save}>
          {error && <div className="management-form-message">{error}</div>}
          <Field label={`Client price (${task.currency})`} wide>
            <span className="management-input">
              <Wallet aria-hidden="true" />
              <input
                type="number"
                min="0"
                step="0.01"
                value={values.price}
                onChange={(event) => setValues({ ...values, price: event.target.value })}
              />
            </span>
          </Field>
          <Field label="Reason" wide>
            <span className="management-input">
              <Pencil aria-hidden="true" />
              <input
                value={values.priceReason}
                onChange={(event) => setValues({ ...values, priceReason: event.target.value })}
                maxLength={500}
                placeholder="For example: long video"
              />
            </span>
          </Field>
          {hasCommission && (
            <>
              <Field label={`Commission (${task.currency})`} wide>
                <span className="management-input">
                  <Wallet aria-hidden="true" />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={values.commission}
                    onChange={(event) => setValues({ ...values, commission: event.target.value })}
                  />
                </span>
              </Field>
              <Field label="Commission reason" wide>
                <span className="management-input">
                  <Pencil aria-hidden="true" />
                  <input
                    value={values.commissionReason}
                    onChange={(event) => setValues({ ...values, commissionReason: event.target.value })}
                    maxLength={500}
                  />
                </span>
              </Field>
            </>
          )}
          <div className="management-form-footer">
            <button type="button" className="management-secondary-action" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button type="submit" className="management-primary-action" disabled={saving}>
              {saving && <RefreshCw className="spin" />}
              {saving ? "Saving…" : "Save prices"}
            </button>
          </div>
        </form>
      ) : (
        <div className="production-panel-body">
          <dl className="production-facts">
            <div>
              <dt>Client price</dt>
              <dd>
                {money(task.client_price, task.currency)}
                <small>
                  {task.client_price_default === null
                    ? "Entered manually"
                    : Number(task.client_price_default) === Number(task.client_price)
                      ? "Client's default rate"
                      : `Default ${money(task.client_price_default, task.currency)}`}
                </small>
              </dd>
            </div>
            <div>
              <dt>Commission</dt>
              <dd>
                {task.commission === null ? "—" : money(task.commission, task.currency)}
                <small>
                  {task.assignee?.role === "EMPLOYEE"
                    ? "Salaried employee"
                    : task.commission_default !== null && task.commission !== null
                      ? Number(task.commission_default) === Number(task.commission)
                        ? "Manager's default rate"
                        : `Default ${money(task.commission_default, task.currency)}`
                      : task.assignee
                        ? "Entered manually"
                        : "Not assigned"}
                </small>
              </dd>
            </div>
          </dl>
          <div className="production-inline-actions">
            <button type="button" className="management-secondary-action" onClick={() => setEditing(true)}>
              <Pencil /> Change prices
            </button>
          </div>
        </div>
      )}
    </Panel>
  );
}

function AssignmentPanel({
  task,
  people,
  onSaved,
}: {
  task: AdminTaskDetail;
  people: AssigneeOption[];
  onSaved: (result: TaskWrite | AdminTaskDetail, message: string) => void;
}) {
  const [assignee, setAssignee] = useState(task.assignee?.id ?? "");
  const [monitor, setMonitor] = useState(task.monitor?.id ?? "");
  const [commission, setCommission] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const closed = BILLING_STATUSES.includes(task.status);
  const person = people.find((item) => item.id === assignee) ?? null;
  const assigneeChanged = assignee !== (task.assignee?.id ?? "");
  const monitorChanged = monitor !== (task.monitor?.id ?? "");

  // The manager's fixed rate for this task's service (owner request 2026-11-19): shown and
  // filled in when a manager is chosen, and it can be changed for this one task.
  const [rate, setRate] = useState<{ for: string; amount: string | null } | null>(null);
  useEffect(() => {
    if (!assigneeChanged || person?.role !== "MANAGER") return;
    let live = true;
    void api<PricingPreview>(
      `/api/company/tasks/pricing-preview${query({
        client_id: task.client.id,
        service_id: task.service.id,
        assignee_user_id: assignee,
      })}`,
    )
      .then((data) => {
        if (!live) return;
        setRate({ for: assignee, amount: data.commission_default });
        setCommission(data.commission_default ?? "");
      })
      .catch(() => live && setRate({ for: assignee, amount: null }));
    return () => {
      live = false;
    };
  }, [assignee, assigneeChanged, person?.role, task.client.id, task.service.id]);
  const fixed = rate?.for === assignee ? rate.amount : null;
  const changedRate = fixed !== null && commission !== "" && Number(commission) !== Number(fixed);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!assigneeChanged && !monitorChanged) return;
    setSaving(true);
    setError("");
    try {
      if (assigneeChanged) {
        if (!assignee) throw new Error("Choose who should do this task.");
        const result = await api<TaskWrite>(`/api/company/tasks/${task.id}/assign`, {
          method: "POST",
          json: {
            assignee_user_id: assignee,
            monitor_user_id: monitor || null,
            commission: person?.role === "MANAGER" && commission !== "" ? commission : null,
            commission_reason: reason.trim(),
          },
        });
        onSaved(result, `Assigned to ${person?.name ?? "the selected person"}.`);
      } else {
        const result = await api<AdminTaskDetail>(`/api/company/tasks/${task.id}/monitor`, {
          method: "PUT",
          json: { monitor_user_id: monitor || null },
        });
        onSaved(result, monitor ? "Monitor updated." : "Monitor removed.");
      }
    } catch (requestError) {
      setError(errorText(requestError, "Unable to update the assignment."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel
      icon={<UserCheck />}
      eyebrow="ASSIGNMENT"
      title={task.assignee ? task.assignee.name : "Not assigned"}
      description={
        task.monitor ? `Monitored by ${task.monitor.name}` : "No monitor. A monitor can only change the status."
      }
    >
      <form className="management-form" noValidate onSubmit={save}>
        {error && <div className="management-form-message">{error}</div>}
        {closed && <div className="production-info">Approved, completed or cancelled tasks cannot be reassigned.</div>}
        <Field label="Assigned to" wide>
          <LooplessSelect
            value={assignee}
            onValueChange={(value) => {
              setAssignee(value);
              if (value === monitor) setMonitor("");
            }}
            ariaLabel="Assigned to"
            options={peopleOptions(people, "Not assigned yet")}
            disabled={closed}
          />
        </Field>
        <Field label="Monitor" wide>
          <LooplessSelect
            value={monitor}
            onValueChange={setMonitor}
            ariaLabel="Monitoring manager"
            options={peopleOptions(people, "No monitor", (item) => item.role === "MANAGER" && item.id !== assignee)}
          />
        </Field>
        {assigneeChanged && person?.role === "MANAGER" && (
          <>
            <Field
              label={`Commission (${task.currency})`}
              wide
              hint={
                rate?.for !== assignee
                  ? "Looking up this manager's rate…"
                  : fixed !== null
                    ? `Fixed rate for ${person.name} on ${task.service.name}: ${money(fixed, task.currency)}. Change it for this task if needed.`
                    : `No fixed rate for ${person.name} on ${task.service.name} yet. Enter it here, or set it in Settings → Services & Pricing → Manager rates.`
              }
            >
              <span className="management-input">
                <Wallet aria-hidden="true" />
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={commission}
                  onChange={(event) => setCommission(event.target.value)}
                  placeholder={fixed ?? "Commission"}
                />
              </span>
            </Field>
            <Field label={changedRate ? "Reason for the change" : "Reason"} wide>
              <span className="management-input">
                <Pencil aria-hidden="true" />
                <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} />
              </span>
            </Field>
          </>
        )}
        <div className="management-form-footer">
          <button
            type="submit"
            className="management-primary-action"
            disabled={saving || (!assigneeChanged && !monitorChanged)}
          >
            {saving && <RefreshCw className="spin" />}
            {saving ? "Saving…" : "Save assignment"}
          </button>
        </div>
      </form>
    </Panel>
  );
}

function FilesPanel({
  task,
  onChange,
  onNotice,
}: {
  task: AdminTaskDetail;
  onChange: (files: AdminTaskDetail["files"]) => void;
  onNotice: (message: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function upload(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", "REFERENCE");
      onChange(
        await api<AdminTaskDetail["files"]>(`/api/company/tasks/${task.id}/files`, { method: "POST", body: form }),
      );
      onNotice(`${file.name} uploaded.`);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to upload the file."));
    } finally {
      setUploading(false);
    }
  }

  async function remove(fileId: string) {
    setRemoving(fileId);
    setError("");
    try {
      onChange(
        await api<AdminTaskDetail["files"]>(`/api/company/tasks/${task.id}/files/${fileId}`, { method: "DELETE" }),
      );
      setConfirmId(null);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to delete the file."));
    } finally {
      setRemoving(null);
    }
  }

  const confirmFile = task.files.find((file) => file.id === confirmId);

  return (
    <Panel
      icon={<Paperclip />}
      eyebrow="FILES"
      title="Reference files and deliverables"
      description="Stored on your server. Only you and the people on this task can download them."
    >
      <div className="production-panel-body">
        {error && <div className="management-form-message">{error}</div>}
        {task.files.length === 0 ? (
          <p className="production-muted">No files yet.</p>
        ) : (
          <ul className="production-list">
            {task.files.map((file) => (
              <li key={file.id}>
                <div>
                  <strong>{file.file_name}</strong>
                  <small>
                    {file.kind === "REFERENCE" ? "Reference" : "Deliverable"} · {fileSize(file.size_bytes)} ·{" "}
                    {file.uploaded_by_name} · {formatDateTime(file.created_at)}
                  </small>
                </div>
                <span className="production-inline-actions">
                  <a
                    className="production-icon-button"
                    href={`/api/company/tasks/${task.id}/files/${file.id}`}
                    aria-label={`Download ${file.file_name}`}
                    title="Download"
                  >
                    <Download />
                  </a>
                  <button
                    type="button"
                    className="production-icon-button danger"
                    aria-label={`Delete ${file.file_name}`}
                    title="Delete"
                    disabled={removing === file.id}
                    onClick={() => setConfirmId(file.id)}
                  >
                    <Trash2 />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
        <div className="production-inline-actions">
          <label className={`production-upload${uploading ? " disabled" : ""}`}>
            {uploading ? <RefreshCw className="spin" /> : <Upload />}
            {uploading ? "Uploading…" : "Add reference file"}
            <input
              type="file"
              disabled={uploading}
              onChange={(event) => {
                void upload(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
          </label>
        </div>
      </div>
      <ConfirmationDialog
        open={Boolean(confirmFile)}
        title={`Delete ${confirmFile?.file_name ?? "file"}?`}
        description="The file will be removed from your server. This cannot be undone."
        confirmLabel="Delete file"
        tone="danger"
        loading={Boolean(removing)}
        onCancel={() => setConfirmId(null)}
        onConfirm={() => confirmId && void remove(confirmId)}
      />
    </Panel>
  );
}

function CommentsPanel({
  task,
  onChange,
}: {
  task: AdminTaskDetail;
  onChange: (comments: AdminTaskDetail["comments"]) => void;
}) {
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function post(event: FormEvent) {
    event.preventDefault();
    if (!content.trim()) return;
    setSaving(true);
    setError("");
    try {
      onChange(
        await api<AdminTaskDetail["comments"]>(`/api/company/tasks/${task.id}/comments`, {
          method: "POST",
          json: { content: content.trim() },
        }),
      );
      setContent("");
    } catch (requestError) {
      setError(errorText(requestError, "Unable to post the comment."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel
      icon={<MessageSquare />}
      eyebrow="COMMENTS"
      title="Discussion"
      description="Shared with the assignee and monitor. Clients never see comments."
    >
      <div className="production-panel-body">
        {task.comments.length === 0 ? (
          <p className="production-muted">No comments yet.</p>
        ) : (
          <ul className="production-list">
            {task.comments.map((comment) => (
              <li key={comment.id}>
                <div>
                  <strong>{comment.author_name}</strong>
                  <p>{comment.content}</p>
                  <small>{formatDateTime(comment.created_at)}</small>
                </div>
              </li>
            ))}
          </ul>
        )}
        <form className="production-comment-form" onSubmit={post}>
          {error && <div className="management-form-message">{error}</div>}
          <span className="management-input organization-textarea-shell">
            <MessageSquare aria-hidden="true" />
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Write a comment"
              maxLength={5000}
            />
          </span>
          <div className="production-inline-actions">
            <button type="submit" className="management-primary-action" disabled={saving || !content.trim()}>
              {saving ? <RefreshCw className="spin" /> : <Send />}
              {saving ? "Posting…" : "Post comment"}
            </button>
          </div>
        </form>
      </div>
    </Panel>
  );
}

function ActivityPanel({ task }: { task: AdminTaskDetail }) {
  const entries = [
    ...task.status_history.map((item) => ({
      id: item.id,
      at: item.created_at,
      title:
        item.from_status === null
          ? `Created as ${STATUS_LABELS[item.to_status]}`
          : item.from_status === item.to_status
            ? item.note || "Reassigned"
            : `${STATUS_LABELS[item.from_status]} → ${STATUS_LABELS[item.to_status]}`,
      detail: item.from_status !== null && item.from_status !== item.to_status ? item.note : "",
      actor: item.actor_name,
    })),
    ...task.price_changes.map((item) => ({
      id: item.id,
      at: item.created_at,
      title: `${item.field === "CLIENT_PRICE" ? "Client price" : "Commission"}: ${
        item.old_amount === null ? "no rate" : money(item.old_amount, task.currency)
      } → ${item.new_amount === null ? "none" : money(item.new_amount, task.currency)}`,
      detail: item.reason,
      actor: item.actor_name,
    })),
  ].sort((a, b) => b.at.localeCompare(a.at));

  return (
    <Panel
      icon={<History />}
      eyebrow="ACTIVITY"
      title="History"
      description="Every status and price change, newest first."
    >
      <div className="production-panel-body">
        <ul className="production-list">
          {entries.map((entry) => (
            <li key={entry.id}>
              <div>
                <strong>{entry.title}</strong>
                {entry.detail && <p>{entry.detail}</p>}
                <small>
                  {entry.actor} · {formatDateTime(entry.at)}
                </small>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
