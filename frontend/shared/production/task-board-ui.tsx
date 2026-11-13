"use client";

/*
 * Building blocks for the modern Tasks pages (Admin "Tasks" and the Manager/Employee "My Tasks"):
 * compact header, quick filter chips, richer board cards, a slide-in task sheet and a status
 * progress bar. Colours and type come from the existing theme tokens only.
 */
import { useEffect, useRef, type DragEvent, type ReactNode } from "react";
import { CalendarDays, Check, List, MessageSquare, Paperclip, Search, SquareKanban, X } from "lucide-react";
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

export function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "–"
  );
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

/** Board card: priority stripe, assignee initials, due chip, money line and file/comment counts. */
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
  return (
    <button
      type="button"
      className={`production-board-card production-task-card priority-${priority.toLowerCase()}${
        dragging ? " dragging" : ""
      }`}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onOpen}
      aria-label={`Open ${code}: ${title}`}
    >
      <span className="production-task-card-top">
        <small>
          {code} · {service}
        </small>
        <em className={`production-priority priority-${priority.toLowerCase()}`}>{PRIORITY_LABELS[priority]}</em>
      </span>
      <strong>{title}</strong>
      <span className="production-task-card-client">{client}</span>
      {amount && <span className="production-board-price">{amount}</span>}
      <footer>
        <span className="production-board-person" title={personTitle ?? person ?? "Not assigned"}>
          <b aria-hidden="true" className={person ? undefined : "empty"}>
            {person ? initials(person) : "–"}
          </b>
          <span className="name">{person ?? "Not assigned"}</span>
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
