// Chat (Phase 14): shapes returned by /chat (backend/app/schemas/chat.py) and small helpers.

export type ChatRole = "ADMIN" | "MANAGER" | "EMPLOYEE" | "CLIENT";
export type ChatStatus = "AVAILABLE" | "BUSY" | "AWAY" | "OFFLINE";

export type ChatPerson = {
  id: string;
  name: string;
  role: ChatRole;
  image: string | null;
  online: boolean;
  status: ChatStatus;
};

export type ChatMember = ChatPerson & { last_read_at: string | null };

export type Conversation = {
  id: string;
  type: "DIRECT" | "GROUP" | "CLIENT";
  title: string;
  client_id: string | null;
  client_name: string | null;
  created_by_id: string;
  last_message: { id: string; sender_id: string; sender_name: string; preview: string; created_at: string } | null;
  unread: number;
  members: ChatMember[];
  created_at: string;
};

export type ChatAttachment = { id: string; file_name: string; mime_type: string; size_bytes: number };

export type ChatMessage = {
  id: string;
  conversation_id: string;
  sender: ChatPerson;
  body: string;
  reply_to: { id: string; sender_name: string; preview: string } | null;
  attachments: ChatAttachment[];
  edited: boolean;
  deleted: boolean;
  created_at: string;
};

export const STATUS_LABELS: Record<ChatStatus, string> = {
  AVAILABLE: "Available",
  BUSY: "Busy",
  AWAY: "Away",
  OFFLINE: "Offline",
};

export const ROLE_LABELS: Record<ChatRole, string> = {
  ADMIN: "Admin",
  MANAGER: "Manager",
  EMPLOYEE: "Employee",
  CLIENT: "Client",
};

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? (parts[parts.length - 1][0] ?? "") : "")).toUpperCase() || "?";
}

export function clock(value: string): string {
  return new Date(value).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

/** Today: the time; this week: the day; otherwise the date. */
export function listTime(value: string): string {
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return clock(value);
  const days = (now.getTime() - date.getTime()) / 86_400_000;
  if (days < 6) return date.toLocaleDateString("en-IN", { weekday: "short" });
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function dayLabel(value: string): string {
  const date = new Date(value);
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === now.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export async function chatApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/chat${path}`, { cache: "no-store", ...init });
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]
          ? String((detail[0] as { msg: string }).msg).replace(/^Value error, /, "")
          : "Something went wrong. Please try again.",
    );
  }
  return body as T;
}

export function jsonBody(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
