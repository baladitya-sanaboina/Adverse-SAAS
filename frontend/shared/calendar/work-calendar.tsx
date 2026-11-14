"use client";

/*
 * Calendar for managers and employees (owner request 2026-11-14: "a calendar in every role"):
 * their tasks by due date, the client content plan behind those tasks, and meetings from their
 * chats. Read only; work itself is changed on the Tasks page.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, ClipboardList, Clapperboard, RefreshCw, Video } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { useLiveRefresh } from "../realtime/realtime";
import { MeetingCard, localDay, meetingTime, useMeetings, type CalendarMeeting } from "./meetings";
import type { CalendarEntry } from "./content-calendar";
import "../styles/content-calendar.css";

type StaffTask = {
  id: string;
  code: string;
  title: string;
  status: string;
  due_date: string;
  client_name: string;
  my_role: "ASSIGNEE" | "MONITOR";
};

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STATUS: Record<string, string> = {
  PENDING: "Pending",
  ASSIGNED: "Assigned",
  IN_PROGRESS: "In progress",
  SUBMITTED: "Submitted",
  REVIEW: "In review",
  APPROVED: "Approved",
  COMPLETED: "Completed",
};

function iso(day: Date): string {
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

function grid(month: Date): Date[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(first);
  start.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  const end = new Date(last);
  end.setDate(last.getDate() + (6 - ((last.getDay() + 6) % 7)));
  const days: Date[] = [];
  for (const day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) days.push(new Date(day));
  return days;
}

function longDate(value: string): string {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function WorkCalendarPage() {
  const today = iso(new Date());
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selected, setSelected] = useState(today);
  const [tasks, setTasks] = useState<StaffTask[] | null>(null);
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const days = useMemo(() => grid(month), [month]);
  const start = iso(days[0]);
  const end = iso(days[days.length - 1]);
  const meetings = useMeetings(start, end);

  const load = useCallback(async () => {
    try {
      const response = await fetch(`/api/workspace/calendar?start=${start}&end=${end}`, { cache: "no-store" });
      const body = (await response.json()) as { tasks?: StaffTask[]; entries?: CalendarEntry[]; detail?: string };
      if (!response.ok)
        throw new Error(typeof body.detail === "string" ? body.detail : "Unable to load your calendar.");
      setTasks(body.tasks ?? []);
      setEntries(body.entries ?? []);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load your calendar.");
    }
  }, [start, end]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    const clock = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(clock);
    };
  }, [load]);

  useLiveRefresh(["task.", "calendar."], () => void load());

  const byDay = useMemo(() => {
    const map = new Map<string, { tasks: StaffTask[]; entries: CalendarEntry[]; meetings: CalendarMeeting[] }>();
    const slot = (key: string) => {
      if (!map.has(key)) map.set(key, { tasks: [], entries: [], meetings: [] });
      return map.get(key)!;
    };
    (tasks ?? []).forEach((task) => slot(task.due_date).tasks.push(task));
    entries.forEach((entry) => slot(entry.entry_date).entries.push(entry));
    meetings.forEach((meeting) => slot(localDay(meeting.starts_at)).meetings.push(meeting));
    return map;
  }, [tasks, entries, meetings]);

  const monthKey = iso(month).slice(0, 7);
  const inMonth = (key: string) => key.startsWith(monthKey);
  const label = month.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  const day = byDay.get(selected) ?? { tasks: [], entries: [], meetings: [] };
  const totals = {
    tasks: (tasks ?? []).filter((task) => inMonth(task.due_date)).length,
    open: (tasks ?? []).filter((task) => inMonth(task.due_date) && !["APPROVED", "COMPLETED"].includes(task.status))
      .length,
    content: entries.filter((entry) => inMonth(entry.entry_date)).length,
    meetings: meetings.filter((meeting) => inMonth(localDay(meeting.starts_at))).length,
  };

  return (
    <>
      <DashboardHero
        title=""
        highlight="Calendar"
        description="Your tasks by due date, the client content plan behind them and your meetings, in one place."
        compact
      />
      <div className="dash-content">
        <section className="cal-page" aria-live="polite">
          <div className="cal-toolbar">
            <div className="cal-month-nav">
              <button
                type="button"
                className="cal-icon-button"
                aria-label="Previous month"
                onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
              >
                <ChevronLeft />
              </button>
              <h2>{label}</h2>
              <button
                type="button"
                className="cal-icon-button"
                aria-label="Next month"
                onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
              >
                <ChevronRight />
              </button>
              <button
                type="button"
                className="cal-btn"
                onClick={() => {
                  setMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
                  setSelected(today);
                }}
              >
                Today
              </button>
            </div>
            <div className="cal-legend" aria-label="Legend">
              <span className="task">Tasks</span>
              <span className="content">Content plan</span>
              <span className="meeting">Meetings</span>
            </div>
          </div>

          <dl className="cal-totals" aria-label={`${label} summary`}>
            <div>
              <dt>Tasks due</dt>
              <dd>{totals.tasks}</dd>
            </div>
            <div>
              <dt>Still open</dt>
              <dd>{totals.open}</dd>
            </div>
            <div>
              <dt>Content planned</dt>
              <dd>{totals.content}</dd>
            </div>
            <div>
              <dt>Meetings</dt>
              <dd>{totals.meetings}</dd>
            </div>
          </dl>

          {error ? (
            <div className="cal-state" role="alert">
              <strong>{error}</strong>
              <button type="button" className="cal-btn" onClick={() => void load()}>
                <RefreshCw /> Retry
              </button>
            </div>
          ) : tasks === null ? (
            <div className="cal-state">
              <RefreshCw className="spin" /> Loading your calendar…
            </div>
          ) : (
            <div className="cal-month-layout">
              <div className="cal-grid" role="grid" aria-label={label}>
                {WEEKDAYS.map((name) => (
                  <span key={name} className="cal-weekday" role="columnheader">
                    {name}
                  </span>
                ))}
                {days.map((date) => {
                  const key = iso(date);
                  const items = byDay.get(key);
                  const count =
                    (items?.tasks.length ?? 0) + (items?.entries.length ?? 0) + (items?.meetings.length ?? 0);
                  return (
                    <div
                      key={key}
                      role="gridcell"
                      className={`cal-day${date.getMonth() !== month.getMonth() ? " outside" : ""}${key === today ? " today" : ""}${key === selected ? " selected" : ""}`}
                    >
                      <button
                        type="button"
                        className="cal-day-number"
                        aria-label={`${longDate(key)}, ${count} items`}
                        onClick={() => setSelected(key)}
                      >
                        {date.getDate()}
                        {count > 0 && <i aria-hidden="true" className="cal-day-dot" />}
                      </button>
                      <div className="cal-day-items">
                        {items?.meetings.slice(0, 2).map((meeting) => (
                          <button
                            key={meeting.id}
                            type="button"
                            className="cal-chip meeting"
                            onClick={() => setSelected(key)}
                            title={meeting.title}
                          >
                            <strong>
                              {meetingTime(meeting)} {meeting.title}
                            </strong>
                          </button>
                        ))}
                        {items?.tasks.slice(0, 2).map((task) => (
                          <button
                            key={task.id}
                            type="button"
                            className={`cal-chip task${["APPROVED", "COMPLETED"].includes(task.status) ? " edited" : ""}`}
                            onClick={() => setSelected(key)}
                            title={task.title}
                          >
                            <strong>{task.title}</strong>
                            <small>{task.code}</small>
                          </button>
                        ))}
                        {items?.entries.slice(0, 1).map((entry) => (
                          <button
                            key={entry.id}
                            type="button"
                            className={`cal-chip content${entry.no_post ? " no-post" : ""}`}
                            onClick={() => setSelected(key)}
                            title={entry.title}
                          >
                            <strong>{entry.no_post ? "No post" : entry.title}</strong>
                            <small>{entry.client.name}</small>
                          </button>
                        ))}
                        {count > 5 && (
                          <button type="button" className="cal-more" onClick={() => setSelected(key)}>
                            +{count - 5} more
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <aside className="cal-agenda" aria-label={`On ${longDate(selected)}`}>
                <header>
                  <div>
                    <span>SELECTED DAY</span>
                    <h3>{longDate(selected)}</h3>
                  </div>
                </header>
                {day.tasks.length + day.entries.length + day.meetings.length === 0 ? (
                  <p className="cal-empty">Nothing on this day.</p>
                ) : (
                  <ul>
                    {day.meetings.map((meeting) => (
                      <li key={meeting.id}>
                        <MeetingCard meeting={meeting} now={now} />
                      </li>
                    ))}
                    {day.tasks.map((task) => (
                      <li key={task.id}>
                        <article className="cal-card task">
                          <Link href={`/tasks?task=${task.id}`} className="cal-card-title">
                            <small>
                              <ClipboardList aria-hidden="true" /> {task.code} · {task.client_name}
                              {task.my_role === "MONITOR" ? " · monitoring" : ""}
                            </small>
                            <strong>{task.title}</strong>
                          </Link>
                          <div className="cal-card-foot">
                            <span
                              className={`cal-task-badge${["APPROVED", "COMPLETED"].includes(task.status) ? " done" : ""}`}
                            >
                              {STATUS[task.status] ?? task.status}
                            </span>
                            <span>Due {longDate(task.due_date)}</span>
                          </div>
                        </article>
                      </li>
                    ))}
                    {day.entries.map((entry) => (
                      <li key={entry.id}>
                        <article className="cal-card content">
                          <div className="cal-card-title static">
                            <small>
                              <Clapperboard aria-hidden="true" /> Content plan · {entry.client.name}
                            </small>
                            <strong>{entry.no_post ? "No post day" : entry.title}</strong>
                          </div>
                          {!entry.no_post && (
                            <div className="cal-card-foot">
                              {(
                                ["recorded", "script_ready", "edited", "posted_instagram", "posted_youtube"] as const
                              ).map((key) => (
                                <span key={key} className={`cal-flag${entry[key] ? " on" : ""}`}>
                                  {
                                    {
                                      recorded: "Recorded",
                                      script_ready: "Script",
                                      edited: "Edited",
                                      posted_instagram: "Insta",
                                      posted_youtube: "YouTube",
                                    }[key]
                                  }
                                </span>
                              ))}
                              {entry.reference_url && (
                                <a href={entry.reference_url} target="_blank" rel="noreferrer noopener">
                                  Reference
                                </a>
                              )}
                              {entry.script_url && (
                                <a href={entry.script_url} target="_blank" rel="noreferrer noopener">
                                  Script
                                </a>
                              )}
                            </div>
                          )}
                        </article>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="cal-agenda-hint">
                  <CalendarDays aria-hidden="true" /> <Video aria-hidden="true" /> Meetings come from your chats;
                  schedule one from a chat.
                </p>
              </aside>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
