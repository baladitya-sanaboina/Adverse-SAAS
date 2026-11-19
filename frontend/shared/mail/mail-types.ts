/*
 * Adverse Mail (owner requests 2026-11-15): shapes, the API helper and small formatters shared by
 * the mail tab and the topbar mail button.
 */
export type Role = "ADMIN" | "MANAGER" | "EMPLOYEE" | "CLIENT";
export type Person = { id: string; name: string; role: Role; image?: string | null };
export type MailFile = { id: string; file_name: string; mime_type: string; size_bytes: number };
export type MailStatus = "SENT" | "SCHEDULED" | "DRAFT";
export type Priority = "LOW" | "NORMAL" | "HIGH" | "URGENT";
export type TicketStatus = "OPEN" | "IN_PROGRESS" | "CLOSED";

export type MailItem = {
  id: string;
  thread_id: string;
  reply_to_id: string | null;
  kind: string;
  subject: string;
  preview: string;
  body: string;
  link: string;
  created_at: string;
  sender: Person | null;
  recipients: Person[];
  cc: Person[];
  bcc: Person[];
  read: boolean;
  mine: boolean;
  starred: boolean;
  trashed: boolean;
  status: MailStatus;
  scheduled_at: string | null;
  attachments: MailFile[];
  /** App mails: how the mail is laid out (owner request 2026-11-19). */
  card?: MailCard | null;
};

export type MailCard = {
  title: string;
  lines: string[];
  rows: { label: string; value: string }[];
  table: string[][];
  action: string | null;
  note: string | null;
};

export type Ticket = {
  id: string;
  number: number;
  code: string;
  thread_id: string;
  message_id: string | null;
  subject: string;
  priority: Priority;
  status: TicketStatus;
  raised_by: Person | null;
  assignee: Person | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  last_at: string | null;
  count: number;
  can_manage: boolean;
};

export type Conversation = {
  thread_id: string;
  message_id: string;
  subject: string;
  preview: string;
  created_at: string;
  sender: Person | null;
  to: Person[];
  participants: string[];
  count: number;
  unread: boolean;
  starred: boolean;
  has_files: boolean;
  kind: string;
  status: MailStatus;
  scheduled_at: string | null;
  mine: boolean;
  ticket: Ticket | null;
};

export type Counts = {
  inbox: number;
  updates: number;
  total: number;
  drafts: number;
  scheduled: number;
  tickets_open: number;
};
export type ListResponse = {
  items: Conversation[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  unread: Counts;
};
export type MeetingCard = {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  video: boolean;
  conversation_id: string | null;
  location: string;
  owner: Person;
  attendees: { person: Person; response: "PENDING" | "YES" | "NO" | "MAYBE" }[];
  my_response: "PENDING" | "YES" | "NO" | "MAYBE" | null;
};
export type Thread = {
  thread_id: string;
  subject: string;
  items: MailItem[];
  ticket: Ticket | null;
  event?: MeetingCard | null; // a meeting planned from this conversation (staff calendar)
};

export const ROLE_LABEL: Record<Role, string> = {
  ADMIN: "Admin",
  MANAGER: "Manager",
  EMPLOYEE: "Employee",
  CLIENT: "Client",
};
export const PRIORITY_LABEL: Record<Priority, string> = {
  LOW: "Low",
  NORMAL: "Normal",
  HIGH: "High",
  URGENT: "Urgent",
};
export const STATUS_LABEL: Record<TicketStatus, string> = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  CLOSED: "Closed",
};

// The mail tab is one named window: every mail link reuses it instead of opening many tabs.
export const MAIL_WINDOW = "adverse-mail";

export function openMail(path = "/mail"): void {
  const opened = window.open(path, MAIL_WINDOW);
  opened?.focus();
}

export async function mailApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/mail${path}`, { cache: "no-store", ...init });
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]
          ? String((detail[0] as { msg: string }).msg)
          : "Something went wrong. Please try again.",
    );
  }
  return body as T;
}

export function utc(value: string): Date {
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
}

/** Gmail-style list time: 10:32 am today, 14 Nov this year, 14/11/25 before. */
export function shortTime(value: string): string {
  const date = utc(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  }
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

export function fullTime(value: string): string {
  return utc(value).toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function initialsOf(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}

const PALETTE = ["#0876ed", "#2fa66a", "#c2414f", "#8a5cf6", "#d97706", "#0e9f9a", "#db2777", "#4b5563"];
export function colourFor(id: string): string {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}
