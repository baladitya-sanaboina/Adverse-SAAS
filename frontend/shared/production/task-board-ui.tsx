"use client";

/*
 * Building blocks for the modern Tasks pages (Admin "Tasks" and the Manager/Employee "My Tasks"):
 * compact header, quick filter chips, richer board cards, a slide-in task sheet and a status
 * progress bar. Colours and type come from the existing theme tokens only.
 */
import { useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from "react";
import {
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  List,
  MessageSquare,
  Paperclip,
  Search,
  SquareKanban,
  X,
} from "lucide-react";
import { PRIORITY_LABELS, STATUS_LABELS } from "./client";
import type { TaskPriority, TaskStatus } from "./types";
import "../styles/task-board.css";

export type TaskView = "board" | "list";
export type QuickFilter = "all" | "overdue" | "week" | "review" | "unassigned";

const CLOSED: TaskStatus[] = ["APPROVED", "COMPLETED", "CANCELLED"];
const IN_REVIEW: TaskStatus[] = ["SUBMITTED", "REVIEW"];

type Filterable = { status: TaskStatus; due_date: string | null; is_overdue: boolean; unassigned?: boolean };

function localDay(offset = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** True when a task belongs to a quick filter. "Due this week" means today and the next six days. */
export function matchesQuick(task: Filterable, filter: QuickFilter): boolean {
  switch (filter) {
    case "overdue":
      return task.is_overdue;
    case "week":
      return (
        !CLOSED.includes(task.status) &&
        !task.is_overdue &&
        task.due_date !== null &&
        task.due_date >= localDay() &&
        task.due_date <= localDay(6)
      );
    case "review":
      return IN_REVIEW.includes(task.status);
    case "unassigned":
      return Boolean(task.unassigned) && task.status !== "CANCELLED";
    default:
      return true;
  }
}

/** Header line such as "12 open · 2 overdue · 3 to review". */
export function taskSummary(tasks: Filterable[], reviewLabel = "to review"): string {
  const open = tasks.filter((task) => !CLOSED.includes(task.status)).length;
  const overdue = tasks.filter((task) => task.is_overdue).length;
  const review = tasks.filter((task) => IN_REVIEW.includes(task.status)).length;
  return `${open} open · ${overdue} overdue · ${review} ${reviewLabel}`;
}

/** The first letter of a name, shown when there is no photo (owner request 2026-11-28). */
export function initials(name: string): string {
  return name.trim().charAt(0).toUpperCase() || "–";
}

function shortDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  }).format(date);
}

/** Compact page header: title, live counts, search, Board/List switch and an optional main action. */
export function TasksHeader({
  title,
  summary,
  search,
  onSearch,
  searchPlaceholder,
  view,
  onView,
  action,
}: {
  title: string;
  summary: string;
  search: string;
  onSearch: (value: string) => void;
  searchPlaceholder: string;
  view: TaskView;
  onView: (view: TaskView) => void;
  action?: ReactNode;
}) {
  return (
    <header className="production-dash-header production-tasks-header">
      <div>
        <h1>{title}</h1>
        <p aria-live="polite">{summary}</p>
      </div>
      <div className="production-dash-actions">
        <label className="production-task-search">
          <Search aria-hidden="true" />
          <input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
          />
        </label>
        <div className="production-view-toggle" role="group" aria-label="Task view">
          <button
            type="button"
            className={view === "board" ? "active" : ""}
            aria-pressed={view === "board"}
            onClick={() => onView("board")}
          >
            <SquareKanban aria-hidden="true" /> Board
          </button>
          <button
            type="button"
            className={view === "list" ? "active" : ""}
            aria-pressed={view === "list"}
            onClick={() => onView("list")}
          >
            <List aria-hidden="true" /> List
          </button>
        </div>
        {action}
      </div>
    </header>
  );
}

/** Row of one-click filters with live counts, followed by the detailed dropdown filters. */
export function QuickFilters({
  chips,
  value,
  onChange,
  children,
}: {
  chips: { key: QuickFilter; label: string; count: number }[];
  value: QuickFilter;
  onChange: (value: QuickFilter) => void;
  children?: ReactNode;
}) {
  return (
    <div className="production-task-filters">
      <div className="production-chips" role="group" aria-label="Quick filters">
        {chips.map((chip) => (
          <button
            type="button"
            key={chip.key}
            className={`production-chip${value === chip.key ? " active" : ""}${
              chip.key === "overdue" && chip.count > 0 ? " alert" : ""
            }`}
            aria-pressed={value === chip.key}
            onClick={() => onChange(chip.key)}
          >
            {chip.label}
            <b>{chip.count}</b>
          </button>
        ))}
      </div>
      {children && <div className="production-task-selects">{children}</div>}
    </div>
  );
}

/** Board card: code (with Urgent/High flag), amount, title, client, assignee, counts and due date. */
export function TaskCard({
  code,
  service,
  title,
  client,
  priority,
  person,
  personTitle,
  dueDate,
  overdue,
  closed,
  amount,
  files,
  comments,
  dragging,
  draggable,
  onOpen,
  onDragStart,
  onDragEnd,
}: {
  code: string;
  service: string;
  title: string;
  client: string;
  priority: TaskPriority;
  person: string | null;
  personTitle?: string;
  dueDate: string | null;
  overdue: boolean;
  closed: boolean;
  amount?: string | null;
  files: number;
  comments: number;
  dragging: boolean;
  draggable: boolean;
  onOpen: () => void;
  onDragStart: (event: DragEvent<HTMLButtonElement>) => void;
  onDragEnd: () => void;
}) {
  const flagged = priority === "URGENT" || priority === "HIGH";
  return (
    <button
      type="button"
      className={`production-board-card production-task-card${dragging ? " dragging" : ""}`}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onOpen}
      aria-label={`Open ${code}: ${title}, ${PRIORITY_LABELS[priority]} priority`}
    >
      <span className="production-task-card-top">
        <small>
          {code}
          {flagged && (
            <em className={`production-priority priority-${priority.toLowerCase()}`}>{PRIORITY_LABELS[priority]}</em>
          )}
        </small>
        {amount && <span className="production-task-card-amount">{amount}</span>}
      </span>
      <strong>{title}</strong>
      <span className="production-task-card-client">
        {client} · {service}
      </span>
      <footer>
        <span className="production-board-person" title={personTitle ?? person ?? "Not assigned"}>
          <b aria-hidden="true" className={person ? undefined : "empty"}>
            {person ? initials(person) : ""}
          </b>
          <span className="name">{person ?? "Unassigned"}</span>
        </span>
        <span className="production-task-card-meta">
          {files > 0 && (
            <span title={`${files} ${files === 1 ? "file" : "files"}`}>
              <Paperclip aria-hidden="true" />
              {files}
            </span>
          )}
          {comments > 0 && (
            <span title={`${comments} ${comments === 1 ? "comment" : "comments"}`}>
              <MessageSquare aria-hidden="true" />
              {comments}
            </span>
          )}
          {dueDate && (
            <span
              className={`production-due${overdue ? " overdue" : ""}${closed ? " closed" : ""}`}
              title={overdue ? "Overdue" : "Due date"}
            >
              <CalendarDays aria-hidden="true" />
              {shortDate(dueDate)}
            </span>
          )}
        </span>
      </footer>
    </button>
  );
}

/**
 * Panel that slides in from the right over the board. Escape, the close button or a click on
 * the dimmed area closes it. Escape is ignored while a confirmation dialog is open over it.
 */
export function TaskSheet({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  const panel = useRef<HTMLElement>(null);
  const close = useRef(onClose);

  useEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panel.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest(".loopless-select") || document.querySelector(".confirm-dialog-backdrop")) return;
      close.current();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);

  return (
    <div className="production-sheet-layer">
      <div className="production-sheet-backdrop" aria-hidden="true" onClick={() => close.current()} />
      <aside className="production-sheet" role="dialog" aria-modal="true" aria-label={label} tabIndex={-1} ref={panel}>
        {children}
      </aside>
    </div>
  );
}

/** Sticky top of the sheet: eyebrow, title, badges, extra actions and the close button. */
export function SheetHeader({
  eyebrow,
  title,
  badges,
  actions,
  onClose,
}: {
  eyebrow: string;
  title: string;
  badges?: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
}) {
  return (
    <header className="production-sheet-head">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
        {badges && <div className="production-detail-head">{badges}</div>}
      </div>
      <div className="production-sheet-tools">
        {actions}
        <button type="button" className="production-sheet-close" onClick={onClose} aria-label="Close task panel">
          <X aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}

const STEPS: TaskStatus[] = ["ASSIGNED", "IN_PROGRESS", "SUBMITTED", "REVIEW", "APPROVED", "COMPLETED"];

/** Assigned → In Progress → Submitted → Review → Approved → Completed, with the current step marked. */
export function StatusProgress({ status }: { status: TaskStatus }) {
  const index = STEPS.indexOf(status);
  const cancelled = status === "CANCELLED";
  return (
    <div className={`production-progress${cancelled ? " cancelled" : ""}`}>
      <ol aria-label={`Progress: ${STATUS_LABELS[status]}`}>
        {STEPS.map((step, position) => {
          const done = position < index || status === "COMPLETED";
          const current = position === index && status !== "COMPLETED";
          return (
            <li
              key={step}
              className={done ? "done" : current ? "current" : undefined}
              aria-current={position === index ? "step" : undefined}
            >
              <b aria-hidden="true">{done ? <Check /> : position + 1}</b>
              <span>{STATUS_LABELS[step]}</span>
            </li>
          );
        })}
      </ol>
      {(cancelled || status === "PENDING") && (
        <p>{cancelled ? "This task was cancelled." : "Not assigned yet. Assign someone to start the work."}</p>
      )}
    </div>
  );
}

/* Board columns fold by due date (owner request 2026-11-28): this week by day, the rest of this
   month by week, other months by month, then tasks with no due date. Today's group starts open;
   click a group to open or close it. Approved and completed columns list the newest first. */
type DueGroup<T> = { key: string; sort: string; label: string; today: boolean; tasks: T[] };

const pad2 = (value: number) => String(value).padStart(2, "0");
const isoDate = (date: Date) => `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
const dateOf = (value: string) => {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day);
};
const mondayOf = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate() - ((date.getDay() + 6) % 7));
const dueText = (options: Intl.DateTimeFormatOptions, value: Date) =>
  new Intl.DateTimeFormat("en-IN", options).format(value);

export function groupByDue<T extends { due_date: string | null }>(tasks: T[], today: string): DueGroup<T>[] {
  const weekStart = isoDate(mondayOf(dateOf(today)));
  const weekEnd = isoDate(
    new Date(dateOf(weekStart).getFullYear(), dateOf(weekStart).getMonth(), dateOf(weekStart).getDate() + 6),
  );
  const groups = new Map<string, DueGroup<T>>();
  for (const task of tasks) {
    const due = task.due_date?.slice(0, 10) ?? null;
    let group: Omit<DueGroup<T>, "tasks">;
    if (!due) {
      group = { key: "none", sort: "9999", label: "No due date", today: false };
    } else if (due >= weekStart && due <= weekEnd) {
      const day = dueText({ weekday: "short", day: "numeric", month: "short" }, dateOf(due));
      group = { key: `day-${due}`, sort: due, label: due === today ? `Today · ${day}` : day, today: due === today };
    } else if (due.slice(0, 7) === today.slice(0, 7)) {
      const monday = mondayOf(dateOf(due));
      group = {
        key: `week-${isoDate(monday)}`,
        sort: isoDate(monday),
        label: `Week of ${dueText({ day: "numeric", month: "short" }, monday)}`,
        today: false,
      };
    } else {
      group = {
        key: `month-${due.slice(0, 7)}`,
        sort: `${due.slice(0, 7)}-01`,
        label: dueText({ month: "long", year: "numeric" }, dateOf(due)),
        today: false,
      };
    }
    const entry = groups.get(group.key) ?? { ...group, tasks: [] };
    entry.tasks.push(task);
    groups.set(group.key, entry);
  }
  return [...groups.values()].sort((a, b) => a.sort.localeCompare(b.sort));
}

export function BoardColumnGroups<T extends { id: string; due_date: string | null }>({
  tasks,
  newestFirst = false,
  render,
}: {
  tasks: T[];
  newestFirst?: boolean;
  render: (task: T) => ReactNode;
}) {
  const [today] = useState(() => isoDate(new Date()));
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const groups = useMemo(() => {
    const list = groupByDue(tasks, today);
    if (!newestFirst) return list;
    const dated = list.filter((group) => group.key !== "none").reverse();
    return [...dated, ...list.filter((group) => group.key === "none")];
  }, [tasks, today, newestFirst]);
  // A small column needs no folding; otherwise today's group (else the first) starts open.
  const openByDefault = tasks.length <= 4 ? null : (groups.find((group) => group.today)?.key ?? groups[0]?.key ?? null);
  return (
    <>
      {groups.map((group) => {
        const open = toggled[group.key] ?? (openByDefault === null || group.key === openByDefault);
        return (
          <div key={group.key} className={`production-board-group${group.today ? " today" : ""}`}>
            <button
              type="button"
              className="production-board-group-head"
              aria-expanded={open}
              onClick={() => setToggled((current) => ({ ...current, [group.key]: !open }))}
            >
              {open ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
              <span>{group.label}</span>
              <b>{group.tasks.length}</b>
            </button>
            {open && group.tasks.map(render)}
          </div>
        );
      })}
    </>
  );
}
