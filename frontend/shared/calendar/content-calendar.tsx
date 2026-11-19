"use client";

/*
 * Content calendar (Phase 13, owner decision 2026-11-14). The client plans what to shoot and post
 * on which day and ticks Recorded, Script, Instagram and YouTube; "Edited" ticks itself when the
 * linked task is approved. The Admin sees every client's entries, can change anything and creates
 * the task for an entry. Used by the Admin and Client apps (the Client app has a copy).
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  ClipboardPlus,
  ExternalLink,
  FileText,
  Table2,
  Paperclip,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { useLiveRefresh } from "../realtime/realtime";
import { CalendarSheet } from "./calendar-sheet";
import { MeetingCard, localDay, meetingTime, useMeetings } from "./meetings";
import "../styles/content-calendar.css";
import { OrbitLoader } from "../branding/orbit-loader";
import { LooplessDate } from "@/components/foundation/loopless-date";

type Role = "ADMIN" | "CLIENT";
type TaskStatus =
  | "PENDING"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "SUBMITTED"
  | "REVIEW"
  | "APPROVED"
  | "COMPLETED"
  | "CANCELLED";

export type CalendarEntry = {
  id: string;
  client: { id: string; name: string; code: string };
  entry_date: string;
  title: string;
  reference_url: string;
  script_url: string;
  pdf_url: string;
  notes: string;
  no_post: boolean;
  recorded: boolean;
  script_ready: boolean;
  posted_instagram: boolean;
  posted_youtube: boolean;
  edited: boolean;
  edited_manual: boolean;
  script: { file_name: string; size_bytes: number } | null;
  task: { id: string; code: string; title: string; status: TaskStatus } | null;
  created_by_name: string;
  created_at: string;
  updated_at: string;
};

type Tick = "recorded" | "script_ready" | "edited" | "posted_instagram" | "posted_youtube";

const TICKS: { key: Tick; label: string; short: string }[] = [
  { key: "recorded", label: "Recorded", short: "R" },
  { key: "script_ready", label: "Script", short: "S" },
  { key: "edited", label: "Edited", short: "E" },
  { key: "posted_instagram", label: "Instagram", short: "I" },
  { key: "posted_youtube", label: "YouTube", short: "Y" },
];

const STATUS_TEXT: Record<TaskStatus, string> = {
  PENDING: "Pending",
  ASSIGNED: "Assigned",
  IN_PROGRESS: "In progress",
  SUBMITTED: "Submitted",
  REVIEW: "In review",
  APPROVED: "Approved",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/* ------------------------------------------------------------------ dates (local, YYYY-MM-DD) */

function iso(day: Date): string {
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

function parse(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDays(day: Date, count: number): Date {
  const next = new Date(day);
  next.setDate(next.getDate() + count);
  return next;
}

/** Monday-first grid covering the whole month. */
function monthGrid(month: Date): Date[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = addDays(first, -((first.getDay() + 6) % 7));
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  const end = addDays(last, 6 - ((last.getDay() + 6) % 7));
  const days: Date[] = [];
  for (let day = start; day <= end; day = addDays(day, 1)) days.push(day);
  return days;
}

function longDate(value: string): string {
  return parse(value).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/* ------------------------------------------------------------------ requests */

async function send<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    const detail = body.detail;
    const text =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]
          ? String((detail[0] as { msg: string }).msg).replace(/^Value error, /, "")
          : "Something went wrong. Please try again.";
    throw new Error(text);
  }
  return body as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

/* ------------------------------------------------------------------ page */

export function ContentCalendarPage({ role }: { role: Role }) {
  const base = role === "ADMIN" ? "/api/company/calendar" : "/api/client-portal/calendar";
  const today = iso(new Date());
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [view, setView] = useState<"sheet" | "month">("sheet");
  const [selectedDay, setSelectedDay] = useState(today);
  const [clientFilter, setClientFilter] = useState("");
  // Filters (owner request 2026-11-15).
  const [search, setSearch] = useState("");
  const [progress, setProgress] = useState("");
  const [videoState, setVideoState] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [clients, setClients] = useState<{ id: string; name: string }[]>([]);
  const [entries, setEntries] = useState<CalendarEntry[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<{ entry: CalendarEntry | null; date: string } | null>(null);

  const grid = useMemo(() => monthGrid(month), [month]);
  const start = iso(grid[0]);
  const end = iso(grid[grid.length - 1]);
  // Meetings from chats show on the calendar too (owner request 2026-11-14).
  const meetings = useMeetings(start, end);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const clock = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(clock);
  }, []);
  const meetingsByDay = useMemo(() => {
    const map = new Map<string, typeof meetings>();
    meetings.forEach((meeting) =>
      map.set(localDay(meeting.starts_at), [...(map.get(localDay(meeting.starts_at)) ?? []), meeting]),
    );
    return map;
  }, [meetings]);

  const load = useCallback(async () => {
    setError("");
    try {
      // The sheet shows every row like the owner's Google Sheet; the month view only its weeks.
      const params = new URLSearchParams(view === "month" ? { start, end } : {});
      if (role === "ADMIN" && clientFilter) params.set("client_id", clientFilter);
      const result = await send<{ items: CalendarEntry[] }>(`${base}?${params}`);
      setEntries(result.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the calendar.");
    }
  }, [base, start, end, clientFilter, role, view]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useLiveRefresh(["calendar.", "task."], () => void load());

  useEffect(() => {
    if (role !== "ADMIN") return;
    void send<{ items: { id: string; name: string; status: string }[] }>("/api/company/clients?page_size=100")
      .then((result) => setClients(result.items.map((item) => ({ id: item.id, name: item.name }))))
      .catch(() => setClients([]));
  }, [role]);

  // ?entry=<id> (from a notification) opens that entry once it is loaded.
  useEffect(() => {
    if (!entries) return;
    const wanted = new URLSearchParams(window.location.search).get("entry");
    if (!wanted) return;
    const found = entries.find((item) => item.id === wanted);
    if (found) {
      const timer = window.setTimeout(() => {
        setEditor({ entry: found, date: found.entry_date });
        window.history.replaceState(null, "", window.location.pathname);
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [entries]);

  const shown = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (entries ?? []).filter((entry) => {
      if (!entry.title && !entry.notes) return true; // a row just added stays visible
      if (term && ![entry.title, entry.notes, entry.client.name].some((text) => text.toLowerCase().includes(term)))
        return false;
      if (from && entry.entry_date < from) return false;
      if (to && entry.entry_date > to) return false;
      const posted = entry.posted_instagram || entry.posted_youtube;
      if (progress === "not-recorded" && (entry.no_post || entry.recorded)) return false;
      if (progress === "recorded" && !entry.recorded) return false;
      if (progress === "script" && !entry.script_ready) return false;
      if (progress === "edited" && !entry.edited) return false;
      if (progress === "posted" && !posted) return false;
      if (progress === "not-posted" && (entry.no_post || posted)) return false;
      if (progress === "no-post" && !entry.no_post) return false;
      const status = entry.task?.status;
      if (videoState === "none" && entry.task) return false;
      if (videoState === "working" && !(status && !["APPROVED", "COMPLETED", "CANCELLED"].includes(status)))
        return false;
      if (videoState === "approved" && !(status === "APPROVED" || status === "COMPLETED")) return false;
      return true;
    });
  }, [entries, search, from, to, progress, videoState]);
  const filtering = Boolean(search || from || to || progress || videoState);
  const clearFilters = () => {
    setSearch("");
    setProgress("");
    setVideoState("");
    setFrom("");
    setTo("");
  };

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEntry[]>();
    for (const entry of shown) map.set(entry.entry_date, [...(map.get(entry.entry_date) ?? []), entry]);
    return map;
  }, [shown]);

  const monthKey = iso(month).slice(0, 7);
  const inMonth = shown.filter(
    (entry) => !entry.no_post && (view === "sheet" || entry.entry_date.startsWith(monthKey)),
  );
  const totals = {
    planned: inMonth.length,
    recorded: inMonth.filter((entry) => entry.recorded).length,
    edited: inMonth.filter((entry) => entry.edited).length,
    posted: inMonth.filter((entry) => entry.posted_instagram || entry.posted_youtube).length,
  };

  async function toggle(entry: CalendarEntry, key: Tick) {
    const field = key === "edited" ? "edited_manual" : key;
    const value = key === "edited" ? !entry.edited_manual : !entry[key];
    // Optimistic: flip it now, put the saved version back when the server answers.
    setEntries((current) =>
      (current ?? []).map((item) =>
        item.id === entry.id
          ? {
              ...item,
              [field]: value,
              ...(key === "edited"
                ? { edited: value || item.task?.status === "APPROVED" || item.task?.status === "COMPLETED" }
                : {}),
            }
          : item,
      ),
    );
    try {
      const saved = await send<CalendarEntry>(`${base}/${entry.id}`, json("PATCH", { [field]: value }));
      setEntries((current) => (current ?? []).map((item) => (item.id === saved.id ? saved : item)));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Could not save that tick.");
      void load();
    }
  }

  function saved(entry: CalendarEntry, message: string) {
    setEntries((current) => {
      const list = (current ?? []).filter((item) => item.id !== entry.id);
      return [...list, entry].sort((a, b) => a.entry_date.localeCompare(b.entry_date));
    });
    setNotice(message);
  }

  function removed(id: string) {
    setEntries((current) => (current ?? []).filter((item) => item.id !== id));
    setEditor(null);
    setNotice("Entry deleted.");
  }

  const dayEntries = byDay.get(selectedDay) ?? [];
  const clientName =
    role === "ADMIN"
      ? (clients.find((item) => item.id === clientFilter)?.name ?? "All clients")
      : (entries?.[0]?.client.name ?? "My");

  async function editField(
    entry: CalendarEntry,
    field: "title" | "reference_url" | "script_url" | "pdf_url" | "notes" | "entry_date",
    value: string,
  ) {
    try {
      const saved = await send<CalendarEntry>(`${base}/${entry.id}`, json("PATCH", { [field]: value }));
      setEntries((current) => (current ?? []).map((item) => (item.id === saved.id ? saved : item)));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Could not save that cell.");
    }
  }

  async function addRow(values: { entry_date: string; title: string; no_post: boolean }): Promise<boolean> {
    try {
      const body = role === "ADMIN" ? { ...values, client_id: clientFilter } : values;
      const created = await send<CalendarEntry>(base, json("POST", body));
      saved(
        created,
        created.task ? `Row added. Ticket ${role === "ADMIN" ? created.task.code + " " : ""}created.` : "Row added.",
      );
      return true;
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Could not add the row.");
      return false;
    }
  }

  const monthLabel = month.toLocaleDateString("en-IN", { month: "long", year: "numeric" });

  return (
    <>
      <DashboardHero
        title=""
        highlight="Content Calendar"
        description={
          role === "ADMIN"
            ? "Every client's plan by date. Turn an idea into a task in one step; Edited ticks itself when you approve the video."
            : "Plan what to shoot and post on which day. Tick each step as it happens; Edited ticks itself when your video is approved."
        }
        compact
      />
      <div className="dash-content">
        <section className="cal-page" aria-live="polite">
          <div className="cal-toolbar">
            {view === "sheet" ? (
              <div className="cal-month-nav">
                <h2 className="cal-sheet-heading">{clientName} Content Calendar</h2>
              </div>
            ) : (
              <div className="cal-month-nav">
                <button
                  type="button"
                  className="cal-icon-button"
                  aria-label="Previous month"
                  onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
                >
                  <ChevronLeft />
                </button>
                <h2>{monthLabel}</h2>
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
                    const now = new Date();
                    setMonth(new Date(now.getFullYear(), now.getMonth(), 1));
                    setSelectedDay(today);
                  }}
                >
                  Today
                </button>
              </div>
            )}
            <div className="cal-toolbar-actions">
              {role === "ADMIN" && (
                <div className="cal-client-filter">
                  <LooplessSelect
                    value={clientFilter}
                    onValueChange={setClientFilter}
                    ariaLabel="Filter by client"
                    options={[
                      { value: "", label: "All clients" },
                      ...clients.map((item) => ({ value: item.id, label: item.name })),
                    ]}
                  />
                </div>
              )}
              <div className="cal-view-toggle" role="group" aria-label="View">
                <button
                  type="button"
                  className={view === "sheet" ? "active" : undefined}
                  aria-pressed={view === "sheet"}
                  onClick={() => setView("sheet")}
                >
                  <Table2 /> Sheet
                </button>
                <button
                  type="button"
                  className={view === "month" ? "active" : undefined}
                  aria-pressed={view === "month"}
                  onClick={() => setView("month")}
                >
                  <CalendarDays /> Month
                </button>
              </div>
              <button
                type="button"
                className="cal-btn primary"
                onClick={() =>
                  setEditor({ entry: null, date: selectedDay.startsWith(monthKey) ? selectedDay : iso(month) })
                }
              >
                <Plus /> Add entry
              </button>
            </div>
          </div>

          <div className="cal-filters" role="search" aria-label="Filter the calendar">
            <label className="cal-filter-search">
              <Search aria-hidden="true" />
              <input
                type="search"
                value={search}
                placeholder={role === "ADMIN" ? "Search title, notes or client" : "Search title or notes"}
                aria-label="Search the calendar"
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <LooplessSelect
              value={progress}
              onValueChange={setProgress}
              ariaLabel="Filter by progress"
              options={[
                { value: "", label: "Any progress" },
                { value: "not-recorded", label: "Not recorded yet" },
                { value: "recorded", label: "Recorded" },
                { value: "script", label: "Script ready" },
                { value: "edited", label: "Edited" },
                { value: "posted", label: "Posted" },
                { value: "not-posted", label: "Not posted yet" },
                { value: "no-post", label: "No-post days" },
              ]}
            />
            <LooplessSelect
              value={videoState}
              onValueChange={setVideoState}
              ariaLabel="Filter by video"
              options={[
                { value: "", label: "Any video status" },
                { value: "none", label: "No video yet" },
                { value: "working", label: "Video in production" },
                { value: "approved", label: "Video approved" },
              ]}
            />
            <label className="cal-filter-date">
              <span>From</span>
              <LooplessDate value={from} onValueChange={setFrom} ariaLabel="From" max={to || undefined} />
            </label>
            <label className="cal-filter-date">
              <span>To</span>
              <LooplessDate value={to} onValueChange={setTo} ariaLabel="To" min={from || undefined} />
            </label>
            {filtering && (
              <button type="button" className="cal-btn" onClick={clearFilters}>
                <X /> Clear · {shown.length} of {entries?.length ?? 0}
              </button>
            )}
          </div>

          <dl className="cal-totals" aria-label={view === "sheet" ? "Summary" : `${monthLabel} summary`}>
            <div>
              <dt>Planned</dt>
              <dd>{totals.planned}</dd>
            </div>
            <div>
              <dt>Recorded</dt>
              <dd>{totals.recorded}</dd>
            </div>
            <div>
              <dt>Edited</dt>
              <dd>{totals.edited}</dd>
            </div>
            <div>
              <dt>Posted</dt>
              <dd>{totals.posted}</dd>
            </div>
          </dl>

          {notice && (
            <div className="cal-notice" role="status">
              <span>{notice}</span>
              <button type="button" aria-label="Dismiss" onClick={() => setNotice("")}>
                <X />
              </button>
            </div>
          )}

          {error ? (
            <div className="cal-state" role="alert">
              <strong>{error}</strong>
              <button type="button" className="cal-btn" onClick={() => void load()}>
                <RefreshCw /> Retry
              </button>
            </div>
          ) : entries === null ? (
            <div className="cal-state">
              <OrbitLoader size={56} label="Loading the calendar" />
            </div>
          ) : view === "sheet" ? (
            <CalendarSheet
              role={role}
              title={`${clientName} Content Calendar`}
              entries={shown}
              showClient={role === "ADMIN" && !clientFilter}
              canAdd={role === "CLIENT" || Boolean(clientFilter)}
              onToggle={(entry, key) => void toggle(entry, key)}
              onEdit={(entry, field, value) => void editField(entry, field, value)}
              onAdd={addRow}
              onOpen={(entry) => setEditor({ entry, date: entry.entry_date })}
            />
          ) : (
            <div className="cal-month-layout">
              <div className="cal-grid" role="grid" aria-label={monthLabel}>
                {WEEKDAYS.map((name) => (
                  <span key={name} className="cal-weekday" role="columnheader">
                    {name}
                  </span>
                ))}
                {grid.map((day) => {
                  const key = iso(day);
                  const items = byDay.get(key) ?? [];
                  const outside = day.getMonth() !== month.getMonth();
                  return (
                    <div
                      key={key}
                      role="gridcell"
                      className={`cal-day${outside ? " outside" : ""}${key === today ? " today" : ""}${key === selectedDay ? " selected" : ""}`}
                    >
                      <button
                        type="button"
                        className="cal-day-number"
                        aria-label={`${longDate(key)}, ${items.length} entries`}
                        onClick={() => setSelectedDay(key)}
                      >
                        {day.getDate()}
                        {(items.length > 0 || meetingsByDay.has(key)) && (
                          <i aria-hidden="true" className="cal-day-dot" />
                        )}
                      </button>
                      <div className="cal-day-items">
                        {(meetingsByDay.get(key) ?? []).slice(0, 1).map((meeting) => (
                          <button
                            key={meeting.id}
                            type="button"
                            className="cal-chip meeting"
                            onClick={() => setSelectedDay(key)}
                            title={meeting.title}
                          >
                            <strong>
                              {meetingTime(meeting)} {meeting.title}
                            </strong>
                          </button>
                        ))}
                        {items.slice(0, 3).map((entry) => (
                          <button
                            key={entry.id}
                            type="button"
                            className={`cal-chip${entry.no_post ? " no-post" : ""}${entry.edited ? " edited" : ""}`}
                            onClick={() => {
                              setSelectedDay(key);
                              setEditor({ entry, date: key });
                            }}
                            title={entry.title}
                          >
                            <strong>{entry.no_post ? "No post" : entry.title}</strong>
                            {role === "ADMIN" && <small>{entry.client.name}</small>}
                            {!entry.no_post && (
                              <span className="cal-chip-ticks" aria-hidden="true">
                                {TICKS.map((tick) => (
                                  <i key={tick.key} className={entry[tick.key] ? "on" : undefined} />
                                ))}
                              </span>
                            )}
                          </button>
                        ))}
                        {items.length > 3 && (
                          <button type="button" className="cal-more" onClick={() => setSelectedDay(key)}>
                            +{items.length - 3} more
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <aside className="cal-agenda" aria-label={`Entries on ${longDate(selectedDay)}`}>
                <header>
                  <div>
                    <span>SELECTED DAY</span>
                    <h3>{longDate(selectedDay)}</h3>
                  </div>
                  <button
                    type="button"
                    className="cal-icon-button"
                    aria-label="Add an entry on this day"
                    onClick={() => setEditor({ entry: null, date: selectedDay })}
                  >
                    <Plus />
                  </button>
                </header>
                {(meetingsByDay.get(selectedDay) ?? []).length > 0 && (
                  <ul>
                    {(meetingsByDay.get(selectedDay) ?? []).map((meeting) => (
                      <li key={meeting.id}>
                        <MeetingCard meeting={meeting} now={now} />
                      </li>
                    ))}
                  </ul>
                )}
                {dayEntries.length === 0 ? (
                  <p className="cal-empty">Nothing planned. Add an idea for this day.</p>
                ) : (
                  <ul>
                    {dayEntries.map((entry) => (
                      <li key={entry.id}>
                        <EntryCard
                          entry={entry}
                          role={role}
                          onOpen={() => setEditor({ entry, date: entry.entry_date })}
                          onToggle={(key) => void toggle(entry, key)}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </aside>
            </div>
          )}
        </section>
      </div>

      {editor && (
        <EntryDialog
          role={role}
          base={base}
          entry={editor.entry}
          date={editor.date}
          clients={clients}
          defaultClient={clientFilter}
          onClose={() => setEditor(null)}
          onSaved={(entry, message) => {
            saved(entry, message);
            setEditor({ entry, date: entry.entry_date });
          }}
          onCreated={(entry) => {
            saved(entry, "Entry added.");
            setSelectedDay(entry.entry_date);
            setEditor(null);
          }}
          onDeleted={removed}
        />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ pieces */

function TickBox({
  entry,
  tick,
  label,
  role,
  onToggle,
}: {
  entry: CalendarEntry;
  tick: Tick;
  label: string;
  role: Role;
  onToggle: () => void;
}) {
  const automatic = tick === "edited" && role === "CLIENT";
  const checked = entry[tick];
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={`${label}: ${entry.title}`}
      title={automatic ? "Ticks itself when your video is approved" : label}
      className={`cal-tick${checked ? " on" : ""}${automatic ? " auto" : ""}`}
      disabled={automatic}
      onClick={onToggle}
    >
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3.5 8.5l3 3 6-7" />
      </svg>
    </button>
  );
}

function TaskBadge({ task, role }: { task: NonNullable<CalendarEntry["task"]>; role: Role }) {
  const done = task.status === "APPROVED" || task.status === "COMPLETED";
  const body = (
    <>
      {role === "ADMIN" ? `${task.code} · ` : ""}
      {done ? "Edited" : STATUS_TEXT[task.status]}
    </>
  );
  const className = `cal-task-badge${done ? " done" : task.status === "CANCELLED" ? " cancelled" : ""}`;
  return role === "ADMIN" ? (
    <Link href={`/tasks?task=${task.id}`} className={className}>
      {body}
    </Link>
  ) : (
    <span className={className}>
      {task.status === "PENDING" ? "Ticket raised" : task.status === "ASSIGNED" ? "In production" : body}
    </span>
  );
}

function createTaskHref(entry: CalendarEntry): string {
  const notes = [entry.notes, entry.reference_url ? `Reference: ${entry.reference_url}` : ""]
    .filter(Boolean)
    .join("\n\n");
  const params = new URLSearchParams({
    mode: "create",
    client: entry.client.id,
    title: entry.title,
    description: notes,
    due: entry.entry_date,
    calendar: entry.id,
  });
  return `/tasks?${params}`;
}

function CreateTaskLink({ entry }: { entry: CalendarEntry }) {
  return (
    <Link href={createTaskHref(entry)} className="cal-create-task">
      <ClipboardPlus /> Create task
    </Link>
  );
}

function EntryCard({
  entry,
  role,
  onOpen,
  onToggle,
}: {
  entry: CalendarEntry;
  role: Role;
  onOpen: () => void;
  onToggle: (key: Tick) => void;
}) {
  return (
    <article className={`cal-card${entry.no_post ? " no-post" : ""}`}>
      <button type="button" className="cal-card-title" onClick={onOpen}>
        {role === "ADMIN" && <small>{entry.client.name}</small>}
        <strong>{entry.no_post ? "No post day" : entry.title}</strong>
      </button>
      {!entry.no_post && (
        <div className="cal-card-ticks">
          {TICKS.map((tick) => (
            <label key={tick.key} className="cal-card-tick">
              <TickBox
                entry={entry}
                tick={tick.key}
                label={tick.label}
                role={role}
                onToggle={() => onToggle(tick.key)}
              />
              <span>{tick.label}</span>
            </label>
          ))}
        </div>
      )}
      <div className="cal-card-foot">
        {entry.reference_url && (
          <a href={entry.reference_url} target="_blank" rel="noreferrer noopener">
            <ExternalLink /> Reference
          </a>
        )}
        {entry.script_url && (
          <a href={entry.script_url} target="_blank" rel="noreferrer noopener">
            <Paperclip /> Script
          </a>
        )}
        {entry.pdf_url && (
          <a href={entry.pdf_url} target="_blank" rel="noreferrer noopener">
            <FileText /> PDF
          </a>
        )}
        {entry.task ? (
          <TaskBadge task={entry.task} role={role} />
        ) : role === "ADMIN" && !entry.no_post ? (
          <CreateTaskLink entry={entry} />
        ) : null}
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ add / edit dialog */

function EntryDialog({
  role,
  base,
  entry,
  date,
  clients,
  defaultClient,
  onClose,
  onSaved,
  onCreated,
  onDeleted,
}: {
  role: Role;
  base: string;
  entry: CalendarEntry | null;
  date: string;
  clients: { id: string; name: string }[];
  defaultClient: string;
  onClose: () => void;
  onSaved: (entry: CalendarEntry, message: string) => void;
  onCreated: (entry: CalendarEntry) => void;
  onDeleted: (id: string) => void;
}) {
  const [form, setForm] = useState({
    client_id: entry?.client.id ?? defaultClient,
    entry_date: entry?.entry_date ?? date,
    title: entry?.title ?? "",
    reference_url: entry?.reference_url ?? "",
    script_url: entry?.script_url ?? "",
    pdf_url: entry?.pdf_url ?? "",
    notes: entry?.notes ?? "",
    no_post: entry?.no_post ?? false,
    priority: "",
  });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  // Once the agency starts the video, the client can no longer move or rename it (links,
  // notes and ticks stay editable). Before that, a change also updates the ticket.
  const locked =
    role === "CLIENT" && entry?.task != null && !["PENDING", "ASSIGNED", "CANCELLED"].includes(entry.task.status);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    if (role === "ADMIN" && !entry && !form.client_id) return setMessage("Choose the client.");
    if (!form.no_post && !form.title.trim()) return setMessage("Give the video a title.");
    setBusy(true);
    try {
      const payload = {
        entry_date: form.entry_date,
        title: form.title.trim() || "No post",
        reference_url: form.reference_url.trim(),
        script_url: form.script_url.trim(),
        pdf_url: form.pdf_url.trim(),
        notes: form.notes,
        no_post: form.no_post,
      };
      if (entry) {
        onSaved(await send<CalendarEntry>(`${base}/${entry.id}`, json("PATCH", payload)), "Entry saved.");
      } else {
        onCreated(
          await send<CalendarEntry>(
            base,
            json("POST", {
              ...payload,
              ...(role === "ADMIN" ? { client_id: form.client_id } : {}),
              ...(form.priority && !form.no_post ? { priority: form.priority } : {}),
            }),
          ),
        );
      }
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not save the entry.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!entry) return;
    setBusy(true);
    try {
      await send<void>(`${base}/${entry.id}`, { method: "DELETE" });
      onDeleted(entry.id);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not delete the entry.");
      setConfirmDelete(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="cal-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}
    >
      <section className="cal-dialog" role="dialog" aria-modal="true" aria-labelledby="cal-dialog-title">
        <header>
          <div>
            <span>{entry ? (role === "ADMIN" ? entry.client.name.toUpperCase() : "CALENDAR ENTRY") : "NEW ENTRY"}</span>
            <h2 id="cal-dialog-title">{entry ? (entry.no_post ? "No post day" : entry.title) : "Plan a video"}</h2>
            {entry && <p>Added by {entry.created_by_name}</p>}
          </div>
          <button type="button" className="cal-icon-button" aria-label="Close" onClick={onClose} disabled={busy}>
            <X />
          </button>
        </header>

        <form onSubmit={submit} noValidate className="cal-form">
          {message && (
            <div className="cal-form-message" role="alert">
              {message}
            </div>
          )}
          {locked && (
            <p className="cal-form-hint">Your agency is working on this video, so its date and title are fixed.</p>
          )}
          {role === "ADMIN" && !entry && (
            <label className="cal-field wide">
              <span>Client</span>
              <LooplessSelect
                value={form.client_id}
                onValueChange={(value) => setForm((current) => ({ ...current, client_id: value }))}
                ariaLabel="Client"
                options={[
                  { value: "", label: "Choose a client" },
                  ...clients.map((item) => ({ value: item.id, label: item.name })),
                ]}
              />
            </label>
          )}
          <label className="cal-field">
            <span>Date</span>
            <LooplessDate
              value={form.entry_date}
              onValueChange={(value) => setForm((current) => ({ ...current, entry_date: value }))}
              ariaLabel="Date"
              disabled={locked}
              clearable={false}
            />
          </label>
          <div className="cal-field">
            <span>Day type</span>
            <button
              type="button"
              role="switch"
              aria-checked={form.no_post}
              className={`cal-switch${form.no_post ? " on" : ""}`}
              disabled={locked}
              onClick={() => setForm((current) => ({ ...current, no_post: !current.no_post }))}
            >
              <i aria-hidden="true" /> {form.no_post ? "No post on this day" : "Post on this day"}
            </button>
          </div>
          {!form.no_post && (
            <>
              <label className="cal-field wide">
                <span>Title</span>
                <input
                  value={form.title}
                  maxLength={200}
                  disabled={locked}
                  placeholder="e.g. Diwali offer reel"
                  onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                />
              </label>
              {!entry && (
                <div className="cal-field wide">
                  <span>Priority</span>
                  <LooplessSelect
                    value={form.priority}
                    ariaLabel="Priority"
                    onValueChange={(value) => setForm((current) => ({ ...current, priority: value }))}
                    options={[
                      { value: "", label: "Automatic (by how soon the date is)" },
                      { value: "LOW", label: "Low" },
                      { value: "MEDIUM", label: "Medium" },
                      { value: "HIGH", label: "High" },
                      { value: "URGENT", label: "Urgent" },
                    ]}
                  />
                </div>
              )}
              <label className="cal-field wide">
                <span>Reference link</span>
                <input
                  type="url"
                  value={form.reference_url}
                  maxLength={1000}
                  placeholder="https://instagram.com/reel/…"
                  onChange={(event) => setForm((current) => ({ ...current, reference_url: event.target.value }))}
                />
              </label>
            </>
          )}
          {!form.no_post && (
            <>
              <label className="cal-field">
                <span>Script link</span>
                <input
                  type="url"
                  value={form.script_url}
                  maxLength={1000}
                  placeholder="https://docs.google.com/…"
                  onChange={(event) => setForm((current) => ({ ...current, script_url: event.target.value }))}
                />
              </label>
              <label className="cal-field">
                <span>PDF link</span>
                <input
                  type="url"
                  value={form.pdf_url}
                  maxLength={1000}
                  placeholder="https://drive.google.com/…"
                  onChange={(event) => setForm((current) => ({ ...current, pdf_url: event.target.value }))}
                />
              </label>
            </>
          )}
          <label className="cal-field wide">
            <span>Notes</span>
            <textarea
              rows={3}
              value={form.notes}
              maxLength={2000}
              placeholder="Idea, script points, location, outfit…"
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
            />
          </label>

          {entry && !entry.no_post && (
            <div className="cal-field wide">
              <span>Video</span>
              <div className="cal-dialog-task">
                {entry.task ? (
                  <TaskBadge task={entry.task} role={role} />
                ) : role === "ADMIN" ? (
                  <CreateTaskLink entry={entry} />
                ) : (
                  <span className="cal-muted">Not started yet</span>
                )}
                {entry.reference_url && (
                  <a href={entry.reference_url} target="_blank" rel="noreferrer noopener" className="cal-ref">
                    <ExternalLink /> Open reference
                  </a>
                )}
              </div>
            </div>
          )}

          <footer>
            {entry && !locked && (
              <button type="button" className="cal-delete" disabled={busy} onClick={() => setConfirmDelete(true)}>
                <Trash2 /> Delete
              </button>
            )}
            <span className="cal-footer-space" />
            <button type="button" className="cal-btn" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="cal-btn primary" disabled={busy}>
              {busy ? <RefreshCw className="spin" /> : null}
              {entry ? "Save" : "Add entry"}
            </button>
          </footer>
        </form>
      </section>
      <ConfirmationDialog
        open={confirmDelete}
        title="Delete this entry?"
        description={
          role === "CLIENT"
            ? "It is removed from your calendar and its ticket is cancelled."
            : "It is removed from the calendar. Its ticket stays in Tasks."
        }
        confirmLabel="Delete entry"
        tone="danger"
        loading={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => void remove()}
      />
    </div>
  );
}
