"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ClipboardList,
  Download,
  FileText,
  History,
  MessageSquare,
  Paperclip,
  RefreshCw,
  Send,
  Upload,
  Wallet,
} from "lucide-react";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { Field, Panel, TableSkeleton } from "../production/production-ui";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  api,
  errorText,
  fileSize,
  formatDate,
  formatDateTime,
  money,
  query,
  statusTone,
} from "../production/client";
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
} from "../production/task-board-ui";
import type { Paged, TaskComment, TaskFile, TaskStatus } from "../production/types";
import type { WorkerTask, WorkerTaskDetail } from "./types";
import { useLiveRefresh } from "../realtime/realtime";
import "../styles/organization.css";
import "../styles/service-pricing-settings.css";
import "../styles/production.css";

const COLUMNS: TaskStatus[] = ["ASSIGNED", "IN_PROGRESS", "SUBMITTED", "REVIEW", "APPROVED", "COMPLETED", "CANCELLED"];
const CLOSED: TaskStatus[] = ["APPROVED", "COMPLETED", "CANCELLED"];
const VIEW_KEY = "adverse-workspace-task-view";
const TASK_ID = /^[0-9a-f-]{36}$/i;

/** Keep ?task=<id> in the address bar so an open task can be shared or reloaded. */
function syncUrl(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("task", id);
  else url.searchParams.delete("task");
  window.history.replaceState(null, "", `${url.pathname}${url.search}`);
}

/** "My Tasks" for Managers and Employees: only their own or monitored work, never prices. */
export function WorkspaceTasksPage({ canMonitor }: { canMonitor: boolean }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [items, setItems] = useState<WorkerTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [role, setRole] = useState("");
  const [quick, setQuick] = useState<QuickFilter>("all");
  const [view, setView] = useState<TaskView>("board");
  const [dragging, setDragging] = useState<WorkerTask | null>(null);
  const [hover, setHover] = useState<TaskStatus | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const id = params.get("task");
      if (id && TASK_ID.test(id)) setOpenId(id);
      // Dashboard links: ?status=<STATUS> opens the list filtered to that status.
      const statusFilter = params.get("status");
      if (statusFilter && (COLUMNS as string[]).includes(statusFilter)) setStatus(statusFilter);
      try {
        const saved = window.localStorage.getItem(VIEW_KEY);
        if (saved === "board" || saved === "list") setView(saved);
      } catch {
        // Storage unavailable: keep the board.
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      setError("");
      try {
        const data = await api<Paged<WorkerTask>>(
          `/api/workspace/tasks${query({ search, status, role, page_size: 500 })}`,
        );
        setItems(data.items);
      } catch (requestError) {
        setError(errorText(requestError, "Unable to load your tasks."));
      } finally {
        setLoading(false);
      }
    },
    [search, status, role],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  // New or changed tasks show up live, without a page reload.
  useLiveRefresh(["task."], () => void load(true));

  const choose = (next: TaskView) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_KEY, next);
    } catch {
      // Not remembered; harmless.
    }
  };

  const open = (id: string) => {
    setNotice("");
    setOpenId(id);
    syncUrl(id);
  };
  const close = useCallback(() => {
    setOpenId(null);
    syncUrl(null);
  }, []);
  const refresh = useCallback(() => void load(), [load]);

  async function move(task: WorkerTask, target: TaskStatus) {
    setError("");
    try {
      await api(`/api/workspace/tasks/${task.id}/status`, { method: "POST", json: { status: target, note: "" } });
      setNotice(`${task.code} moved to ${STATUS_LABELS[target]}.`);
      await load();
    } catch (requestError) {
      setError(errorText(requestError, "Unable to move the task."));
    }
  }

  const reviewLabel = canMonitor ? "To review" : "In review";
  const chips = useMemo(
    () =>
      (
        [
          ["all", "All"],
          ["overdue", "Overdue"],
          ["week", "Due this week"],
          ["review", reviewLabel],
        ] as const
      ).map(([key, label]) => ({ key, label, count: items.filter((task) => matchesQuick(task, key)).length })),
    [items, reviewLabel],
  );
  const visible = useMemo(() => items.filter((task) => matchesQuick(task, quick)), [items, quick]);
  const filtered = Boolean(search || status || role || quick !== "all");
  const columns = COLUMNS.filter((column) =>
    quick === "all" && !status && column !== "CANCELLED" ? true : visible.some((task) => task.status === column),
  );
  const canDrop = (column: TaskStatus) =>
    Boolean(dragging && dragging.status !== column && dragging.allowed_statuses.includes(column));

  return (
    <div className="dash-content production-tasks-content">
      <section className="organization-workspace production-workspace production-tasks-page" aria-live="polite">
        <TasksHeader
          title="My Tasks"
          summary={
            loading && items.length === 0 ? "Loading your tasks…" : taskSummary(items, reviewLabel.toLowerCase())
          }
          search={search}
          onSearch={setSearch}
          searchPlaceholder="Search by task or client"
          view={view}
          onView={choose}
        />
        <QuickFilters chips={chips} value={quick} onChange={setQuick}>
          {canMonitor && (
            <LooplessSelect
              value={role}
              onValueChange={setRole}
              ariaLabel="Show tasks"
              options={[
                { value: "", label: "All my tasks" },
                { value: "ASSIGNEE", label: "Assigned to me" },
                { value: "MONITOR", label: "I monitor" },
              ]}
            />
          )}
          <LooplessSelect
            value={status}
            onValueChange={setStatus}
            ariaLabel="Filter by status"
            options={[
              { value: "", label: "All statuses" },
              ...COLUMNS.map((value) => ({ value, label: STATUS_LABELS[value] })),
            ]}
          />
        </QuickFilters>
        {notice && !openId && <div className="organization-notice">{notice}</div>}
        {error && <div className="organization-form-error">{error}</div>}
        {loading && items.length === 0 ? (
          <TableSkeleton />
        ) : visible.length === 0 ? (
          <div className="organization-state">
            <ClipboardList />
            <h3>{filtered ? "No tasks match these filters" : "No tasks yet"}</h3>
            <p>
              {filtered
                ? "Try another filter, or clear the search."
                : "Tasks appear here when the Admin assigns work to you."}
            </p>
            {filtered && (
              <button
                type="button"
                onClick={() => {
                  setQuick("all");
                  setSearch("");
                  setStatus("");
                  setRole("");
                }}
              >
                Clear filters
              </button>
            )}
          </div>
        ) : view === "board" ? (
          <>
            <div className="production-board" aria-label="Your tasks by status">
              {columns.map((column) => {
                const tasks = visible.filter((task) => task.status === column);
                const droppable = canDrop(column);
                return (
                  <section
                    key={column}
                    className={`production-board-column${hover === column && droppable ? " drop-target" : ""}${
                      dragging && !droppable && dragging.status !== column ? " drop-blocked" : ""
                    }`}
                    data-status={column}
                    aria-label={`${STATUS_LABELS[column]}, ${tasks.length} tasks`}
                    onDragOver={(event) => {
                      if (!droppable) return;
                      event.preventDefault();
                      setHover(column);
                    }}
                    onDragLeave={() => setHover((current) => (current === column ? null : current))}
                    onDrop={(event) => {
                      event.preventDefault();
                      const task = dragging;
                      setDragging(null);
                      setHover(null);
                      if (task && droppable) void move(task, column);
                    }}
                  >
                    <header>
                      <em className={statusTone(column)}>{STATUS_LABELS[column]}</em>
                      <span>{tasks.length}</span>
                    </header>
                    {tasks.length === 0 ? (
                      <p className="production-board-empty">No tasks</p>
                    ) : (
                      tasks.map((task) => (
                        <TaskCard
                          key={task.id}
                          code={task.code}
                          service={task.service_name}
                          title={task.title}
                          client={task.client_name}
                          priority={task.priority}
                          person={task.my_role === "MONITOR" ? task.assignee_name : "You"}
                          personTitle={
                            task.my_role === "MONITOR"
                              ? `You monitor this task · ${task.assignee_name ?? "not assigned"}`
                              : "Assigned to you"
                          }
                          dueDate={task.due_date}
                          overdue={task.is_overdue}
                          closed={CLOSED.includes(task.status)}
                          amount={task.my_commission ? money(task.my_commission, task.currency) : null}
                          files={task.files_count}
                          comments={task.comments_count}
                          dragging={dragging?.id === task.id}
                          draggable={task.allowed_statuses.length > 0}
                          onOpen={() => open(task.id)}
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
            <p className="production-muted">Drag a card to move it forward, or open it for details.</p>
          </>
        ) : (
          <div className="organization-table production-tasks" role="table">
            <div className="organization-table-head">
              <span>Task</span>
              <span>Client</span>
              <span>Role</span>
              <span>Due</span>
              <span>Status</span>
              <span className="production-money">Commission</span>
              <span>Actions</span>
            </div>
            {visible.map((task) => (
              <article key={task.id}>
                <div className="production-cell">
                  <small>
                    {task.code} · {task.service_name} · {PRIORITY_LABELS[task.priority]}
                  </small>
                  <strong>{task.title}</strong>
                </div>
                <span>{task.client_name}</span>
                <span>{task.my_role === "MONITOR" ? "Monitoring" : "Assigned"}</span>
                <span className={task.is_overdue ? "production-overdue" : undefined}>
                  {task.due_date ? formatDate(task.due_date) : "—"}
                </span>
                <em className={statusTone(task.status)}>{STATUS_LABELS[task.status]}</em>
                <span className="production-money">
                  {task.my_commission ? money(task.my_commission, task.currency) : "—"}
                </span>
                <CrudActionButtons view={{ label: `View ${task.code}`, onClick: () => open(task.id) }} />
              </article>
            ))}
          </div>
        )}
        {openId && (
          <TaskSheet label="Task" onClose={close}>
            <TaskDetail
              key={openId}
              id={openId}
              notice={notice}
              onClose={close}
              onNotice={setNotice}
              onChanged={refresh}
            />
          </TaskSheet>
        )}
      </section>
    </div>
  );
}

function TaskDetail({
  id,
  notice,
  onClose,
  onNotice,
  onChanged,
}: {
  id: string;
  notice: string;
  onClose: () => void;
  onNotice: (message: string) => void;
  onChanged: () => void;
}) {
  const [task, setTask] = useState<WorkerTaskDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setTask(await api<WorkerTaskDetail>(`/api/workspace/tasks/${id}`));
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load the task."));
    }
  }, [id]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useLiveRefresh(["task."], () => void load());

  if (error || !task) {
    return (
      <>
        <SheetHeader eyebrow="Task" title={error ? "Task not available" : "Loading…"} onClose={onClose} />
        {error ? (
          <div className="organization-state">
            <h3>{error}</h3>
            <button type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : (
          <TableSkeleton />
        )}
      </>
    );
  }

  return (
    <>
      <SheetHeader
        eyebrow={`${task.code} · ${task.service_name}`}
        title={task.title}
        onClose={onClose}
        badges={
          <>
            <em className={statusTone(task.status)}>{STATUS_LABELS[task.status]}</em>
            {task.is_overdue && <em className="overdue">Overdue</em>}
            <em>{task.my_role === "MONITOR" ? "You monitor this task" : "Assigned to you"}</em>
            <em>{PRIORITY_LABELS[task.priority]} priority</em>
          </>
        }
      />
      <StatusProgress status={task.status} />
      {notice && <div className="organization-notice">{notice}</div>}
      <Panel icon={<FileText />} eyebrow="OVERVIEW" title="Task details">
        <div className="production-panel-body">
          <dl className="production-facts">
            <div>
              <dt>Client</dt>
              <dd>{task.client_name}</dd>
            </div>
            <div>
              <dt>Due date</dt>
              <dd>{formatDate(task.due_date)}</dd>
            </div>
            {task.my_role === "MONITOR" && (
              <div>
                <dt>Assigned to</dt>
                <dd>{task.assignee_name ?? "—"}</dd>
              </div>
            )}
            <div>
              <dt>Assigned</dt>
              <dd>{formatDateTime(task.assigned_at)}</dd>
            </div>
          </dl>
          {task.description ? (
            <p className="production-description">{task.description}</p>
          ) : (
            <p className="production-muted">No description added.</p>
          )}
        </div>
      </Panel>
      {task.my_commission && (
        <Panel icon={<Wallet />} eyebrow="YOUR COMMISSION" title={money(task.my_commission, task.currency)}>
          <div className="production-panel-body">
            <p className="production-muted">Earned when the Admin approves this task.</p>
          </div>
        </Panel>
      )}
      <StatusPanel
        key={task.status}
        task={task}
        onSaved={(next, message) => {
          setTask(next);
          onNotice(message);
          onChanged();
        }}
      />
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
      <Panel icon={<History />} eyebrow="ACTIVITY" title="History">
        <div className="production-panel-body">
          <ul className="production-list">
            {[...task.status_history].reverse().map((item) => (
              <li key={item.id}>
                <div>
                  <strong>
                    {item.from_status === null
                      ? `Created as ${STATUS_LABELS[item.to_status]}`
                      : item.from_status === item.to_status
                        ? item.note || "Updated"
                        : `${STATUS_LABELS[item.from_status]} → ${STATUS_LABELS[item.to_status]}`}
                  </strong>
                  {item.note && item.from_status !== item.to_status && <p>{item.note}</p>}
                  <small>
                    {item.actor_name} · {formatDateTime(item.created_at)}
                  </small>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </Panel>
    </>
  );
}

function StatusPanel({
  task,
  onSaved,
}: {
  task: WorkerTaskDetail;
  onSaved: (task: WorkerTaskDetail, message: string) => void;
}) {
  const [target, setTarget] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setSaving(true);
    setError("");
    try {
      const result = await api<WorkerTaskDetail>(`/api/workspace/tasks/${task.id}/status`, {
        method: "POST",
        json: { status: target, note: note.trim() },
      });
      onSaved(result, `Status changed to ${STATUS_LABELS[target as TaskStatus]}.`);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to change the status."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel
      icon={<RefreshCw />}
      eyebrow="WORKFLOW"
      title={STATUS_LABELS[task.status]}
      description={
        task.my_role === "MONITOR"
          ? "As monitor you can only change the status. Only the Admin approves work."
          : "Submit your work when it is ready. Only the Admin approves it."
      }
    >
      <div className="production-panel-body">
        {error && <div className="management-form-message">{error}</div>}
        {task.allowed_statuses.length === 0 ? (
          <p className="production-muted">There is nothing for you to change at this stage.</p>
        ) : (
          <>
            <Field label="Move to">
              <LooplessSelect
                value={target}
                onValueChange={setTarget}
                ariaLabel="New status"
                options={[
                  { value: "", label: "Choose new status" },
                  ...task.allowed_statuses.map((value) => ({ value, label: STATUS_LABELS[value] })),
                ]}
              />
            </Field>
            <Field label="Note (optional)">
              <span className="management-input">
                <MessageSquare aria-hidden="true" />
                <input
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  maxLength={1000}
                  placeholder="What changed"
                />
              </span>
            </Field>
            <div className="production-inline-actions">
              <button
                type="button"
                className="management-primary-action"
                disabled={!target || saving}
                onClick={() => void submit()}
              >
                {saving && <RefreshCw className="spin" />}
                {saving ? "Saving…" : "Update status"}
              </button>
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

function FilesPanel({
  task,
  onChange,
  onNotice,
}: {
  task: WorkerTaskDetail;
  onChange: (files: TaskFile[]) => void;
  onNotice: (message: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  async function upload(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      onChange(await api<TaskFile[]>(`/api/workspace/tasks/${task.id}/files`, { method: "POST", body: form }));
      onNotice(`${file.name} uploaded.`);
    } catch (requestError) {
      setError(errorText(requestError, "Unable to upload the file."));
    } finally {
      setUploading(false);
    }
  }

  return (
    <Panel icon={<Paperclip />} eyebrow="FILES" title="References and your work">
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
                    {file.uploaded_by_name}
                  </small>
                </div>
                <a
                  className="production-icon-button"
                  href={`/api/workspace/tasks/${task.id}/files/${file.id}`}
                  aria-label={`Download ${file.file_name}`}
                  title="Download"
                >
                  <Download />
                </a>
              </li>
            ))}
          </ul>
        )}
        {task.can_upload_deliverables && (
          <div className="production-inline-actions">
            <label className={`production-upload${uploading ? " disabled" : ""}`}>
              {uploading ? <RefreshCw className="spin" /> : <Upload />}
              {uploading ? "Uploading…" : "Upload finished work"}
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
        )}
      </div>
    </Panel>
  );
}

function CommentsPanel({ task, onChange }: { task: WorkerTaskDetail; onChange: (comments: TaskComment[]) => void }) {
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
        await api<TaskComment[]>(`/api/workspace/tasks/${task.id}/comments`, {
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
      description="Seen by the Admin and the people on this task."
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
