"use client";

/*
 * Today panel on the Admin, Manager and Employee dashboards (owner request 2026-11-19): overdue
 * work, what is due today, the rest of the week, and work waiting for review, most urgent
 * first. The server decides what each person sees (the admin every task; managers and
 * employees the tasks they are assigned to or monitor). Calendar items become tasks, so they
 * show up here too.
 */
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlarmClock, CalendarCheck, CalendarRange, ClipboardCheck } from "lucide-react";
import { PanelHead } from "../dashboard/role-dashboard-ui";
import { PRIORITY_LABELS, STATUS_LABELS, api, errorText } from "../production/client";
import type { TaskPriority, TaskStatus } from "../production/types";
import { useLiveRefresh } from "../realtime/realtime";
import "../styles/task-board.css";
import "../styles/today-focus.css";

type FocusTask = {
  id: string;
  code: string;
  title: string;
  client_name: string;
  service_name: string;
  priority: TaskPriority;
  status: TaskStatus;
  due_date: string | null;
  days_left: number | null;
  assignee_name: string | null;
  monitor_name: string | null;
  my_role: "ASSIGNEE" | "MONITOR" | null;
};
type Focus = {
  today: string;
  overdue: FocusTask[];
  due_today: FocusTask[];
  this_week: FocusTask[];
  to_review: FocusTask[];
};
type Tab = "overdue" | "due_today" | "this_week" | "to_review";

const TABS: { key: Tab; label: string; icon: typeof AlarmClock; empty: string }[] = [
  { key: "overdue", label: "Overdue", icon: AlarmClock, empty: "Nothing overdue. Well done." },
  { key: "due_today", label: "Today", icon: CalendarCheck, empty: "Nothing due today." },
  { key: "this_week", label: "This week", icon: CalendarRange, empty: "Nothing due in the next 7 days." },
  { key: "to_review", label: "To review", icon: ClipboardCheck, empty: "Nothing waiting for review." },
];

function dueText(task: FocusTask): string {
  if (task.days_left === null) return "No due date";
  if (task.days_left < 0) return `${-task.days_left} ${task.days_left === -1 ? "day" : "days"} late`;
  if (task.days_left === 0) return "Due today";
  if (task.days_left === 1) return "Due tomorrow";
  const date = new Date(`${task.due_date}T00:00:00`);
  return `Due ${date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}`;
}

export function TodayFocus({ endpoint, scope }: { endpoint: string; scope: "ADMIN" | "WORKER" }) {
  const [focus, setFocus] = useState<Focus | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab | null>(null);

  const load = useCallback(async () => {
    try {
      setFocus(await api<Focus>(endpoint));
      setError("");
    } catch (reason) {
      setError(errorText(reason, "Could not load today's work."));
    }
  }, [endpoint]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  useLiveRefresh(["task."], () => void load());

  // Open on the most pressing list that has something in it.
  const active: Tab =
    tab ?? (focus ? (TABS.find((item) => focus[item.key].length > 0)?.key ?? "due_today") : "due_today");
  const items = focus ? focus[active] : [];
  const meta = TABS.find((item) => item.key === active) ?? TABS[1];

  return (
    <article className="company-dashboard-panel production-dash-panel today-focus">
      <PanelHead
        eyebrow={scope === "ADMIN" ? "ALL WORK" : "YOUR WORK"}
        title="Today's focus"
        aside={
          focus && focus.overdue.length > 0 ? (
            <span className="today-focus-alert">
              <AlarmClock aria-hidden="true" /> {focus.overdue.length} overdue
            </span>
          ) : undefined
        }
      />
      <div className="today-focus-tabs" role="tablist" aria-label="Today's focus">
        {TABS.map(({ key, label, icon: Icon }) => {
          const count = focus ? focus[key].length : 0;
          return (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={active === key}
              className={`${active === key ? "active" : ""}${key === "overdue" && count ? " late" : ""}`}
              onClick={() => setTab(key)}
            >
              <Icon aria-hidden="true" />
              {label}
              <b>{count}</b>
            </button>
          );
        })}
      </div>
      <div className="production-dash-panel-body">
        {error ? (
          <p className="today-focus-empty">{error}</p>
        ) : !focus ? (
          <p className="today-focus-empty">Loading…</p>
        ) : items.length === 0 ? (
          <p className="today-focus-empty">{meta.empty}</p>
        ) : (
          <ul className="today-focus-list">
            {items.map((task) => (
              <li key={task.id}>
                <Link href={`/tasks?task=${task.id}`} className={task.days_left !== null && task.days_left < 0 ? "late" : undefined}>
                  <span className={`production-priority priority-${task.priority.toLowerCase()}`}>
                    {PRIORITY_LABELS[task.priority]}
                  </span>
                  <span className="today-focus-main">
                    <strong>
                      <em>{task.code}</em> {task.title}
                    </strong>
                    <small>
                      {task.client_name} · {task.service_name}
                      {scope === "ADMIN" || task.my_role === "MONITOR"
                        ? ` · ${task.assignee_name ?? "Not assigned"}`
                        : ""}
                      {task.my_role === "MONITOR" ? " (you monitor)" : ""}
                    </small>
                  </span>
                  <span className="today-focus-meta">
                    <span className="today-focus-due">{dueText(task)}</span>
                    <small>{STATUS_LABELS[task.status]}</small>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}
