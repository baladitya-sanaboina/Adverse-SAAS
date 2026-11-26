"use client";

/*
 * Content calendar as a sheet (owner request 2026-11-14): the same rows and columns as the
 * owner's "Path Of Aditya Content Calendar" Google Sheet. Cells edit in place. Progress columns
 * are plain tick boxes (the sheet's colours only marked status, so they are not copied); a no-post
 * day is one "No Reel" row; Script and PDF's LINKS hold links the client types in.
 * Columns: Date | Week | Day | Video Topic | Reference Video | Recorded | Script | Edited |
 * Insta-Posted | Youtube-Post | Script | PDF's LINKS (+ Client and Ticket for the Admin).
 */
import Link from "next/link";
import { useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import {
  CirclePlay,
  FileSpreadsheet,
  FileText,
  Film,
  HardDrive,
  Link2,
  MoreHorizontal,
  Presentation,
  type LucideIcon,
} from "lucide-react";
import type { CalendarEntry } from "./content-calendar";
import { LooplessDate } from "@/components/foundation/loopless-date";
import { LooplessSelect } from "@/components/foundation/loopless-select";

// STAFF: a manager or employee with access to the client (owner request 2026-11-26), view only.
type Role = "ADMIN" | "CLIENT" | "STAFF";
type Tick = "recorded" | "script_ready" | "edited" | "posted_instagram" | "posted_youtube";
type TextField = "title" | "reference_url" | "script_url" | "pdf_url" | "notes" | "entry_date";

const DAY_MS = 24 * 60 * 60 * 1000;
const MERGED = 9; // Video Topic … PDF's LINKS, one cell on a "No Reel" row

function parse(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function sheetDate(value: string): string {
  const [year, month, day] = value.split("-");
  return `${day}-${month}-${year}`;
}

/** Sunday that starts the week of a date (the sheet counts weeks Sunday to Saturday). */
function weekStart(value: string): number {
  const day = parse(value);
  return new Date(day.getFullYear(), day.getMonth(), day.getDate() - day.getDay()).getTime();
}

function EditCell({
  value,
  display,
  type = "text",
  placeholder,
  disabled,
  disabledTitle = "Your agency is working on this video",
  className,
  onSave,
}: {
  value: string;
  display?: ReactNode;
  type?: "text" | "date" | "url";
  placeholder?: string;
  disabled?: boolean;
  disabledTitle?: string;
  className?: string;
  onSave: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  function finish(save: boolean) {
    setEditing(false);
    if (save && draft.trim() !== value.trim()) onSave(draft.trim());
    else setDraft(value);
  }

  if (editing && type === "date") {
    return (
      <td className={`sheet-cell editing ${className ?? ""}`}>
        <LooplessDate
          value={value}
          ariaLabel="Date"
          clearable={false}
          defaultOpen
          onClose={() => setEditing(false)}
          onValueChange={(next) => {
            setEditing(false);
            if (next && next !== value) onSave(next);
          }}
        />
      </td>
    );
  }
  if (editing) {
    return (
      <td className={`sheet-cell editing ${className ?? ""}`}>
        <input
          autoFocus
          type={type}
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => finish(true)}
          onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
            if (event.key === "Enter") finish(true);
            if (event.key === "Escape") finish(false);
          }}
        />
      </td>
    );
  }
  return (
    <td className={`sheet-cell ${className ?? ""}`}>
      <button
        type="button"
        className="sheet-cell-button"
        disabled={disabled}
        title={disabled ? disabledTitle : "Click to edit"}
        onClick={() => {
          setDraft(value);
          setEditing(true);
        }}
      >
        {display ?? (value || <span className="sheet-placeholder">{placeholder}</span>)}
      </button>
    </td>
  );
}

/*
 * A link shows as a chip with what it points to, the way Google Sheets shows a Doc
 * (owner request 2026-11-19): Google Doc, Google Sheet, Slides, Drive, PDF, Instagram, YouTube.
 */
export function linkInfo(url: string): { kind: string; label: string; Icon: LucideIcon } {
  let host = "";
  let path = "";
  try {
    const parsed = new URL(url);
    host = parsed.hostname.replace(/^www\./, "").toLowerCase();
    path = parsed.pathname.toLowerCase();
  } catch {
    return { kind: "web", label: "Link", Icon: Link2 };
  }
  if (host === "docs.google.com") {
    if (path.startsWith("/spreadsheets")) return { kind: "sheet", label: "Google Sheet", Icon: FileSpreadsheet };
    if (path.startsWith("/presentation")) return { kind: "slides", label: "Google Slides", Icon: Presentation };
    if (path.startsWith("/forms")) return { kind: "doc", label: "Google Form", Icon: FileText };
    return { kind: "doc", label: "Google Doc", Icon: FileText };
  }
  if (path.endsWith(".pdf")) return { kind: "pdf", label: "PDF", Icon: FileText };
  if (host === "drive.google.com") return { kind: "drive", label: "Drive file", Icon: HardDrive };
  if (host.endsWith("instagram.com")) {
    return { kind: "insta", label: path.startsWith("/p/") ? "Instagram post" : "Instagram reel", Icon: Film };
  }
  if (host === "youtu.be" || host.endsWith("youtube.com"))
    return { kind: "youtube", label: "YouTube", Icon: CirclePlay };
  return { kind: "web", label: host || "Link", Icon: Link2 };
}

export function LinkChip({ url, label }: { url: string; label?: string }) {
  const info = linkInfo(url);
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer noopener"
      className={`sheet-chip ${info.kind}`}
      aria-label={label ? `${label}: ${info.label}` : info.label}
      title={url}
      onClick={(event) => event.stopPropagation()}
    >
      <info.Icon aria-hidden="true" />
      <span>{info.label}</span>
    </a>
  );
}

function LinkCell({
  value,
  label,
  readOnly = false,
  onSave,
}: {
  value: string;
  label: string;
  readOnly?: boolean;
  onSave: (value: string) => void;
}) {
  if (readOnly) {
    return <td className="sheet-cell link">{value ? <LinkChip url={value} label={label} /> : null}</td>;
  }
  return (
    <EditCell
      value={value}
      type="url"
      placeholder="Add link"
      className="link"
      display={value ? <LinkChip url={value} label={label} /> : undefined}
      onSave={onSave}
    />
  );
}

function TickCell({
  on,
  label,
  title,
  disabled,
  onToggle,
}: {
  on: boolean;
  label: string;
  title?: string;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <td className="sheet-check">
      <button
        type="button"
        role="checkbox"
        aria-checked={on}
        aria-label={label}
        title={title ?? label}
        disabled={disabled}
        className={on ? "on" : undefined}
        onClick={onToggle}
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M3.5 8.5l3 3 6-7" />
        </svg>
      </button>
    </td>
  );
}

export function CalendarSheet({
  role,
  title,
  entries,
  showClient,
  canAdd,
  onToggle,
  onEdit,
  onAdd,
  onOpen,
  services = [],
}: {
  role: Role;
  title: string;
  entries: CalendarEntry[];
  showClient: boolean;
  canAdd: boolean;
  onToggle: (entry: CalendarEntry, key: Tick) => void;
  onEdit: (entry: CalendarEntry, field: TextField, value: string) => void;
  onAdd: (values: { entry_date: string; title: string; no_post: boolean; service_id: string }) => Promise<boolean>;
  onOpen: (entry: CalendarEntry) => void;
  /** Services to pick for a new row (owner request 2026-11-20: required). */
  services?: { id: string; name: string }[];
}) {
  const rows = useMemo(
    () =>
      [...entries].sort((a, b) => a.entry_date.localeCompare(b.entry_date) || a.created_at.localeCompare(b.created_at)),
    [entries],
  );
  // Week-1 is the week of each client's first entry.
  const firstWeek = useMemo(() => {
    const map = new Map<string, number>();
    for (const entry of rows) if (!map.has(entry.client.id)) map.set(entry.client.id, weekStart(entry.entry_date));
    return map;
  }, [rows]);
  const lastDate = rows[rows.length - 1]?.entry_date;
  const nextDate = (() => {
    const start = lastDate ? parse(lastDate) : new Date();
    const next = lastDate ? new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1) : start;
    return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-${String(next.getDate()).padStart(2, "0")}`;
  })();
  const [draft, setDraft] = useState({ entry_date: "", title: "", no_post: false, service_id: "" });
  const [hint, setHint] = useState("");
  const [adding, setAdding] = useState(false);
  const readOnly = role === "STAFF";
  const showTicket = role !== "CLIENT";
  const columns = 12 + (showClient ? 1 : 0) + (showTicket ? 1 : 0) + 1;

  async function add() {
    const values = { ...draft, entry_date: draft.entry_date || nextDate, title: draft.title.trim() };
    if (!values.no_post && !values.title) return;
    if (!values.no_post && !values.service_id) return setHint("Choose the service first.");
    setHint("");
    setAdding(true);
    if (await onAdd({ ...values, title: values.title || "No post" }))
      setDraft((current) => ({ entry_date: "", title: "", no_post: false, service_id: current.service_id }));
    setAdding(false);
  }

  return (
    <div className="sheet-wrap">
      <table className="sheet">
        <thead>
          <tr>
            <th className="sheet-title" colSpan={columns}>
              <span className="sheet-title-text">{title}</span>
            </th>
          </tr>
          <tr className="sheet-head">
            <th>Date</th>
            <th>Week</th>
            <th>Day</th>
            {showClient && <th>Client</th>}
            <th className="topic">Video Topic</th>
            <th>Reference Video</th>
            <th>Recorded</th>
            <th>Script</th>
            <th>Edited</th>
            <th>Insta-Posted</th>
            <th>Youtube-Post</th>
            <th>Script</th>
            <th>PDF&apos;s LINKS</th>
            {showTicket && <th>Ticket</th>}
            <th aria-label="Open" />
          </tr>
        </thead>
        <tbody>
          {rows.map((entry) => {
            const week =
              Math.floor((weekStart(entry.entry_date) - (firstWeek.get(entry.client.id) ?? 0)) / (7 * DAY_MS)) + 1;
            const day = parse(entry.entry_date).toLocaleDateString("en-IN", { weekday: "long" });
            const started = entry.task != null && !["PENDING", "ASSIGNED", "CANCELLED"].includes(entry.task.status);
            const locked = (role === "CLIENT" && started) || readOnly;
            const lockedTitle = readOnly ? "View only" : undefined;
            // Videos the agency's team added show in their own colour (owner request 2026-11-26).
            const rowClass = [entry.no_post ? "no-reel" : "", entry.added_by_team ? "team" : ""].join(" ").trim();
            return (
              <tr
                key={entry.id}
                className={rowClass || undefined}
                title={entry.added_by_team ? `Added by ${entry.created_by_name} (team)` : undefined}
              >
                <EditCell
                  value={entry.entry_date}
                  display={sheetDate(entry.entry_date)}
                  type="date"
                  disabled={locked}
                  disabledTitle={lockedTitle}
                  className="date"
                  onSave={(value) => value && onEdit(entry, "entry_date", value)}
                />
                <td className="sheet-cell muted">Week-{week}</td>
                <td className="sheet-cell muted">{day}</td>
                {showClient && <td className="sheet-cell muted">{entry.client.name}</td>}
                {entry.no_post ? (
                  <td className="sheet-no-reel" colSpan={MERGED}>
                    No Reel
                  </td>
                ) : (
                  <>
                    <EditCell
                      value={entry.title}
                      disabled={locked}
                      disabledTitle={lockedTitle}
                      className="topic"
                      onSave={(value) => value && onEdit(entry, "title", value)}
                    />
                    <LinkCell
                      value={entry.reference_url}
                      label={`Reference video: ${entry.title}`}
                      readOnly={readOnly}
                      onSave={(value) => onEdit(entry, "reference_url", value)}
                    />
                    <TickCell
                      on={entry.recorded}
                      label={`Recorded: ${entry.title}`}
                      disabled={readOnly}
                      onToggle={() => onToggle(entry, "recorded")}
                    />
                    <TickCell
                      on={entry.script_ready}
                      label={`Script ready: ${entry.title}`}
                      disabled={readOnly}
                      onToggle={() => onToggle(entry, "script_ready")}
                    />
                    <TickCell
                      on={entry.edited}
                      label={`Edited: ${entry.title}`}
                      title={role === "ADMIN" ? "Edited" : "Ticks itself when the video is approved"}
                      disabled={role !== "ADMIN"}
                      onToggle={() => onToggle(entry, "edited")}
                    />
                    <TickCell
                      on={entry.posted_instagram}
                      label={`Posted on Instagram: ${entry.title}`}
                      disabled={readOnly}
                      onToggle={() => onToggle(entry, "posted_instagram")}
                    />
                    <TickCell
                      on={entry.posted_youtube}
                      label={`Posted on YouTube: ${entry.title}`}
                      disabled={readOnly}
                      onToggle={() => onToggle(entry, "posted_youtube")}
                    />
                    <LinkCell
                      value={entry.script_url}
                      label={`Script: ${entry.title}`}
                      readOnly={readOnly}
                      onSave={(value) => onEdit(entry, "script_url", value)}
                    />
                    <LinkCell
                      value={entry.pdf_url}
                      label={`PDF: ${entry.title}`}
                      readOnly={readOnly}
                      onSave={(value) => onEdit(entry, "pdf_url", value)}
                    />
                  </>
                )}
                {showTicket && (
                  <td className="sheet-cell ticket">
                    {entry.task ? (
                      <Link
                        href={`/tasks?task=${entry.task.id}`}
                        className={`sheet-ticket ${entry.task.status.toLowerCase()}`}
                      >
                        {entry.task.code}
                      </Link>
                    ) : entry.no_post ? null : (
                      <span className="sheet-placeholder">No ticket</span>
                    )}
                  </td>
                )}
                <td className="sheet-cell more">
                  {!readOnly && (
                    <button type="button" aria-label={`Open ${entry.title}`} onClick={() => onOpen(entry)}>
                      <MoreHorizontal />
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
          {canAdd && (
            <tr className="sheet-new">
              <td className="sheet-cell date">
                <LooplessDate
                  value={draft.entry_date || nextDate}
                  onValueChange={(value) => setDraft((current) => ({ ...current, entry_date: value }))}
                  ariaLabel="New row date"
                />
              </td>
              <td className="sheet-cell muted" colSpan={2 + (showClient ? 1 : 0)}>
                {!readOnly && (
                  <label className="sheet-no-reel-toggle">
                    <input
                      type="checkbox"
                      checked={draft.no_post}
                      onChange={(event) => setDraft((current) => ({ ...current, no_post: event.target.checked }))}
                    />
                    No Reel
                  </label>
                )}
              </td>
              <td className="sheet-cell topic" colSpan={MERGED}>
                <div className="sheet-new-topic">
                  {!draft.no_post && (
                    <LooplessSelect
                      value={draft.service_id}
                      ariaLabel="Service for the new row"
                      onValueChange={(value) => {
                        setDraft((current) => ({ ...current, service_id: value }));
                        setHint("");
                      }}
                      options={[
                        { value: "", label: "Service *" },
                        ...services.map((item) => ({ value: item.id, label: item.name })),
                      ]}
                    />
                  )}
                  <input
                    aria-label="New video topic"
                    placeholder={
                      draft.no_post
                        ? "No reel on this day: press Enter"
                        : "Type a video topic and press Enter (add links with the … button)"
                    }
                    value={draft.title}
                    disabled={adding}
                    onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
                    onKeyDown={(event) => event.key === "Enter" && void add()}
                  />
                </div>
                {hint && <small className="sheet-new-hint">{hint}</small>}
              </td>
              {showTicket && <td className="sheet-cell" />}
              <td className="sheet-cell more">
                <button type="button" aria-label="Add row" disabled={adding} onClick={() => void add()}>
                  +
                </button>
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {rows.length === 0 && <p className="sheet-empty">No rows yet. Type the first video topic in the row above.</p>}
    </div>
  );
}
