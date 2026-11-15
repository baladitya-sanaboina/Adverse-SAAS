"use client";

/*
 * Calendar (owner request 2026-11-15) for the admin, managers and employees, next to (not
 * instead of) the Content / Work calendars. Month, Week, Day and List views of events, meetings
 * planned in chats, task deadlines and todos. Who sees whose calendar is decided by the server:
 * the admin everyone, a manager self and team, an employee self.
 *
 * Events invite people by internal mail (they answer Yes / No / Maybe here). A video event holds
 * its call in a chat; Join opens the call from the calendar. Alerts come 10 minutes before and at
 * the start. "Email people" opens Mail with them filled in.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  CalendarDays,
  CalendarPlus,
  Check,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock3,
  ExternalLink,
  Mail,
  MapPin,
  MessageSquare,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  UsersRound,
  Video,
  X,
} from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { subscribeRealtime } from "../realtime/realtime";
import { startCall } from "../chat/call-manager";
import { OrbitLoader } from "../branding/orbit-loader";
import { openMail } from "../mail/mail-types";
import "../styles/agenda.css";

type Role = "ADMIN" | "MANAGER" | "EMPLOYEE";
type Person = { id: string; name: string; role: string; image?: string | null };
type Answer = "PENDING" | "YES" | "NO" | "MAYBE";
type AgendaEvent = {
  id: string;
  title: string;
  notes: string;
  location: string;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  colour: string;
  video: boolean;
  conversation_id: string | null;
  mail_thread_id: string | null;
  owner: Person;
  attendees: { person: Person; response: Answer }[];
  my_response: Answer | null;
  can_edit: boolean;
};
type Meeting = { id: string; conversation_id: string; title: string; starts_at: string; ends_at: string; kind: string; room: string };
type TaskDue = { id: string; code: string; title: string; due_date: string; status: string; assignee: string | null; client: string | null };
type Todo = {
  id: string;
  title: string;
  notes: string;
  due_date: string | null;
  due_at: string | null;
  priority: "LOW" | "NORMAL" | "HIGH";
  done: boolean;
  owner: Person;
  mine: boolean;
};
type Feed = { events: AgendaEvent[]; meetings: Meeting[]; tasks: TaskDue[]; todos: Todo[]; people: Person[]; scope: Scope; role: Role };
type Scope = "mine" | "team" | "all";
type View = "month" | "week" | "day" | "list";
type Kind = "event" | "meeting" | "task" | "todo";
type Item = {
  key: string;
  kind: Kind;
  title: string;
  start: Date;
  end: Date;
  allDay: boolean;
  colour: string;
  done?: boolean;
  sub?: string;
  event?: AgendaEvent;
  meeting?: Meeting;
  task?: TaskDue;
  todo?: Todo;
};
type Draft = {
  id: string | null;
  title: string;
  day: string;
  start: string;
  end: string;
  allDay: boolean;
  video: boolean;
  location: string;
  notes: string;
  colour: string;
  attendees: Person[];
};

const COLOURS: Record<string, string> = {
  blue: "#0876ed",
  green: "#23885a",
  red: "#d93a4a",
  purple: "#8a5cf6",
  amber: "#d97706",
  teal: "#0e9f9a",
  pink: "#db2777",
  grey: "#6b7280",
};
const KIND_COLOUR: Record<Exclude<Kind, "event">, string> = { meeting: "teal", task: "amber", todo: "purple" };
const KIND_LABEL: Record<Kind, string> = { event: "Events", meeting: "Chat meetings", task: "Task deadlines", todo: "Todos" };
const ANSWER_LABEL: Record<Answer, string> = { PENDING: "Not answered", YES: "Going", NO: "Not going", MAYBE: "Maybe" };
const HOUR_PX = 52;
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// -- dates ---------------------------------------------------------------------------------------
function utc(value: string): Date {
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
}
function localDate(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function dayStart(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}
function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}
function weekStart(date: Date): Date {
  const start = dayStart(date);
  return addDays(start, -((start.getDay() + 6) % 7));
}
function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
function iso(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function hhmm(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
function timeLabel(date: Date): string {
  return date.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}
function range(view: View, cursor: Date): [Date, Date] {
  if (view === "day") return [dayStart(cursor), addDays(dayStart(cursor), 1)];
  if (view === "week") return [weekStart(cursor), addDays(weekStart(cursor), 7)];
  if (view === "list") return [dayStart(cursor), addDays(dayStart(cursor), 30)];
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const start = weekStart(first);
  return [start, addDays(start, 42)];
}
function heading(view: View, cursor: Date): string {
  if (view === "day") return cursor.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  if (view === "week") {
    const [start] = range("week", cursor);
    const end = addDays(start, 6);
    const sameMonth = start.getMonth() === end.getMonth();
    return `${start.toLocaleDateString("en-IN", { day: "numeric", month: sameMonth ? undefined : "short" })} – ${end.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`;
  }
  if (view === "list") return `Next 30 days from ${cursor.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`;
  return cursor.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/agenda${path}`, { cache: "no-store", ...init });
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]
          ? String((detail[0] as { msg: string }).msg)
          : "That did not work. Please try again.",
    );
  }
  return body as T;
}
function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

function toItems(feed: Feed | null, show: Record<Kind, boolean>): Item[] {
  if (!feed) return [];
  const out: Item[] = [];
  if (show.event)
    for (const event of feed.events) {
      out.push({
        key: `e${event.id}`,
        kind: "event",
        title: event.title,
        start: utc(event.starts_at),
        end: utc(event.ends_at),
        allDay: event.all_day,
        colour: event.colour,
        sub: event.location || (event.video ? "Video call" : ""),
        event,
      });
    }
  if (show.meeting)
    for (const meeting of feed.meetings) {
      out.push({
        key: `m${meeting.id}`,
        kind: "meeting",
        title: meeting.title,
        start: utc(meeting.starts_at),
        end: utc(meeting.ends_at),
        allDay: false,
        colour: KIND_COLOUR.meeting,
        sub: meeting.room,
        meeting,
      });
    }
  if (show.task)
    for (const task of feed.tasks) {
      const day = localDate(task.due_date);
      out.push({
        key: `t${task.id}`,
        kind: "task",
        title: `${task.code} ${task.title}`,
        start: day,
        end: addDays(day, 1),
        allDay: true,
        colour: KIND_COLOUR.task,
        done: ["APPROVED", "COMPLETED"].includes(task.status),
        sub: task.assignee ?? "",
        task,
      });
    }
  if (show.todo)
    for (const todo of feed.todos) {
      const timed = Boolean(todo.due_at);
      const start = todo.due_at ? utc(todo.due_at) : todo.due_date ? localDate(todo.due_date) : null;
      if (!start) continue;
      out.push({
        key: `d${todo.id}`,
        kind: "todo",
        title: todo.title,
        start,
        end: timed ? new Date(start.getTime() + 30 * 60_000) : addDays(start, 1),
        allDay: !timed,
        colour: KIND_COLOUR.todo,
        done: todo.done,
        sub: todo.mine ? "" : todo.owner.name,
        todo,
      });
    }
  return out.sort((a, b) => Number(b.allDay) - Number(a.allDay) || a.start.getTime() - b.start.getTime());
}

function covers(item: Item, day: Date): boolean {
  const start = dayStart(day);
  const end = addDays(start, 1);
  return item.start < end && item.end > start;
}

// -- page ----------------------------------------------------------------------------------------

export function AgendaPage({ role }: { role: Role }) {
  const [view, setView] = useState<View>("week");
  const [cursor, setCursor] = useState(() => new Date());
  const [scope, setScope] = useState<Scope>(role === "EMPLOYEE" ? "mine" : "team");
  const [person, setPerson] = useState("");
  const [show, setShow] = useState<Record<Kind, boolean>>({ event: true, meeting: true, task: true, todo: true });
  const [feed, setFeed] = useState<Feed | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [todos, setTodos] = useState<Todo[]>([]);
  const [open, setOpen] = useState<Item | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [notice, setNotice] = useState("");
  const [now, setNow] = useState(() => Date.now());

  const [from, to] = useMemo(() => range(view, cursor), [view, cursor]);
  const items = useMemo(() => toItems(feed, show), [feed, show]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ start: from.toISOString(), end: to.toISOString(), scope });
      if (person) params.set("person", person);
      setFeed(await api<Feed>(`?${params}`));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the calendar.");
    } finally {
      setLoading(false);
    }
  }, [from, to, scope, person]);

  const loadTodos = useCallback(async () => {
    try {
      setTodos(await api<Todo[]>("/todos"));
    } catch {
      // The todo list stays as it was.
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadTodos();
      void api<Person[]>("/people")
        .then(setPeople)
        .catch(() => undefined);
      const params = new URLSearchParams(window.location.search);
      const wanted = params.get("event");
      if (wanted) {
        void api<AgendaEvent>(`/events/${wanted}`)
          .then((event) => {
            const start = utc(event.starts_at);
            setCursor(start);
            setOpen({ key: `e${event.id}`, kind: "event", title: event.title, start, end: utc(event.ends_at), allDay: event.all_day, colour: event.colour, event });
          })
          .catch((reason) => setNotice(reason instanceof Error ? reason.message : "That event was not found."));
      }
      if (params.get("new")) setDraft(newDraft(new Date()));
    }, 0);
    const tick = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(tick);
    };
  }, [loadTodos]);

  useEffect(() => {
    let timer: number | undefined;
    const off = subscribeRealtime((event) => {
      if (event.type !== "agenda.changed" && event.type !== "chat.meeting") return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        void load();
        void loadTodos();
      }, 300);
    });
    return () => {
      window.clearTimeout(timer);
      off();
    };
  }, [load, loadTodos]);

  // Keep the open details in step with fresh data.
  useEffect(() => {
    if (!open || !feed) return;
    const fresh = toItems(feed, { event: true, meeting: true, task: true, todo: true }).find((item) => item.key === open.key);
    if (fresh && fresh !== open) {
      const timer = window.setTimeout(() => setOpen(fresh), 0);
      return () => window.clearTimeout(timer);
    }
  }, [feed, open]);

  function move(step: number) {
    setCursor((current) => {
      if (view === "month") return new Date(current.getFullYear(), current.getMonth() + step, 1);
      if (view === "week") return addDays(current, 7 * step);
      if (view === "list") return addDays(current, 30 * step);
      return addDays(current, step);
    });
  }

  function newDraft(at: Date, allDay = false): Draft {
    const start = new Date(at);
    if (!allDay && start.getMinutes() % 30) start.setMinutes(start.getMinutes() < 30 ? 30 : 60, 0, 0);
    const end = new Date(start.getTime() + 30 * 60_000);
    return {
      id: null,
      title: "",
      day: iso(start),
      start: hhmm(start),
      end: hhmm(end),
      allDay,
      video: false,
      location: "",
      notes: "",
      colour: "blue",
      attendees: [],
    };
  }

  function editDraft(event: AgendaEvent): Draft {
    const start = utc(event.starts_at);
    const end = utc(event.ends_at);
    return {
      id: event.id,
      title: event.title,
      day: iso(start),
      start: hhmm(start),
      end: hhmm(end),
      allDay: event.all_day,
      video: event.video,
      location: event.location,
      notes: event.notes,
      colour: event.colour,
      attendees: event.attendees.map((item) => item.person),
    };
  }

  async function act(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      setNotice(done);
      await load();
      await loadTodos();
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "That did not work.");
    }
  }

  const canPickPeople = role !== "EMPLOYEE";
  const visiblePeople = feed?.people ?? [];

  return (
    <>
      <DashboardHero
        title=""
        highlight="Calendar"
        description="Your meetings, events, task deadlines and todos in one place. Invite people, join video calls and get a reminder 10 minutes before."
        compact
      />
      <div className="dash-content">
        <section className="agenda" aria-live="polite">
          {notice && (
            <div className="agenda-notice" role="status">
              <span>{notice}</span>
              <button type="button" aria-label="Dismiss" onClick={() => setNotice("")}>
                <X />
              </button>
            </div>
          )}
          <header className="agenda-bar">
            <div className="agenda-nav">
              <button type="button" className="agenda-today" onClick={() => setCursor(new Date())}>
                Today
              </button>
              <button type="button" className="agenda-icon" aria-label="Previous" onClick={() => move(-1)}>
                <ChevronLeft />
              </button>
              <button type="button" className="agenda-icon" aria-label="Next" onClick={() => move(1)}>
                <ChevronRight />
              </button>
              <h2>{heading(view, cursor)}</h2>
              {loading && <RefreshCw className="agenda-spin" aria-label="Loading" />}
            </div>
            <div className="agenda-controls">
              {canPickPeople && (
                <div className="agenda-select">
                  <LooplessSelect
                    value={person || scope}
                    ariaLabel="Whose calendar"
                    options={[
                      { value: "mine", label: "My calendar" },
                      { value: "team", label: role === "ADMIN" ? "Everyone" : "Me and my team" },
                      ...visiblePeople
                        .filter(() => scope !== "mine")
                        .map((item) => ({ value: item.id, label: item.name })),
                    ]}
                    onValueChange={(value) => {
                      if (value === "mine" || value === "team") {
                        setScope(value);
                        setPerson("");
                      } else {
                        setPerson(value);
                      }
                    }}
                  />
                </div>
              )}
              <div className="agenda-views" role="tablist" aria-label="View">
                {(["month", "week", "day", "list"] as View[]).map((value) => (
                  <button
                    key={value}
                    type="button"
                    role="tab"
                    aria-selected={view === value}
                    className={view === value ? "active" : undefined}
                    onClick={() => setView(value)}
                  >
                    {value[0].toUpperCase() + value.slice(1)}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="agenda-create"
                onClick={() => {
                  // Today: the next half hour. Another day in view: 10 am that day.
                  const day = view === "day" || view === "week" ? cursor : new Date();
                  setDraft(newDraft(sameDay(day, new Date()) ? new Date() : new Date(day.getFullYear(), day.getMonth(), day.getDate(), 10)));
                }}
              >
                <CalendarPlus aria-hidden="true" /> Create
              </button>
            </div>
          </header>

          <div className="agenda-layout">
            <aside className="agenda-side">
              <MiniMonth key={`${cursor.getFullYear()}-${cursor.getMonth()}`} cursor={cursor} items={items} onPick={(day) => {
                setCursor(day);
                if (view === "month") setView("day");
              }} />
              <fieldset className="agenda-filters">
                <legend>Show</legend>
                {(Object.keys(KIND_LABEL) as Kind[]).map((kind) => (
                  <label key={kind}>
                    <input
                      type="checkbox"
                      checked={show[kind]}
                      onChange={() => setShow((current) => ({ ...current, [kind]: !current[kind] }))}
                    />
                    <i style={{ background: COLOURS[kind === "event" ? "blue" : KIND_COLOUR[kind]] }} aria-hidden="true" />
                    {KIND_LABEL[kind]}
                  </label>
                ))}
              </fieldset>
              <TodoPanel todos={todos} now={now} onChange={() => void Promise.all([loadTodos(), load()])} onError={setNotice} />
            </aside>

            <div className="agenda-main">
              {error ? (
                <div className="agenda-empty">
                  <CalendarDays aria-hidden="true" />
                  <strong>{error}</strong>
                </div>
              ) : !feed ? (
                <div className="agenda-empty">
                  <OrbitLoader size={64} label="Loading the calendar" />
                </div>
              ) : view === "month" ? (
                <MonthView
                  cursor={cursor}
                  start={from}
                  items={items}
                  onOpen={setOpen}
                  onDay={(day) => {
                    setCursor(day);
                    setView("day");
                  }}
                  onCreate={(day) => setDraft(newDraft(new Date(day.getFullYear(), day.getMonth(), day.getDate(), 10), false))}
                />
              ) : view === "list" ? (
                <ListView start={from} items={items} onOpen={setOpen} />
              ) : (
                <TimeGrid
                  days={view === "day" ? [dayStart(cursor)] : Array.from({ length: 7 }, (_, index) => addDays(from, index))}
                  items={items}
                  now={now}
                  onOpen={setOpen}
                  onCreate={(at) => setDraft(newDraft(at))}
                  onDay={(day) => {
                    setCursor(day);
                    setView("day");
                  }}
                />
              )}
            </div>
          </div>
        </section>
      </div>

      {open && (
        <Details
          item={open}
          now={now}
          onClose={() => setOpen(null)}
          onEdit={(event) => {
            setOpen(null);
            setDraft(editDraft(event));
          }}
          onAnswer={(event, response) => void act(() => api(`/events/${event.id}/respond`, json("POST", { response })), "Answer saved.")}
          onCancel={(event) =>
            void act(async () => {
              await api(`/events/${event.id}`, { method: "DELETE" });
              setOpen(null);
            }, "Event cancelled. People were told by mail.")
          }
          onTodo={(todo, done) => void act(() => api(`/todos/${todo.id}`, json("PATCH", { done })), done ? "Todo done." : "Todo opened again.")}
        />
      )}

      {draft && (
        <EventEditor
          draft={draft}
          people={people}
          role={role}
          onClose={() => setDraft(null)}
          onSaved={(message) => {
            setDraft(null);
            setNotice(message);
            void load();
          }}
        />
      )}
    </>
  );
}

// -- small month ---------------------------------------------------------------------------------

function MiniMonth({ cursor, items, onPick }: { cursor: Date; items: Item[]; onPick: (day: Date) => void }) {
  // Remounted (by key) when the main calendar moves to another month.
  const [shown, setMonth] = useState(() => new Date(cursor.getFullYear(), cursor.getMonth(), 1));
  const start = weekStart(shown);
  const today = new Date();
  const busy = new Set(items.map((item) => iso(item.start)));
  return (
    <div className="agenda-mini">
      <header>
        <strong>{shown.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</strong>
        <span>
          <button type="button" aria-label="Previous month" onClick={() => setMonth(new Date(shown.getFullYear(), shown.getMonth() - 1, 1))}>
            <ChevronLeft />
          </button>
          <button type="button" aria-label="Next month" onClick={() => setMonth(new Date(shown.getFullYear(), shown.getMonth() + 1, 1))}>
            <ChevronRight />
          </button>
        </span>
      </header>
      <div className="agenda-mini-grid">
        {WEEKDAYS.map((day) => (
          <small key={day}>{day[0]}</small>
        ))}
        {Array.from({ length: 42 }, (_, index) => addDays(start, index)).map((day) => (
          <button
            key={iso(day)}
            type="button"
            className={[
              day.getMonth() !== shown.getMonth() ? "out" : "",
              sameDay(day, today) ? "today" : "",
              sameDay(day, cursor) ? "picked" : "",
              busy.has(iso(day)) ? "busy" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-label={day.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
            onClick={() => onPick(day)}
          >
            {day.getDate()}
          </button>
        ))}
      </div>
    </div>
  );
}

// -- views ---------------------------------------------------------------------------------------

function Chip({ item, onOpen, compact = false }: { item: Item; onOpen: (item: Item) => void; compact?: boolean }) {
  const colour = COLOURS[item.colour] ?? COLOURS.blue;
  return (
    <button
      type="button"
      className={`agenda-chip ${item.kind}${item.allDay ? " all-day" : ""}${item.done ? " done" : ""}${compact ? " compact" : ""}`}
      style={{ ["--chip" as string]: colour }}
      title={`${item.title}${item.allDay ? "" : ` · ${timeLabel(item.start)}`}`}
      onClick={(event) => {
        event.stopPropagation();
        onOpen(item);
      }}
    >
      {!item.allDay && <time>{timeLabel(item.start)}</time>}
      {item.kind === "task" && <ClipboardList aria-hidden="true" />}
      {item.kind === "todo" && (item.done ? <CheckSquare aria-hidden="true" /> : <Check aria-hidden="true" />)}
      {item.kind === "meeting" && <MessageSquare aria-hidden="true" />}
      {item.event?.video && <Video aria-hidden="true" />}
      <span>{item.title}</span>
    </button>
  );
}

function MonthView({
  cursor,
  start,
  items,
  onOpen,
  onDay,
  onCreate,
}: {
  cursor: Date;
  start: Date;
  items: Item[];
  onOpen: (item: Item) => void;
  onDay: (day: Date) => void;
  onCreate: (day: Date) => void;
}) {
  const today = new Date();
  return (
    <div className="agenda-month">
      {WEEKDAYS.map((day) => (
        <div key={day} className="agenda-month-head">
          {day}
        </div>
      ))}
      {Array.from({ length: 42 }, (_, index) => addDays(start, index)).map((day) => {
        const here = items.filter((item) => covers(item, day));
        return (
          <div
            key={iso(day)}
            className={`agenda-cell${day.getMonth() !== cursor.getMonth() ? " out" : ""}${sameDay(day, today) ? " today" : ""}`}
            onClick={() => onCreate(day)}
          >
            <button
              type="button"
              className="agenda-cell-day"
              onClick={(event) => {
                event.stopPropagation();
                onDay(day);
              }}
            >
              {day.getDate() === 1 ? day.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : day.getDate()}
            </button>
            {here.slice(0, 3).map((item) => (
              <Chip key={item.key} item={item} onOpen={onOpen} compact />
            ))}
            {here.length > 3 && (
              <button
                type="button"
                className="agenda-more"
                onClick={(event) => {
                  event.stopPropagation();
                  onDay(day);
                }}
              >
                +{here.length - 3} more
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ListView({ start, items, onOpen }: { start: Date; items: Item[]; onOpen: (item: Item) => void }) {
  const days = Array.from({ length: 30 }, (_, index) => addDays(start, index))
    .map((day) => ({ day, items: items.filter((item) => covers(item, day)) }))
    .filter((entry) => entry.items.length);
  if (!days.length) {
    return (
      <div className="agenda-empty">
        <CalendarDays aria-hidden="true" />
        <strong>Nothing in the next 30 days.</strong>
        <span>Use Create to plan a meeting or an event.</span>
      </div>
    );
  }
  return (
    <div className="agenda-list">
      {days.map(({ day, items: dayItems }) => (
        <section key={iso(day)}>
          <h3 className={sameDay(day, new Date()) ? "today" : undefined}>
            <b>{day.getDate()}</b>
            <span>
              {day.toLocaleDateString("en-IN", { weekday: "long" })}
              <small>{day.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</small>
            </span>
          </h3>
          <ul>
            {dayItems.map((item) => (
              <li key={item.key}>
                <button type="button" onClick={() => onOpen(item)} style={{ ["--chip" as string]: COLOURS[item.colour] ?? COLOURS.blue }}>
                  <i aria-hidden="true" />
                  <time>{item.allDay ? "All day" : `${timeLabel(item.start)} – ${timeLabel(item.end)}`}</time>
                  <strong className={item.done ? "done" : undefined}>{item.title}</strong>
                  {item.sub && <small>{item.sub}</small>}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function TimeGrid({
  days,
  items,
  now,
  onOpen,
  onCreate,
  onDay,
}: {
  days: Date[];
  items: Item[];
  now: number;
  onOpen: (item: Item) => void;
  onCreate: (at: Date) => void;
  onDay: (day: Date) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const first = days[0]?.getTime() ?? 0;
  useEffect(() => {
    // Start the day around 7:30 am (after layout, so it also works when opened from a link).
    const frame = window.requestAnimationFrame(() => {
      if (scroller.current) scroller.current.scrollTop = HOUR_PX * 7.5;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [first]);
  const today = new Date(now);
  return (
    <div className={`agenda-grid${days.length === 1 ? " single" : ""}`} style={{ ["--days" as string]: days.length }}>
      <div className="agenda-grid-head">
        <span />
        {days.map((day) => (
          <button key={iso(day)} type="button" className={sameDay(day, today) ? "today" : undefined} onClick={() => onDay(day)}>
            <small>{day.toLocaleDateString("en-IN", { weekday: "short" })}</small>
            <b>{day.getDate()}</b>
          </button>
        ))}
      </div>
      <div className="agenda-grid-allday">
        <span>All day</span>
        {days.map((day) => (
          <div key={iso(day)}>
            {items
              .filter((item) => item.allDay && covers(item, day))
              .map((item) => (
                <Chip key={item.key} item={item} onOpen={onOpen} compact />
              ))}
          </div>
        ))}
      </div>
      <div className="agenda-grid-body" ref={scroller}>
        <div className="agenda-hours">
          {Array.from({ length: 24 }, (_, hour) => (
            <span key={hour} style={{ top: hour * HOUR_PX }}>
              {hour === 0 ? "" : new Date(2026, 0, 1, hour).toLocaleTimeString("en-IN", { hour: "numeric" })}
            </span>
          ))}
        </div>
        {days.map((day) => (
          <DayColumn key={iso(day)} day={day} items={items.filter((item) => !item.allDay && covers(item, day))} now={now} onOpen={onOpen} onCreate={onCreate} />
        ))}
      </div>
    </div>
  );
}

function DayColumn({
  day,
  items,
  now,
  onOpen,
  onCreate,
}: {
  day: Date;
  items: Item[];
  now: number;
  onOpen: (item: Item) => void;
  onCreate: (at: Date) => void;
}) {
  // Side by side when items overlap (simple columns per cluster).
  const placed = useMemo(() => {
    const sorted = [...items].sort((a, b) => a.start.getTime() - b.start.getTime() || b.end.getTime() - a.end.getTime());
    const out: { item: Item; column: number; columns: number }[] = [];
    let cluster: { item: Item; column: number }[] = [];
    let clusterEnd = 0;
    const flush = () => {
      const columns = Math.max(1, ...cluster.map((entry) => entry.column + 1));
      cluster.forEach((entry) => out.push({ ...entry, columns }));
      cluster = [];
    };
    for (const item of sorted) {
      if (cluster.length && item.start.getTime() >= clusterEnd) flush();
      const used = new Set(cluster.filter((entry) => entry.item.end > item.start).map((entry) => entry.column));
      let column = 0;
      while (used.has(column)) column += 1;
      cluster.push({ item, column });
      clusterEnd = Math.max(clusterEnd, item.end.getTime());
    }
    flush();
    return out;
  }, [items]);
  const start = dayStart(day).getTime();
  const isToday = sameDay(day, new Date(now));
  return (
    <div
      className={`agenda-day${isToday ? " today" : ""}`}
      onClick={(event) => {
        const box = event.currentTarget.getBoundingClientRect();
        const minutes = Math.floor(((event.clientY - box.top) / HOUR_PX) * 2) * 30;
        onCreate(new Date(start + minutes * 60_000));
      }}
    >
      {Array.from({ length: 24 }, (_, hour) => (
        <i key={hour} style={{ top: hour * HOUR_PX }} aria-hidden="true" />
      ))}
      {placed.map(({ item, column, columns }) => {
        const top = Math.max(0, (item.start.getTime() - start) / 3_600_000) * HOUR_PX;
        const bottom = Math.min(24, (item.end.getTime() - start) / 3_600_000) * HOUR_PX;
        const colour = COLOURS[item.colour] ?? COLOURS.blue;
        return (
          <button
            key={item.key}
            type="button"
            className={`agenda-block ${item.kind}${item.done ? " done" : ""}`}
            style={{
              top,
              height: Math.max(22, bottom - top - 2),
              left: `calc(${(100 / columns) * column}% + 2px)`,
              width: `calc(${100 / columns}% - 4px)`,
              ["--chip" as string]: colour,
            }}
            onClick={(event) => {
              event.stopPropagation();
              onOpen(item);
            }}
          >
            <strong>
              {item.event?.video && <Video aria-hidden="true" />}
              {item.title}
            </strong>
            <small>
              {timeLabel(item.start)} – {timeLabel(item.end)}
              {item.sub ? ` · ${item.sub}` : ""}
            </small>
          </button>
        );
      })}
      {isToday && <b className="agenda-now" style={{ top: ((now - start) / 3_600_000) * HOUR_PX }} aria-hidden="true" />}
    </div>
  );
}

// -- details -------------------------------------------------------------------------------------

function Details({
  item,
  now,
  onClose,
  onEdit,
  onAnswer,
  onCancel,
  onTodo,
}: {
  item: Item;
  now: number;
  onClose: () => void;
  onEdit: (event: AgendaEvent) => void;
  onAnswer: (event: AgendaEvent, response: Answer) => void;
  onCancel: (event: AgendaEvent) => void;
  onTodo: (todo: Todo, done: boolean) => void;
}) {
  useEffect(() => {
    const key = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  const colour = COLOURS[item.colour] ?? COLOURS.blue;
  const event = item.event;
  const when = item.allDay
    ? item.start.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" }) +
      (item.end.getTime() - item.start.getTime() > 864e5 ? ` – ${addDays(item.end, -1).toLocaleDateString("en-IN", { day: "numeric", month: "long" })}` : "")
    : `${item.start.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })} · ${timeLabel(item.start)} – ${timeLabel(item.end)}`;
  const joinOpen = now >= item.start.getTime() - 10 * 60_000 && now <= item.end.getTime();
  const conversation = event?.conversation_id ?? item.meeting?.conversation_id ?? null;
  return (
    <div className="agenda-sheet-back" onClick={onClose}>
      <aside className="agenda-sheet" role="dialog" aria-modal="true" aria-label={item.title} onClick={(e) => e.stopPropagation()}>
        <header style={{ ["--chip" as string]: colour }}>
          <span className="agenda-kind">
            <i aria-hidden="true" />
            {item.kind === "event" ? (event?.video ? "Video call" : "Event") : item.kind === "meeting" ? "Chat meeting" : item.kind === "task" ? "Task deadline" : "Todo"}
          </span>
          <span className="agenda-sheet-tools">
            {event?.can_edit && (
              <>
                <button type="button" aria-label="Edit" title="Edit" onClick={() => onEdit(event)}>
                  <Pencil />
                </button>
                <button type="button" aria-label="Cancel event" title="Cancel event" onClick={() => onCancel(event)}>
                  <Trash2 />
                </button>
              </>
            )}
            <button type="button" aria-label="Close" onClick={onClose}>
              <X />
            </button>
          </span>
        </header>
        <h3 className={item.done ? "done" : undefined}>{item.title}</h3>
        <p className="agenda-when">
          <Clock3 aria-hidden="true" /> {when}
        </p>

        {conversation && (item.kind === "meeting" || event?.video) && (
          <div className="agenda-join">
            <button
              type="button"
              className="agenda-join-btn"
              disabled={!joinOpen}
              onClick={() => startCall(conversation, item.meeting?.kind === "AUDIO" ? "AUDIO" : "VIDEO", item.title)}
            >
              <Video aria-hidden="true" /> Join call
            </button>
            <small>{joinOpen ? "The call is open." : "Opens 10 minutes before the start."}</small>
          </div>
        )}

        {event && (
          <>
            {event.my_response !== null && (
              <div className="agenda-rsvp">
                <span>Going?</span>
                {(["YES", "MAYBE", "NO"] as Answer[]).map((answer) => (
                  <button
                    key={answer}
                    type="button"
                    className={event.my_response === answer ? "active" : undefined}
                    aria-pressed={event.my_response === answer}
                    onClick={() => onAnswer(event, answer)}
                  >
                    {answer === "YES" ? "Yes" : answer === "NO" ? "No" : "Maybe"}
                  </button>
                ))}
              </div>
            )}
            {event.location && (
              <p className="agenda-line">
                <MapPin aria-hidden="true" /> {event.location}
              </p>
            )}
            <div className="agenda-people">
              <h4>
                <UsersRound aria-hidden="true" /> {event.attendees.length + 1} {event.attendees.length ? "people" : "person"}
              </h4>
              <ul>
                <li>
                  <Avatar person={event.owner} />
                  <span>
                    {event.owner.name}
                    <small>Organiser</small>
                  </span>
                </li>
                {event.attendees.map(({ person, response }) => (
                  <li key={person.id}>
                    <Avatar person={person} />
                    <span>
                      {person.name}
                      <small className={response.toLowerCase()}>{ANSWER_LABEL[response]}</small>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            {event.notes && <p className="agenda-notes">{event.notes}</p>}
            <div className="agenda-sheet-actions">
              {event.attendees.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    const ids = [event.owner, ...event.attendees.map((a) => a.person)].map((p) => p.id).join(",");
                    openMail(`/mail?compose=1&to=${ids}&subject=${encodeURIComponent(event.title)}`);
                  }}
                >
                  <Mail aria-hidden="true" /> Email people
                </button>
              )}
              {event.mail_thread_id && (
                <button type="button" onClick={() => openMail(`/mail?m=${event.mail_thread_id}`)}>
                  <ExternalLink aria-hidden="true" /> Open the mail
                </button>
              )}
              {event.conversation_id && (
                <Link href={`/chat?c=${event.conversation_id}`}>
                  <MessageSquare aria-hidden="true" /> Open the chat
                </Link>
              )}
            </div>
          </>
        )}

        {item.meeting && (
          <div className="agenda-sheet-actions">
            <p className="agenda-line">
              <MessageSquare aria-hidden="true" /> Planned in {item.meeting.room}
            </p>
            <Link href={`/chat?c=${item.meeting.conversation_id}`}>
              <MessageSquare aria-hidden="true" /> Open the chat
            </Link>
          </div>
        )}

        {item.task && (
          <>
            <p className="agenda-line">
              <ClipboardList aria-hidden="true" /> {item.task.status.replace("_", " ").toLowerCase()}
              {item.task.assignee ? ` · ${item.task.assignee}` : ""}
              {item.task.client ? ` · ${item.task.client}` : ""}
            </p>
            <div className="agenda-sheet-actions">
              <Link href={`/tasks?task=${item.task.id}`}>
                <ExternalLink aria-hidden="true" /> Open the task
              </Link>
            </div>
          </>
        )}

        {item.todo && (
          <>
            {item.todo.notes && <p className="agenda-notes">{item.todo.notes}</p>}
            {!item.todo.mine && <p className="agenda-line">Belongs to {item.todo.owner.name}</p>}
            {item.todo.mine && (
              <div className="agenda-sheet-actions">
                <button type="button" onClick={() => item.todo && onTodo(item.todo, !item.todo.done)}>
                  <CheckSquare aria-hidden="true" /> {item.todo.done ? "Mark as not done" : "Mark as done"}
                </button>
              </div>
            )}
          </>
        )}
      </aside>
    </div>
  );
}

function Avatar({ person }: { person: Person }) {
  const initials = person.name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <b className="agenda-avatar" aria-hidden="true">
      {initials || "?"}
    </b>
  );
}

// -- editor --------------------------------------------------------------------------------------

function EventEditor({
  draft: initial,
  people,
  role,
  onClose,
  onSaved,
}: {
  draft: Draft;
  people: Person[];
  role: Role;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [pick, setPick] = useState("");
  const editing = Boolean(draft.id);
  const update = (change: Partial<Draft>) => {
    setProblem("");
    setDraft((current) => ({ ...current, ...change }));
  };

  useEffect(() => {
    const key = (event: KeyboardEvent) => event.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [busy, onClose]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft.title.trim()) return setProblem("Give it a title.");
    const startsAt = draft.allDay ? new Date(`${draft.day}T00:00`) : new Date(`${draft.day}T${draft.start}`);
    let endsAt = draft.allDay ? addDays(startsAt, 1) : new Date(`${draft.day}T${draft.end}`);
    if (!draft.allDay && endsAt <= startsAt) endsAt = addDays(endsAt, 1); // ends after midnight
    if (draft.video && !draft.attendees.length) return setProblem("Invite someone to the video call.");
    if (draft.video && draft.attendees.length > 1 && role === "EMPLOYEE")
      return setProblem("Only the admin and managers host group video calls. Invite one person.");
    setBusy(true);
    const body = {
      title: draft.title.trim(),
      notes: draft.notes,
      location: draft.location,
      starts_at: startsAt.toISOString(),
      ends_at: endsAt.toISOString(),
      all_day: draft.allDay,
      colour: draft.colour,
      attendee_ids: draft.attendees.map((person) => person.id),
    };
    try {
      if (editing) await api(`/events/${draft.id}`, json("PATCH", body));
      else await api("/events", json("POST", { ...body, video: draft.video }));
      onSaved(
        editing
          ? "Event saved. People were told about changes by mail."
          : draft.attendees.length
            ? `Event created. ${draft.attendees.length === 1 ? "The invitation went" : "Invitations went"} by mail.`
            : "Event created.",
      );
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "Could not save the event.");
      setBusy(false);
    }
  }

  const options = people
    .filter((person) => !draft.attendees.some((chosen) => chosen.id === person.id))
    .map((person) => ({ value: person.id, label: `${person.name} · ${person.role[0]}${person.role.slice(1).toLowerCase()}` }));

  return (
    <div className="agenda-modal-back" onClick={() => !busy && onClose()}>
      <form className="agenda-modal" role="dialog" aria-modal="true" aria-label={editing ? "Edit event" : "New event"} onClick={(e) => e.stopPropagation()} onSubmit={(e) => void save(e)}>
        <header>
          <h2>{editing ? "Edit event" : "New event"}</h2>
          <button type="button" className="agenda-icon" aria-label="Close" onClick={onClose} disabled={busy}>
            <X />
          </button>
        </header>
        <input
          className="agenda-title-input"
          value={draft.title}
          autoFocus
          maxLength={160}
          placeholder="Add a title"
          aria-label="Title"
          onChange={(event) => update({ title: event.target.value })}
        />
        <div className="agenda-row">
          <label className="agenda-field">
            <span>Date</span>
            <input type="date" value={draft.day} aria-label="Date" onChange={(event) => update({ day: event.target.value })} />
          </label>
          {!draft.allDay && (
            <>
              <label className="agenda-field">
                <span>From</span>
                <input type="time" value={draft.start} aria-label="Start time" onChange={(event) => update({ start: event.target.value })} />
              </label>
              <label className="agenda-field">
                <span>To</span>
                <input type="time" value={draft.end} aria-label="End time" onChange={(event) => update({ end: event.target.value })} />
              </label>
            </>
          )}
        </div>
        <div className="agenda-toggles">
          <label>
            <input type="checkbox" checked={draft.allDay} onChange={(event) => update({ allDay: event.target.checked, video: event.target.checked ? false : draft.video })} />
            All day
          </label>
          <label className={editing ? "disabled" : undefined} title={editing ? "Video is set when the event is created." : undefined}>
            <input type="checkbox" checked={draft.video} disabled={editing || draft.allDay} onChange={(event) => update({ video: event.target.checked })} />
            <Video aria-hidden="true" /> Video call
          </label>
        </div>
        <div className="agenda-field">
          <span>People</span>
          <div className="agenda-attendees">
            {draft.attendees.map((person) => (
              <span key={person.id} className="agenda-person-chip">
                <Avatar person={person} />
                {person.name}
                <button type="button" aria-label={`Remove ${person.name}`} onClick={() => update({ attendees: draft.attendees.filter((p) => p.id !== person.id) })}>
                  <X />
                </button>
              </span>
            ))}
            {options.length > 0 && (
              <div className="agenda-add-person">
                <LooplessSelect
                  value={pick}
                  ariaLabel="Invite someone"
                  options={[{ value: "", label: "Invite someone…" }, ...options]}
                  onValueChange={(value) => {
                    const person = people.find((p) => p.id === value);
                    if (person) update({ attendees: [...draft.attendees, person] });
                    setPick("");
                  }}
                />
              </div>
            )}
          </div>
          {draft.attendees.length > 0 && <small className="agenda-hint">They get an invitation in Mail and answer Yes, No or Maybe.</small>}
        </div>
        <label className="agenda-field">
          <span>Where</span>
          <input value={draft.location} maxLength={200} placeholder="Studio, office, client place…" onChange={(event) => update({ location: event.target.value })} />
        </label>
        <label className="agenda-field">
          <span>Notes</span>
          <textarea rows={3} value={draft.notes} maxLength={2000} placeholder="Agenda, links, what to bring…" onChange={(event) => update({ notes: event.target.value })} />
        </label>
        <div className="agenda-field">
          <span>Colour</span>
          <div className="agenda-swatches" role="radiogroup" aria-label="Colour">
            {Object.entries(COLOURS).map(([name, value]) => (
              <button
                key={name}
                type="button"
                role="radio"
                aria-checked={draft.colour === name}
                aria-label={name}
                className={draft.colour === name ? "active" : undefined}
                style={{ background: value }}
                onClick={() => update({ colour: name })}
              />
            ))}
          </div>
        </div>
        {problem && (
          <p className="agenda-problem" role="alert">
            {problem}
          </p>
        )}
        <footer>
          <small>Reminder 10 minutes before and at the start.</small>
          <button type="button" className="agenda-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="agenda-primary" disabled={busy}>
            {busy ? "Saving…" : editing ? "Save" : "Create"}
          </button>
        </footer>
      </form>
    </div>
  );
}

// -- todos ---------------------------------------------------------------------------------------

function TodoPanel({
  todos,
  now,
  onChange,
  onError,
}: {
  todos: Todo[];
  now: number;
  onChange: () => void;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [day, setDay] = useState("");
  const [time, setTime] = useState("");
  const [more, setMore] = useState(false);
  // Ticks show at once; the server answer follows (a failed save puts the tick back).
  const [ticked, setTicked] = useState<Record<string, boolean>>({});
  const isDone = (todo: Todo) => (todo.id in ticked ? ticked[todo.id] : todo.done);
  const open = todos.filter((todo) => !isDone(todo));
  const done = todos.filter((todo) => isDone(todo));

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    const body: Record<string, unknown> = { title: title.trim() };
    if (day && time) body.due_at = new Date(`${day}T${time}`).toISOString();
    else if (day) body.due_date = day;
    try {
      await api("/todos", json("POST", body));
      setTitle("");
      setDay("");
      setTime("");
      setMore(false);
      onChange();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Could not add the todo.");
    }
  }

  async function change(todo: Todo, body: Record<string, unknown>) {
    if (typeof body.done === "boolean") setTicked((current) => ({ ...current, [todo.id]: body.done as boolean }));
    try {
      await api(`/todos/${todo.id}`, json("PATCH", body));
      onChange();
    } catch (reason) {
      setTicked((current) => {
        const next = { ...current };
        delete next[todo.id];
        return next;
      });
      onError(reason instanceof Error ? reason.message : "Could not change the todo.");
    }
  }

  async function remove(todo: Todo) {
    try {
      await api(`/todos/${todo.id}`, { method: "DELETE" });
      onChange();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Could not delete the todo.");
    }
  }

  const due = (todo: Todo): ReactNode => {
    if (todo.due_at) {
      const at = utc(todo.due_at);
      const late = !todo.done && at.getTime() < now;
      return <small className={late ? "late" : undefined}>{at.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</small>;
    }
    if (todo.due_date) {
      const at = localDate(todo.due_date);
      const late = !todo.done && at < dayStart(new Date(now));
      return <small className={late ? "late" : undefined}>{at.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</small>;
    }
    return null;
  };

  return (
    <section className="agenda-todos" aria-label="My todos">
      <h3>
        <CheckSquare aria-hidden="true" /> My todos <b>{open.length}</b>
      </h3>
      <form onSubmit={(event) => void add(event)}>
        <div className="agenda-todo-add">
          <input value={title} maxLength={200} placeholder="Add a todo" aria-label="New todo" onChange={(event) => setTitle(event.target.value)} onFocus={() => setMore(true)} />
          <button type="submit" aria-label="Add todo" disabled={!title.trim()}>
            <Plus />
          </button>
        </div>
        {more && (
          <div className="agenda-todo-when">
            <input type="date" value={day} aria-label="Due date" onChange={(event) => setDay(event.target.value)} />
            <input type="time" value={time} aria-label="Due time" disabled={!day} onChange={(event) => setTime(event.target.value)} />
          </div>
        )}
      </form>
      <ul>
        {[...open, ...done].map((todo) => (
          <li key={todo.id} className={isDone(todo) ? "done" : undefined}>
            <label>
              <input type="checkbox" checked={isDone(todo)} onChange={() => void change(todo, { done: !isDone(todo) })} aria-label={`Done: ${todo.title}`} />
              <span>
                {todo.title}
                {due(todo)}
              </span>
            </label>
            <button type="button" aria-label={`Delete ${todo.title}`} onClick={() => void remove(todo)}>
              <Trash2 />
            </button>
          </li>
        ))}
        {!todos.length && <li className="agenda-todo-empty">Nothing to do. Add a todo above.</li>}
      </ul>
    </section>
  );
}
