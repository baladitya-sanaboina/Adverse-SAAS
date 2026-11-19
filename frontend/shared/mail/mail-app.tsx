"use client";

/*
 * Adverse Mail (owner requests 2026-11-15): the internal mailbox in its own tab, laid out like
 * Gmail, with no app sidebar or topbar. The logo goes back to the dashboard.
 *
 * Folders (Inbox with Primary / Updates, Starred, Sent, Scheduled, Drafts, Tickets, All mail,
 * Trash) list conversations. A conversation opens in place with Reply / Reply all / Forward.
 * Compose has To, Cc and Bcc, files, drafts that save themselves, Undo send, Schedule send, and
 * "Raise a ticket" (goes to the admins, who assign it and move it Open, In progress, Closed).
 * Who may write to whom is decided by the server: clients only with the admins.
 * Keyboard: c compose, / search, j k move, o open, u back, e archive, # delete, r reply,
 * a reply all, f forward, s star, Shift+I read, Shift+U unread, ? help.
 */
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import {
  Archive,
  ArchiveRestore,
  ArrowLeft,
  ArrowRight,
  CalendarClock,
  CalendarDays,
  CalendarPlus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  ClipboardList,
  Clock3,
  Download,
  ExternalLink,
  FileText,
  Forward,
  Inbox,
  Keyboard,
  LifeBuoy,
  Mail,
  MailOpen,
  Maximize2,
  Menu,
  Minimize2,
  Minus,
  Moon,
  Paperclip,
  Printer,
  Receipt,
  RefreshCw,
  Reply,
  ReplyAll,
  Search,
  SendHorizontal,
  SquarePen,
  Star,
  SunMedium,
  Ticket as TicketIcon,
  Trash2,
  Undo2,
  Wallet,
  X,
} from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { getBrandLogo } from "@/lib/branding";
import { subscribeRealtime } from "../realtime/realtime";
import { startCall } from "../chat/call-manager";
import { OrbitLoader } from "../branding/orbit-loader";
import {
  PRIORITY_LABEL,
  ROLE_LABEL,
  STATUS_LABEL,
  colourFor,
  fullTime,
  initialsOf,
  mailApi,
  shortTime,
  sizeLabel,
  type Conversation,
  type Counts,
  type ListResponse,
  type MeetingCard,
  type MailCard,
  type MailItem,
  type Person,
  type Priority,
  type Role,
  type Thread,
  type Ticket,
  type TicketStatus,
} from "./mail-types";
import "../styles/mail-app.css";
import { LooplessDate } from "@/components/foundation/loopless-date";

type Folder = "INBOX" | "UPDATES" | "STARRED" | "SENT" | "SCHEDULED" | "DRAFTS" | "TICKETS" | "ALL" | "TRASH";
type Action = "archive" | "inbox" | "trash" | "restore" | "purge" | "star" | "unstar" | "read" | "unread";

type Draft = {
  key: string;
  draftId: string | null;
  mode: "new" | "reply" | "forward";
  to: Person[];
  cc: Person[];
  bcc: Person[];
  showCc: boolean;
  showBcc: boolean;
  subject: string;
  body: string;
  files: File[];
  replyTo: string | null;
  forwardOf: string | null;
  ticket: Priority | null;
  meeting: { day: string; start: string; end: string; video: boolean } | null;
};

type Toast = { id: number; text: string; undo?: () => void; open?: string; tone?: "error" };

const FOLDERS: { key: Folder; label: string; icon: typeof Inbox }[] = [
  { key: "INBOX", label: "Inbox", icon: Inbox },
  { key: "STARRED", label: "Starred", icon: Star },
  { key: "SENT", label: "Sent", icon: SendHorizontal },
  { key: "SCHEDULED", label: "Scheduled", icon: Clock3 },
  { key: "DRAFTS", label: "Drafts", icon: FileText },
  { key: "TICKETS", label: "Tickets", icon: LifeBuoy },
  { key: "ALL", label: "All mail", icon: Mail },
  { key: "TRASH", label: "Trash", icon: Trash2 },
];
const FOLDER_NAME: Record<Folder, string> = {
  INBOX: "Inbox",
  UPDATES: "Updates",
  STARRED: "Starred",
  SENT: "Sent",
  SCHEDULED: "Scheduled",
  DRAFTS: "Drafts",
  TICKETS: "Tickets",
  ALL: "All mail",
  TRASH: "Trash",
};
const PAGE_SIZE = 30;
const UNDO_SECONDS = 5;
const EMPTY_COUNTS: Counts = { inbox: 0, updates: 0, total: 0, drafts: 0, scheduled: 0, tickets_open: 0 };

let draftSeq = 0;
function newDraft(partial: Partial<Draft> = {}): Draft {
  draftSeq += 1;
  return {
    key: `d${Date.now()}-${draftSeq}`,
    draftId: null,
    mode: "new",
    to: [],
    cc: [],
    bcc: [],
    showCc: false,
    showBcc: false,
    subject: "",
    body: "",
    files: [],
    replyTo: null,
    forwardOf: null,
    ticket: null,
    meeting: null,
    ...partial,
  };
}

function typing(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  return (
    element.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName) ||
    Boolean(element.closest("[role='listbox'], [role='dialog'] input"))
  );
}

/** Text with links that can be clicked; quoted lines (> ...) shown as a quote. */
const CARD_KINDS: Record<string, { label: string; icon: typeof Mail }> = {
  TASK: { label: "Task update", icon: ClipboardList },
  PAYMENT: { label: "Payment", icon: Wallet },
  INVOICE: { label: "Invoice", icon: Receipt },
  BUDGET: { label: "Budget", icon: Wallet },
  ADVANCE: { label: "Advance", icon: Wallet },
  CALENDAR: { label: "Calendar", icon: CalendarDays },
  MEETING: { label: "Meeting", icon: CalendarDays },
  TICKET: { label: "Ticket", icon: LifeBuoy },
};
const MONEY_LABELS = ["amount", "total", "balance", "amount due", "balance due", "advance left now"];
const ROW = /^([A-Z][A-Za-z /&'().-]{1,28}):\s+(\S.{0,160})$/;

/** Older app mails were saved as plain text: lay them out as a card too (2026-11-19). */
function cardFromText(item: MailItem): MailCard {
  const lines: string[] = [];
  const rows: { label: string; value: string }[] = [];
  for (const raw of item.body.split("\n")) {
    const text = raw.trim();
    if (!text) continue;
    const match = ROW.exec(text);
    if (match && rows.length < 12) rows.push({ label: match[1], value: match[2] });
    else lines.push(text);
  }
  const money = rows.find((row) => MONEY_LABELS.includes(row.label.toLowerCase()));
  return {
    title: item.subject,
    lines,
    rows: money ? rows.filter((row) => row !== money) : rows,
    table: [],
    action: item.link ? "Open in Adverse" : null,
    note: null,
    highlight: money ?? null,
    status: null,
  };
}

/** An app mail laid out like a proper mail (owner requests 2026-11-19). */
function MailCardView({ card, kind, onOpen }: { card: MailCard; kind: string; onOpen?: () => void }) {
  const [head, ...rows] = card.table;
  const meta = CARD_KINDS[kind] ?? { label: "Adverse", icon: Mail };
  const Icon = meta.icon;
  return (
    <div className={`mailx-card kind-${kind.toLowerCase()}`}>
      <header className="mailx-card-head">
        <i aria-hidden="true">
          <Icon />
        </i>
        <span>{meta.label}</span>
        {card.status && <em>{card.status}</em>}
      </header>
      <div className="mailx-card-main">
        <h3>{card.title}</h3>
        {card.lines.map((line, index) => (
          <p key={index}>{linkify(line)}</p>
        ))}
        {card.highlight && (
          <div className="mailx-card-highlight">
            <small>{card.highlight.label}</small>
            <strong>{card.highlight.value}</strong>
          </div>
        )}
        {card.rows.length > 0 && (
          <dl className="mailx-card-rows">
            {card.rows.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        )}
        {head && rows.length > 0 && (
          <div className="mailx-card-table">
            <table>
              <thead>
                <tr>
                  {head.map((cell, index) => (
                    <th key={index} scope="col">
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((cell, column) => (
                      <td key={column}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {card.action && onOpen && (
          <button type="button" className="mailx-card-action" onClick={onOpen}>
            {card.action} <ArrowRight aria-hidden="true" />
          </button>
        )}
        {card.note && <small className="mailx-card-note">{card.note}</small>}
      </div>
    </div>
  );
}

function MailBody({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.split("\n");
  let quote: string[] = [];
  const flush = (key: number) => {
    if (quote.length) {
      blocks.push(
        <blockquote key={`q${key}`} className="mailx-quote">
          {linkify(quote.join("\n"))}
        </blockquote>,
      );
      quote = [];
    }
  };
  lines.forEach((line, index) => {
    if (line.startsWith(">")) {
      quote.push(line.replace(/^>\s?/, ""));
      return;
    }
    flush(index);
    blocks.push(
      <span key={index}>
        {linkify(line)}
        {index < lines.length - 1 ? "\n" : ""}
      </span>,
    );
  });
  flush(lines.length);
  return <div className="mailx-body">{blocks}</div>;
}

function linkify(text: string): ReactNode[] {
  const parts = text.split(/(https?:\/\/[^\s<>()]+)/g);
  return parts.map((part, index) =>
    /^https?:\/\//.test(part) ? (
      <a key={index} href={part} target="_blank" rel="noopener noreferrer">
        {part}
      </a>
    ) : (
      part
    ),
  );
}

function Face({ person, size = 36 }: { person: Person | null; size?: number }) {
  const style = { width: size, height: size, fontSize: size * 0.36 };
  if (!person) {
    return (
      <span className="mailx-face app" style={style} aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={getBrandLogo("light", "orbit")} alt="" />
      </span>
    );
  }
  return (
    <span className="mailx-face" style={{ ...style, background: colourFor(person.id) }} aria-hidden="true">
      {person.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={person.image} alt="" />
      ) : (
        initialsOf(person.name)
      )}
    </span>
  );
}

function firstName(person: Person | null, me: string): string {
  if (!person) return "Adverse";
  if (person.id === me) return "me";
  return person.name.split(" ")[0];
}

// ---------------------------------------------------------------------------------------------

export function MailApp({ homeHref = "/dashboard" }: { homeHref?: string }) {
  const [me, setMe] = useState<Person | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [folder, setFolder] = useState<Folder>("INBOX");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [list, setList] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [counts, setCounts] = useState<Counts>(EMPTY_COUNTS);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cursor, setCursor] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [openTrash, setOpenTrash] = useState(false);
  const [thread, setThread] = useState<Thread | null>(null);
  const [compose, setCompose] = useState<Draft | null>(null);
  const [composeSize, setComposeSize] = useState<"normal" | "min" | "max">("normal");
  const [inline, setInline] = useState<Draft | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [tickets, setTickets] = useState<{ items: Ticket[]; counts: Record<string, number> } | null>(null);
  const [ticketFilter, setTicketFilter] = useState<TicketStatus | "">("");
  const [help, setHelp] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [dark, setDark] = useState(false);
  const [scheduling, setScheduling] = useState<{ draft: Draft; inline: boolean } | null>(null);
  const searchBox = useRef<HTMLInputElement>(null);
  const pending = useRef(0);
  const prefill = useRef<string[]>([]);
  const toastSeq = useRef(0);

  const isAdmin = me?.role === "ADMIN";
  const view: "list" | "thread" | "tickets" = openId ? "thread" : folder === "TICKETS" ? "tickets" : "list";

  const toast = useCallback((item: Omit<Toast, "id">, ms = 6000) => {
    toastSeq.current += 1;
    const id = toastSeq.current;
    setToasts((current) => [...current.slice(-2), { ...item, id }]);
    window.setTimeout(() => setToasts((current) => current.filter((entry) => entry.id !== id)), ms);
    return id;
  }, []);
  const fail = useCallback(
    (reason: unknown) =>
      toast({ text: reason instanceof Error ? reason.message : "That did not work.", tone: "error" }),
    [toast],
  );

  // -- loading -------------------------------------------------------------------------------

  const loadCounts = useCallback(async () => {
    try {
      setCounts(await mailApi<Counts>("/unread"));
    } catch {
      // Counts stay as they were.
    }
  }, []);

  const loadList = useCallback(async () => {
    if (folder === "TICKETS") return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ folder, page: String(page), page_size: String(PAGE_SIZE) });
      if (search) params.set("q", search);
      const result = await mailApi<ListResponse>(`?${params}`);
      setList(result);
      setCounts(result.unread);
      setCursor((current) => Math.min(current, Math.max(0, result.items.length - 1)));
    } catch (reason) {
      fail(reason);
    } finally {
      setLoading(false);
    }
  }, [folder, page, search, fail]);

  const loadTickets = useCallback(async () => {
    try {
      const params = ticketFilter ? `?status=${ticketFilter}` : "";
      setTickets(await mailApi(`/tickets${params}`));
    } catch (reason) {
      fail(reason);
    }
  }, [ticketFilter, fail]);

  const loadThread = useCallback(
    async (id: string, trash: boolean) => {
      try {
        const result = await mailApi<Thread>(`/${id}${trash ? "?trash=true" : ""}`);
        setThread(result);
      } catch (reason) {
        fail(reason);
        setOpenId(null);
      }
    },
    [fail],
  );

  // First load: who I am, who I can write to, and the folder / mail from the link.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDark(document.documentElement.classList.contains("dark"));
      const params = new URLSearchParams(window.location.search);
      const wanted = (params.get("f") ?? "").toUpperCase() as Folder;
      if (wanted && wanted in FOLDER_NAME) setFolder(wanted);
      const message = params.get("m");
      if (message) setOpenId(message);
      if (params.get("compose") === "ticket") setCompose(newDraft({ ticket: "NORMAL" }));
      else if (params.get("compose")) {
        // ?to=<ids>&subject=… (for example "Email people" from the calendar).
        const wantedTo = (params.get("to") ?? "").split(",").filter(Boolean);
        prefill.current = wantedTo;
        setCompose(newDraft({ subject: params.get("subject") ?? "" }));
      }
      void fetch("/api/chat/people", { cache: "no-store" })
        .then((response) => (response.ok ? response.json() : null))
        .then((body: { me?: Person } | null) => body?.me && setMe(body.me))
        .catch(() => undefined);
      void mailApi<{ people: Person[] }>("/people")
        .then((body) => {
          setPeople(body.people);
          const wanted = prefill.current;
          if (wanted.length) {
            prefill.current = [];
            const chosen = body.people.filter((person) => wanted.includes(person.id));
            setCompose((current) => (current ? { ...current, to: chosen } : current));
          }
        })
        .catch(() => undefined);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void (folder === "TICKETS" ? loadTickets() : loadList()), 0);
    return () => window.clearTimeout(timer);
  }, [folder, loadList, loadTickets]);

  useEffect(() => {
    if (!openId) return;
    const timer = window.setTimeout(() => void loadThread(openId, openTrash), 0);
    return () => window.clearTimeout(timer);
  }, [openId, openTrash, loadThread]);

  // The link follows what is open, so a reload or a shared link lands in the same place.
  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("f", folder.toLowerCase());
    if (openId) url.searchParams.set("m", openId);
    else url.searchParams.delete("m");
    url.searchParams.delete("compose");
    window.history.replaceState(null, "", url);
  }, [folder, openId]);

  useEffect(() => {
    const unread = counts.inbox;
    document.title = `${FOLDER_NAME[folder]}${unread ? ` (${unread})` : ""} · Adverse Mail`;
  }, [folder, counts.inbox]);

  // Live: new mail and reads elsewhere refresh the list (debounced).
  useEffect(() => {
    let timer: number | undefined;
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type !== "mail.new" && event.type !== "mail.read") return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        void loadCounts();
        if (folder === "TICKETS") void loadTickets();
        else void loadList();
      }, 400);
    });
    return () => {
      window.clearTimeout(timer);
      unsubscribe();
    };
  }, [folder, loadCounts, loadList, loadTickets]);

  // Do not lose a mail that is still in its Undo window.
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (pending.current > 0) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  // -- navigation ----------------------------------------------------------------------------

  const goFolder = useCallback((next: Folder) => {
    setFolder(next);
    setPage(1);
    setSelected(new Set());
    setCursor(0);
    setOpenId(null);
    setThread(null);
    setInline(null);
    setDrawer(false);
    if (next !== "ALL") {
      setSearch("");
      setQuery("");
    }
  }, []);

  const openConversation = useCallback(
    (item: Conversation) => {
      if (item.status === "DRAFT") {
        void mailApi<Thread>(`/${item.message_id}`)
          .then((result) => {
            const draft = result.items[0];
            if (!draft) return;
            setCompose(
              newDraft({
                draftId: draft.id,
                to: draft.recipients,
                cc: draft.cc,
                bcc: draft.bcc,
                showCc: draft.cc.length > 0,
                showBcc: draft.bcc.length > 0,
                subject: draft.subject,
                body: draft.body,
                replyTo: draft.reply_to_id,
                mode: draft.reply_to_id ? "reply" : "new",
              }),
            );
            setComposeSize("normal");
          })
          .catch(fail);
        return;
      }
      setThread(null);
      setInline(null);
      setOpenTrash(folder === "TRASH");
      setOpenId(item.message_id);
    },
    [folder, fail],
  );

  const back = useCallback(() => {
    setOpenId(null);
    setThread(null);
    setInline(null);
    void (folder === "TICKETS" ? loadTickets() : loadList());
  }, [folder, loadList, loadTickets]);

  // -- actions -------------------------------------------------------------------------------

  const runAction = useCallback(async (action: Action, threads: string[]) => {
    const result = await mailApi<{ changed: number; unread: Counts }>("/actions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_ids: threads, action }),
    });
    setCounts(result.unread);
    return result;
  }, []);

  const act = useCallback(
    async (action: Action, threads: string[], quiet = false) => {
      if (!threads.length) return;
      try {
        await runAction(action, threads);
        const word: Partial<Record<Action, string>> = {
          archive: "Archived",
          trash: "Moved to Trash",
          restore: "Moved back",
          inbox: "Moved to Inbox",
          purge: "Deleted forever",
        };
        const undo: Partial<Record<Action, Action>> = { archive: "inbox", trash: "restore" };
        if (!quiet && word[action]) {
          const reverse = undo[action];
          toast({
            text: `${word[action]}${threads.length > 1 ? ` · ${threads.length} conversations` : ""}`,
            undo: reverse
              ? () => {
                  void runAction(reverse, threads)
                    .then(() => void loadList())
                    .catch(fail);
                }
              : undefined,
          });
        }
        setSelected(new Set());
        if (["archive", "trash", "restore", "purge", "inbox"].includes(action) && openId) back();
        else void loadList();
      } catch (reason) {
        fail(reason);
      }
    },
    [runAction, toast, fail, loadList, openId, back],
  );

  const toggleStar = useCallback(
    (threadId: string, starred: boolean) => {
      setList((current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) => (item.thread_id === threadId ? { ...item, starred: !starred } : item)),
            }
          : current,
      );
      void act(starred ? "unstar" : "star", [threadId], true);
    },
    [act],
  );

  // -- composing -----------------------------------------------------------------------------

  const startCompose = useCallback((partial: Partial<Draft> = {}) => {
    setCompose(newDraft(partial));
    setComposeSize("normal");
  }, []);

  const replyDraft = useCallback(
    (message: MailItem, kind: "reply" | "all" | "forward"): Draft => {
      const mine = me?.id ?? "";
      const allowed = new Set(people.map((person) => person.id));
      if (kind === "forward") {
        const header = [
          "",
          "",
          "---------- Forwarded message ---------",
          `From: ${message.sender?.name ?? "Adverse"}`,
          `Date: ${fullTime(message.created_at)}`,
          `Subject: ${message.subject}`,
          `To: ${message.recipients.map((person) => person.name).join(", ")}`,
          "",
          message.body,
        ].join("\n");
        return newDraft({
          mode: "forward",
          subject: message.subject.toLowerCase().startsWith("fwd:") ? message.subject : `Fwd: ${message.subject}`,
          body: header,
          forwardOf: message.id,
        });
      }
      const sender = message.sender && message.sender.id !== mine ? [message.sender] : [];
      let to = message.mine ? message.recipients : sender;
      let cc: Person[] = [];
      if (kind === "all") {
        const everyone = [...(message.sender ? [message.sender] : []), ...message.recipients, ...message.cc];
        const others = everyone.filter(
          (person, index, all) => person.id !== mine && all.findIndex((p) => p.id === person.id) === index,
        );
        to = message.mine ? message.recipients : sender;
        cc = others.filter((person) => !to.some((p) => p.id === person.id));
      }
      // Only people I may write to (a manager replying all never reaches a client).
      to = to.filter((person) => allowed.has(person.id));
      cc = cc.filter((person) => allowed.has(person.id));
      return newDraft({
        mode: "reply",
        to,
        cc,
        showCc: cc.length > 0,
        subject: message.subject.toLowerCase().startsWith("re:") ? message.subject : `Re: ${message.subject}`,
        replyTo: message.id,
      });
    },
    [me, people],
  );

  const deliver = useCallback(async (draft: Draft, when: Date | null) => {
    const form = new FormData();
    draft.to.forEach((person) => form.append("to", person.id));
    draft.cc.forEach((person) => form.append("cc", person.id));
    draft.bcc.forEach((person) => form.append("bcc", person.id));
    form.append("subject", draft.subject);
    form.append("body", draft.body);
    if (draft.replyTo) form.append("reply_to_id", draft.replyTo);
    if (draft.forwardOf) form.append("forward_of_id", draft.forwardOf);
    if (draft.draftId) form.append("draft_id", draft.draftId);
    if (when) form.append("scheduled_at", when.toISOString());
    if (draft.ticket && draft.mode === "new") form.append("ticket_priority", draft.ticket);
    draft.files.forEach((file) => form.append("files", file));
    const result = await mailApi<Thread>("", { method: "POST", body: form });
    if (draft.meeting && draft.mode === "new" && !when) {
      // The mail is the invitation: the calendar event links to this conversation.
      const meeting = draft.meeting;
      const start = new Date(`${meeting.day}T${meeting.start}`);
      let end = new Date(`${meeting.day}T${meeting.end}`);
      if (end <= start) end = new Date(end.getTime() + 864e5);
      await fetch("/api/agenda/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: draft.subject.trim() || "Meeting",
          notes: draft.body.slice(0, 2000),
          starts_at: start.toISOString(),
          ends_at: end.toISOString(),
          video: meeting.video,
          attendee_ids: [...draft.to, ...draft.cc, ...draft.bcc].map((person) => person.id),
          mail_thread_id: result.thread_id,
          invite: false,
        }),
      }).then(async (response) => {
        if (!response.ok) {
          const body = (await response.json().catch(() => ({}))) as { detail?: string };
          throw new Error(
            `The mail went, but the meeting was not added: ${body.detail ?? "please add it in the calendar."}`,
          );
        }
      });
    }
    return result;
  }, []);

  const send = useCallback(
    (draft: Draft, when: Date | null, fromInline: boolean) => {
      if (fromInline) setInline(null);
      else setCompose(null);
      pending.current += 1;
      let undone = false;
      const label = when
        ? `Scheduled for ${when.toLocaleString("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}`
        : draft.ticket && draft.mode === "new"
          ? "Raising the ticket…"
          : "Sending…";
      const toastId = toast(
        {
          text: label,
          undo: () => {
            undone = true;
            pending.current -= 1;
            if (fromInline) setInline(draft);
            else {
              setCompose(draft);
              setComposeSize("normal");
            }
          },
        },
        UNDO_SECONDS * 1000,
      );
      window.setTimeout(() => {
        if (undone) return;
        setToasts((current) => current.filter((entry) => entry.id !== toastId));
        void deliver(draft, when)
          .then((result) => {
            const first = result.items[result.items.length - 1];
            toast({
              text: when
                ? "Mail scheduled"
                : result.ticket
                  ? `Ticket ${result.ticket.code} raised`
                  : draft.meeting
                    ? "Sent, and the meeting is on everyone's calendar"
                    : "Message sent",
              open: first?.id,
            });
            if (openId && result.thread_id === thread?.thread_id) void loadThread(openId, false);
            void loadList();
            void loadCounts();
          })
          .catch((reason) => {
            fail(reason);
            if (fromInline) setInline(draft);
            else setCompose(draft);
          })
          .finally(() => {
            pending.current -= 1;
          });
      }, UNDO_SECONDS * 1000);
    },
    [deliver, toast, fail, openId, thread, loadThread, loadList, loadCounts],
  );

  const discard = useCallback(
    (draft: Draft, fromInline: boolean) => {
      if (fromInline) setInline(null);
      else setCompose(null);
      if (draft.draftId) {
        void mailApi(`/drafts/${draft.draftId}`, { method: "DELETE" })
          .then(() => {
            void loadCounts();
            if (folder === "DRAFTS") void loadList();
          })
          .catch(() => undefined);
      }
      toast({ text: "Draft discarded" }, 3000);
    },
    [toast, loadCounts, loadList, folder],
  );

  // -- keyboard ------------------------------------------------------------------------------

  const items = useMemo(() => list?.items ?? [], [list]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      if (typing(event.target)) return;
      const current = items[cursor];
      const latest = thread?.items[thread.items.length - 1];
      const key = event.key;
      if (key === "?") return setHelp(true);
      if (key === "Escape") {
        if (help) return setHelp(false);
        if (openId) return back();
        return;
      }
      if (key === "c") {
        event.preventDefault();
        return startCompose();
      }
      if (key === "/") {
        event.preventDefault();
        return searchBox.current?.focus();
      }
      if (view === "list") {
        if (key === "j") return setCursor((value) => Math.min(value + 1, items.length - 1));
        if (key === "k") return setCursor((value) => Math.max(value - 1, 0));
        if ((key === "o" || key === "Enter") && current) return openConversation(current);
        if (key === "x" && current)
          return setSelected((value) => {
            const next = new Set(value);
            if (next.has(current.thread_id)) next.delete(current.thread_id);
            else next.add(current.thread_id);
            return next;
          });
      }
      const targets =
        view === "thread" && thread
          ? [thread.thread_id]
          : selected.size
            ? [...selected]
            : current
              ? [current.thread_id]
              : [];
      if (key === "e" && folder !== "TRASH") return void act("archive", targets);
      if (key === "#") return void act(folder === "TRASH" ? "purge" : "trash", targets);
      if (key === "s" && view === "list" && current) return toggleStar(current.thread_id, current.starred);
      if (key === "I") return void act("read", targets);
      if (key === "U") return void act("unread", targets);
      if (key === "u" && openId) return back();
      if (view === "thread" && latest && latest.status === "SENT") {
        if (key === "r") return setInline(replyDraft(latest, "reply"));
        if (key === "a") return setInline(replyDraft(latest, "all"));
        if (key === "f") return setInline(replyDraft(latest, "forward"));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    items,
    cursor,
    thread,
    help,
    openId,
    view,
    selected,
    folder,
    act,
    back,
    startCompose,
    openConversation,
    toggleStar,
    replyDraft,
  ]);

  // -- theme ---------------------------------------------------------------------------------

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("loopless-theme", next ? "dark" : "light");
    } catch {
      // Theme just is not remembered.
    }
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    const term = query.trim();
    setSearch(term);
    setPage(1);
    setOpenId(null);
    setThread(null);
    if (term && folder !== "ALL") setFolder("ALL");
  }

  // -- render --------------------------------------------------------------------------------

  const allChecked = items.length > 0 && items.every((item) => selected.has(item.thread_id));
  const someChecked = selected.size > 0;
  const from = list && list.total ? (list.page - 1) * list.page_size + 1 : 0;
  const to = list ? Math.min(list.total, list.page * list.page_size) : 0;
  const inboxView = folder === "INBOX" || folder === "UPDATES";

  return (
    <div className={`mailx${drawer ? " drawer-open" : ""}`}>
      <header className="mailx-top">
        <button
          type="button"
          className="mailx-icon mailx-menu"
          aria-label="Folders"
          onClick={() => setDrawer((open) => !open)}
        >
          <Menu />
        </button>
        <a className="mailx-brand" href={homeHref} title="Back to Adverse">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={getBrandLogo("light", "wordmark")} alt="Adverse" />
          <span>Mail</span>
        </a>
        <form className="mailx-search" role="search" onSubmit={submitSearch}>
          <Search aria-hidden="true" />
          <input
            ref={searchBox}
            value={query}
            placeholder="Search mail"
            aria-label="Search mail"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setQuery("");
                setSearch("");
                (event.target as HTMLInputElement).blur();
              }
            }}
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => {
                setQuery("");
                setSearch("");
              }}
            >
              <X />
            </button>
          )}
        </form>
        <div className="mailx-top-actions">
          <button
            type="button"
            className="mailx-icon"
            aria-label="Keyboard shortcuts"
            title="Keyboard shortcuts (?)"
            onClick={() => setHelp(true)}
          >
            <Keyboard />
          </button>
          <button
            type="button"
            className="mailx-icon"
            aria-label={dark ? "Light mode" : "Dark mode"}
            onClick={toggleTheme}
          >
            {dark ? <SunMedium /> : <Moon />}
          </button>
          {me && (
            <span className="mailx-me" title={`${me.name} · ${ROLE_LABEL[me.role]}`}>
              <Face person={me} size={34} />
            </span>
          )}
        </div>
      </header>

      <aside className="mailx-side" aria-label="Folders">
        <button type="button" className="mailx-compose-btn" onClick={() => startCompose()}>
          <SquarePen aria-hidden="true" /> Compose
        </button>
        <nav>
          {FOLDERS.map(({ key, label, icon: Icon }) => {
            const active = folder === key || (key === "INBOX" && folder === "UPDATES");
            const count =
              key === "INBOX"
                ? counts.inbox + counts.updates
                : key === "DRAFTS"
                  ? counts.drafts
                  : key === "SCHEDULED"
                    ? counts.scheduled
                    : key === "TICKETS"
                      ? counts.tickets_open
                      : 0;
            return (
              <button
                key={key}
                type="button"
                className={`mailx-folder${active ? " active" : ""}${key === "INBOX" && count ? " bold" : ""}`}
                aria-current={active ? "page" : undefined}
                onClick={() => goFolder(key)}
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
                {count > 0 && <b>{count > 999 ? "999+" : count}</b>}
              </button>
            );
          })}
        </nav>
        <button type="button" className="mailx-side-ticket" onClick={() => startCompose({ ticket: "NORMAL" })}>
          <TicketIcon aria-hidden="true" />
          <span>
            <strong>Raise a ticket</strong>
            <small>Report a problem to the admin</small>
          </span>
        </button>
        {me && me.role !== "CLIENT" && (
          <button type="button" className="mailx-side-link" onClick={() => openApp("/agenda")}>
            <CalendarDays aria-hidden="true" /> Calendar
          </button>
        )}
        <p className="mailx-side-note">
          {me?.role === "CLIENT"
            ? "Mail here goes to the Adverse team."
            : "Mail inside Adverse. Clients can only write to the admin."}
        </p>
      </aside>
      {drawer && (
        <button type="button" className="mailx-scrim" aria-label="Close folders" onClick={() => setDrawer(false)} />
      )}

      <main className="mailx-main">
        {view === "tickets" ? (
          <TicketsView
            data={tickets}
            filter={ticketFilter}
            onFilter={(value) => setTicketFilter(value)}
            onOpen={(ticket) => {
              if (!ticket.message_id) return;
              setOpenTrash(false);
              setOpenId(ticket.message_id);
            }}
            onRaise={() => startCompose({ ticket: "NORMAL" })}
            onRefresh={() => void loadTickets()}
          />
        ) : view === "thread" ? (
          <ThreadView
            thread={thread}
            me={me}
            people={people}
            isAdmin={Boolean(isAdmin)}
            inTrash={openTrash}
            inline={inline}
            onBack={back}
            onAct={(action) => thread && void act(action, [thread.thread_id])}
            onReply={(message, kind) => setInline(replyDraft(message, kind))}
            onInlineChange={setInline}
            onInlineSend={(draft) => send(draft, null, true)}
            onInlineSchedule={(draft) => setScheduling({ draft, inline: true })}
            onInlineDiscard={(draft) => discard(draft, true)}
            onUnschedule={(message) =>
              void mailApi(`/${message.id}/unschedule`, { method: "POST" })
                .then(() => {
                  toast({ text: "Send cancelled. The mail is in Drafts." });
                  back();
                  void loadCounts();
                })
                .catch(fail)
            }
            onTicket={(ticket, change) =>
              void mailApi<Ticket>(`/tickets/${ticket.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(change),
              })
                .then(() => {
                  if (openId) void loadThread(openId, false);
                  void loadCounts();
                })
                .catch(fail)
            }
            onError={fail}
          />
        ) : (
          <section className="mailx-list-wrap" aria-label={FOLDER_NAME[folder]}>
            <div className="mailx-toolbar">
              <label className="mailx-check" title="Select">
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={(element) => {
                    if (element) element.indeterminate = someChecked && !allChecked;
                  }}
                  onChange={() => setSelected(allChecked ? new Set() : new Set(items.map((item) => item.thread_id)))}
                  aria-label="Select all on this page"
                />
              </label>
              <button
                type="button"
                className="mailx-icon"
                aria-label="Refresh"
                title="Refresh"
                onClick={() => void loadList()}
              >
                <RefreshCw className={loading ? "spin" : undefined} />
              </button>
              {someChecked && (
                <BulkActions
                  folder={folder}
                  onAct={(action) => void act(action, [...selected])}
                  onDiscardDrafts={() => {
                    const ids = items.filter((item) => selected.has(item.thread_id)).map((item) => item.message_id);
                    void Promise.all(
                      ids.map((id) => mailApi(`/drafts/${id}`, { method: "DELETE" }).catch(() => undefined)),
                    ).then(() => {
                      setSelected(new Set());
                      toast({ text: "Drafts discarded" }, 3000);
                      void loadList();
                    });
                  }}
                  onUnschedule={() => {
                    const ids = items.filter((item) => selected.has(item.thread_id)).map((item) => item.message_id);
                    void Promise.all(
                      ids.map((id) => mailApi(`/${id}/unschedule`, { method: "POST" }).catch(() => undefined)),
                    ).then(() => {
                      setSelected(new Set());
                      toast({ text: "Send cancelled. The mails are in Drafts." });
                      void loadList();
                    });
                  }}
                />
              )}
              {search && (
                <span className="mailx-search-chip">
                  Results for “{search}”
                  <button
                    type="button"
                    aria-label="Clear search"
                    onClick={() => {
                      setQuery("");
                      setSearch("");
                    }}
                  >
                    <X />
                  </button>
                </span>
              )}
              <span className="mailx-pages">
                {list && list.total > 0 && (
                  <>
                    {from}–{to} of {list.total}
                  </>
                )}
                <button
                  type="button"
                  className="mailx-icon"
                  aria-label="Newer"
                  disabled={!list || list.page <= 1}
                  onClick={() => setPage((value) => value - 1)}
                >
                  <ChevronLeft />
                </button>
                <button
                  type="button"
                  className="mailx-icon"
                  aria-label="Older"
                  disabled={!list || list.page >= list.total_pages}
                  onClick={() => setPage((value) => value + 1)}
                >
                  <ChevronRight />
                </button>
              </span>
            </div>
            {inboxView && !search && (
              <div className="mailx-tabs" role="tablist" aria-label="Inbox">
                <button
                  type="button"
                  role="tab"
                  aria-selected={folder === "INBOX"}
                  className={folder === "INBOX" ? "active" : undefined}
                  onClick={() => goFolder("INBOX")}
                >
                  <Inbox aria-hidden="true" /> Primary
                  {counts.inbox > 0 && <b>{counts.inbox} new</b>}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={folder === "UPDATES"}
                  className={folder === "UPDATES" ? "active" : undefined}
                  onClick={() => goFolder("UPDATES")}
                >
                  <CircleAlert aria-hidden="true" /> Updates
                  {counts.updates > 0 && <b className="updates">{counts.updates} new</b>}
                </button>
              </div>
            )}
            {folder === "TRASH" && items.length > 0 && (
              <p className="mailx-banner">Conversations in Trash stay until you delete them forever.</p>
            )}
            {loading && !list ? (
              <div className="mailx-empty">
                <OrbitLoader size={64} label="Loading mail" />
              </div>
            ) : items.length === 0 ? (
              <EmptyFolder folder={folder} search={search} onCompose={() => startCompose()} />
            ) : (
              <ul className="mailx-rows">
                {items.map((item, index) => (
                  <ConversationRow
                    key={item.thread_id}
                    item={item}
                    me={me?.id ?? ""}
                    folder={folder}
                    focused={index === cursor}
                    checked={selected.has(item.thread_id)}
                    onCheck={() =>
                      setSelected((value) => {
                        const next = new Set(value);
                        if (next.has(item.thread_id)) next.delete(item.thread_id);
                        else next.add(item.thread_id);
                        return next;
                      })
                    }
                    onStar={() => toggleStar(item.thread_id, item.starred)}
                    onOpen={() => {
                      setCursor(index);
                      openConversation(item);
                    }}
                    onAct={(action) => void act(action, [item.thread_id])}
                  />
                ))}
              </ul>
            )}
          </section>
        )}
      </main>

      {compose && (
        <div
          className={`mailx-compose ${composeSize}`}
          role="dialog"
          aria-label={compose.ticket ? "Raise a ticket" : "New message"}
        >
          <header onClick={() => composeSize === "min" && setComposeSize("normal")}>
            <strong>
              {compose.ticket
                ? "Raise a ticket"
                : compose.mode === "forward"
                  ? "Forward"
                  : compose.subject || "New message"}
            </strong>
            <span>
              <button
                type="button"
                aria-label={composeSize === "min" ? "Open" : "Minimise"}
                onClick={(event) => {
                  event.stopPropagation();
                  setComposeSize((value) => (value === "min" ? "normal" : "min"));
                }}
              >
                <Minus />
              </button>
              <button
                type="button"
                aria-label={composeSize === "max" ? "Exit full screen" : "Full screen"}
                onClick={(event) => {
                  event.stopPropagation();
                  setComposeSize((value) => (value === "max" ? "normal" : "max"));
                }}
              >
                {composeSize === "max" ? <Minimize2 /> : <Maximize2 />}
              </button>
              <button
                type="button"
                aria-label="Save and close"
                title="Save and close"
                onClick={(event) => {
                  event.stopPropagation();
                  setCompose(null);
                  if (compose.draftId) toast({ text: "Draft saved" }, 2500);
                }}
              >
                <X />
              </button>
            </span>
          </header>
          {composeSize !== "min" && (
            <Composer
              draft={compose}
              people={people}
              me={me}
              onChange={setCompose}
              onSend={(draft) => send(draft, null, false)}
              onSchedule={(draft) => setScheduling({ draft, inline: false })}
              onDiscard={(draft) => discard(draft, false)}
              onSaved={() => {
                void loadCounts();
                if (folder === "DRAFTS") void loadList();
              }}
              onError={fail}
            />
          )}
        </div>
      )}

      {scheduling && (
        <ScheduleDialog
          onClose={() => setScheduling(null)}
          onPick={(when) => {
            const { draft, inline: fromInline } = scheduling;
            setScheduling(null);
            send(draft, when, fromInline);
          }}
        />
      )}

      {help && <ShortcutsDialog onClose={() => setHelp(false)} />}

      <div className="mailx-toasts" aria-live="polite">
        {toasts.map((item) => (
          <div key={item.id} className={`mailx-toast${item.tone === "error" ? " error" : ""}`}>
            <span>{item.text}</span>
            {item.undo && (
              <button
                type="button"
                onClick={() => {
                  item.undo?.();
                  setToasts((current) => current.filter((entry) => entry.id !== item.id));
                }}
              >
                <Undo2 aria-hidden="true" /> Undo
              </button>
            )}
            {item.open && (
              <button
                type="button"
                onClick={() => {
                  setOpenTrash(false);
                  setOpenId(item.open ?? null);
                  setToasts((current) => current.filter((entry) => entry.id !== item.id));
                }}
              >
                View message
              </button>
            )}
            <button
              type="button"
              className="close"
              aria-label="Dismiss"
              onClick={() => setToasts((current) => current.filter((entry) => entry.id !== item.id))}
            >
              <X />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

function BulkActions({
  folder,
  onAct,
  onDiscardDrafts,
  onUnschedule,
}: {
  folder: Folder;
  onAct: (action: Action) => void;
  onDiscardDrafts: () => void;
  onUnschedule: () => void;
}) {
  if (folder === "DRAFTS") {
    return (
      <button type="button" className="mailx-tool" onClick={onDiscardDrafts}>
        <Trash2 aria-hidden="true" /> Discard drafts
      </button>
    );
  }
  if (folder === "SCHEDULED") {
    return (
      <button type="button" className="mailx-tool" onClick={onUnschedule}>
        <Undo2 aria-hidden="true" /> Cancel send
      </button>
    );
  }
  if (folder === "TRASH") {
    return (
      <>
        <button type="button" className="mailx-tool" onClick={() => onAct("restore")}>
          <ArchiveRestore aria-hidden="true" /> Move back
        </button>
        <button type="button" className="mailx-tool danger" onClick={() => onAct("purge")}>
          <Trash2 aria-hidden="true" /> Delete forever
        </button>
      </>
    );
  }
  return (
    <>
      {folder !== "ALL" && folder !== "SENT" && (
        <button
          type="button"
          className="mailx-icon"
          aria-label="Archive"
          title="Archive (e)"
          onClick={() => onAct("archive")}
        >
          <Archive />
        </button>
      )}
      <button
        type="button"
        className="mailx-icon"
        aria-label="Delete"
        title="Delete (#)"
        onClick={() => onAct("trash")}
      >
        <Trash2 />
      </button>
      <button
        type="button"
        className="mailx-icon"
        aria-label="Mark as read"
        title="Mark as read (Shift+I)"
        onClick={() => onAct("read")}
      >
        <MailOpen />
      </button>
      <button
        type="button"
        className="mailx-icon"
        aria-label="Mark as unread"
        title="Mark as unread (Shift+U)"
        onClick={() => onAct("unread")}
      >
        <Mail />
      </button>
      <button type="button" className="mailx-icon" aria-label="Star" title="Star" onClick={() => onAct("star")}>
        <Star />
      </button>
    </>
  );
}

function EmptyFolder({ folder, search, onCompose }: { folder: Folder; search: string; onCompose: () => void }) {
  const text: Record<Folder, string> = {
    INBOX: "No mail from people yet.",
    UPDATES: "No updates from Adverse.",
    STARRED: "Star a conversation to keep it here.",
    SENT: "Mail you send shows up here.",
    SCHEDULED: "Mail you schedule waits here until it goes out.",
    DRAFTS: "Unsent mail is saved here as you write.",
    TICKETS: "No tickets.",
    ALL: "No mail yet.",
    TRASH: "Trash is empty.",
  };
  return (
    <div className="mailx-empty">
      <Mail aria-hidden="true" />
      <strong>{search ? `Nothing matches “${search}”.` : text[folder]}</strong>
      {!search && (folder === "INBOX" || folder === "SENT") && (
        <button type="button" className="mailx-primary" onClick={onCompose}>
          <SquarePen aria-hidden="true" /> Compose
        </button>
      )}
    </div>
  );
}

function ConversationRow({
  item,
  me,
  folder,
  focused,
  checked,
  onCheck,
  onStar,
  onOpen,
  onAct,
}: {
  item: Conversation;
  me: string;
  folder: Folder;
  focused: boolean;
  checked: boolean;
  onCheck: () => void;
  onStar: () => void;
  onOpen: () => void;
  onAct: (action: Action) => void;
}) {
  const outgoing = folder === "SENT" || folder === "SCHEDULED" || folder === "DRAFTS";
  let who: ReactNode;
  if (item.status === "DRAFT") {
    who = (
      <>
        <em className="mailx-draft">Draft</em>
        {item.to.length ? ` ${item.to.map((p) => p.name.split(" ")[0]).join(", ")}` : ""}
      </>
    );
  } else if (outgoing) {
    who = `To: ${item.to.map((person) => (person.id === me ? "me" : person.name.split(" ")[0])).join(", ") || "—"}`;
  } else {
    // First names, like Gmail; full names when there is one person or first names would clash.
    const recent = item.participants.slice(-3);
    const firsts = recent.map((name) => name.split(" ")[0]);
    const full = recent.length === 1 || new Set(firsts).size < firsts.length;
    const names = recent.map((name, index) =>
      item.mine && name === item.sender?.name ? "me" : full ? name : firsts[index],
    );
    who = names.join(", ") || firstName(item.sender, me);
  }
  return (
    <li
      className={`mailx-row${item.unread ? " unread" : ""}${checked ? " checked" : ""}${focused ? " focused" : ""}`}
      onClick={onOpen}
    >
      <label className="mailx-check" onClick={(event) => event.stopPropagation()}>
        <input type="checkbox" checked={checked} onChange={onCheck} aria-label={`Select ${item.subject}`} />
      </label>
      <button
        type="button"
        className={`mailx-star${item.starred ? " on" : ""}`}
        aria-label={item.starred ? "Unstar" : "Star"}
        aria-pressed={item.starred}
        onClick={(event) => {
          event.stopPropagation();
          onStar();
        }}
      >
        <Star />
      </button>
      <span className="mailx-row-who">
        {who}
        {item.count > 1 && <small>{item.count}</small>}
      </span>
      <span className="mailx-row-text">
        {item.ticket && <i className={`mailx-ticket-pill ${item.ticket.status.toLowerCase()}`}>{item.ticket.code}</i>}
        {item.kind !== "PERSONAL" && !item.ticket && item.sender === null && <i className="mailx-label">Adverse</i>}
        <strong>{item.subject}</strong>
        <span> — {item.preview}</span>
      </span>
      <span className="mailx-row-meta">
        {item.has_files && <Paperclip aria-label="Has files" />}
        {item.status === "SCHEDULED" && item.scheduled_at ? (
          <time className="mailx-scheduled" dateTime={item.scheduled_at}>
            <Clock3 aria-hidden="true" /> {shortTime(item.scheduled_at)}
          </time>
        ) : (
          <time dateTime={item.created_at} title={fullTime(item.created_at)}>
            {shortTime(item.created_at)}
          </time>
        )}
      </span>
      {item.status === "SENT" && (
        <span className="mailx-row-hover" onClick={(event) => event.stopPropagation()}>
          {folder !== "TRASH" && folder !== "ALL" && folder !== "SENT" && (
            <button type="button" aria-label="Archive" title="Archive" onClick={() => onAct("archive")}>
              <Archive />
            </button>
          )}
          <button
            type="button"
            aria-label={folder === "TRASH" ? "Delete forever" : "Delete"}
            title={folder === "TRASH" ? "Delete forever" : "Delete"}
            onClick={() => onAct(folder === "TRASH" ? "purge" : "trash")}
          >
            <Trash2 />
          </button>
          <button
            type="button"
            aria-label={item.unread ? "Mark as read" : "Mark as unread"}
            title={item.unread ? "Mark as read" : "Mark as unread"}
            onClick={() => onAct(item.unread ? "read" : "unread")}
          >
            {item.unread ? <MailOpen /> : <Mail />}
          </button>
        </span>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------------------------

function ThreadView({
  thread,
  me,
  people,
  isAdmin,
  inTrash,
  inline,
  onBack,
  onAct,
  onReply,
  onInlineChange,
  onInlineSend,
  onInlineSchedule,
  onInlineDiscard,
  onUnschedule,
  onTicket,
  onError,
}: {
  thread: Thread | null;
  me: Person | null;
  people: Person[];
  isAdmin: boolean;
  inTrash: boolean;
  inline: Draft | null;
  onBack: () => void;
  onAct: (action: Action) => void;
  onReply: (message: MailItem, kind: "reply" | "all" | "forward") => void;
  onInlineChange: (draft: Draft) => void;
  onInlineSend: (draft: Draft) => void;
  onInlineSchedule: (draft: Draft) => void;
  onInlineDiscard: (draft: Draft) => void;
  onUnschedule: (message: MailItem) => void;
  onTicket: (ticket: Ticket, change: Record<string, unknown>) => void;
  onError: (reason: unknown) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const replyBox = useRef<HTMLDivElement>(null);
  const items = useMemo(() => thread?.items ?? [], [thread]);
  const last = items[items.length - 1];
  const starred = items.some((item) => item.starred);
  const lastSent = [...items].reverse().find((item) => item.status === "SENT");

  useEffect(() => {
    if (inline) replyBox.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [inline]);

  if (!thread) {
    return (
      <div className="mailx-empty">
        <OrbitLoader size={64} label="Opening the conversation" />
      </div>
    );
  }
  const isOpen = (item: MailItem, index: number) =>
    expanded.has(item.id) || index === items.length - 1 || !item.read || items.length <= 2;

  return (
    <section className="mailx-thread" aria-label={thread.subject}>
      <div className="mailx-toolbar">
        <button type="button" className="mailx-icon" aria-label="Back" title="Back (u)" onClick={onBack}>
          <ArrowLeft />
        </button>
        {inTrash ? (
          <>
            <button type="button" className="mailx-tool" onClick={() => onAct("restore")}>
              <ArchiveRestore aria-hidden="true" /> Move back
            </button>
            <button type="button" className="mailx-tool danger" onClick={() => onAct("purge")}>
              <Trash2 aria-hidden="true" /> Delete forever
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="mailx-icon"
              aria-label="Archive"
              title="Archive (e)"
              onClick={() => onAct("archive")}
            >
              <Archive />
            </button>
            <button
              type="button"
              className="mailx-icon"
              aria-label="Delete"
              title="Delete (#)"
              onClick={() => onAct("trash")}
            >
              <Trash2 />
            </button>
            <button
              type="button"
              className="mailx-icon"
              aria-label="Mark as unread"
              title="Mark as unread"
              onClick={() => onAct("unread")}
            >
              <Mail />
            </button>
          </>
        )}
        <button
          type="button"
          className={`mailx-icon${starred ? " starred" : ""}`}
          aria-label={starred ? "Unstar" : "Star"}
          aria-pressed={starred}
          onClick={() => onAct(starred ? "unstar" : "star")}
        >
          <Star />
        </button>
        <button type="button" className="mailx-icon" aria-label="Print" title="Print" onClick={() => window.print()}>
          <Printer />
        </button>
      </div>

      <div className="mailx-thread-scroll">
        <h1 className="mailx-subject">
          {thread.subject}
          {thread.ticket && (
            <i className={`mailx-ticket-pill ${thread.ticket.status.toLowerCase()}`}>{thread.ticket.code}</i>
          )}
        </h1>

        {thread.event && <MeetingBanner event={thread.event} onError={onError} />}

        {thread.ticket && (
          <TicketBar
            ticket={thread.ticket}
            people={people}
            isAdmin={isAdmin}
            onChange={(change) => onTicket(thread.ticket as Ticket, change)}
          />
        )}

        <ol className="mailx-messages">
          {items.map((item, index) =>
            isOpen(item, index) ? (
              <MessageCard
                key={item.id}
                item={item}
                me={me?.id ?? ""}
                onCollapse={
                  index < items.length - 1
                    ? () =>
                        setExpanded((value) => {
                          const next = new Set(value);
                          next.delete(item.id);
                          return next;
                        })
                    : undefined
                }
                onReply={(kind) => onReply(item, kind)}
                onUnschedule={() => onUnschedule(item)}
              />
            ) : (
              <li
                key={item.id}
                className="mailx-collapsed"
                onClick={() => setExpanded((value) => new Set(value).add(item.id))}
              >
                <Face person={item.sender} size={30} />
                <strong>{item.sender ? item.sender.name : "Adverse"}</strong>
                <span>{item.preview}</span>
                <time>{shortTime(item.created_at)}</time>
              </li>
            ),
          )}
        </ol>

        <div ref={replyBox}>
          {inline ? (
            <div className="mailx-inline">
              <Face person={me} size={36} />
              <div className="mailx-inline-box">
                <Composer
                  draft={inline}
                  people={people}
                  me={me}
                  inline
                  onChange={onInlineChange}
                  onSend={onInlineSend}
                  onSchedule={onInlineSchedule}
                  onDiscard={onInlineDiscard}
                  onSaved={() => undefined}
                  onError={onError}
                />
              </div>
            </div>
          ) : (
            lastSent &&
            !inTrash && (
              <div className="mailx-reply-bar">
                <button type="button" onClick={() => onReply(lastSent, "reply")}>
                  <Reply aria-hidden="true" /> Reply
                </button>
                {(lastSent.recipients.length + lastSent.cc.length > 1 ||
                  (lastSent.mine && lastSent.recipients.length > 1)) && (
                  <button type="button" onClick={() => onReply(lastSent, "all")}>
                    <ReplyAll aria-hidden="true" /> Reply all
                  </button>
                )}
                <button type="button" onClick={() => onReply(lastSent, "forward")}>
                  <Forward aria-hidden="true" /> Forward
                </button>
              </div>
            )
          )}
        </div>
        {last && last.status === "SCHEDULED" && <div className="mailx-spacer" />}
      </div>
    </section>
  );
}

function MessageCard({
  item,
  me,
  onCollapse,
  onReply,
  onUnschedule,
}: {
  item: MailItem;
  me: string;
  onCollapse?: () => void;
  onReply: (kind: "reply" | "all" | "forward") => void;
  onUnschedule: () => void;
}) {
  const [details, setDetails] = useState(false);
  const [menu, setMenu] = useState(false);
  const names = (list: Person[]) => list.map((person) => (person.id === me ? "me" : person.name)).join(", ");
  const toLine = [
    item.recipients.length ? `to ${names(item.recipients)}` : "",
    item.cc.length ? `cc ${names(item.cc)}` : "",
    item.bcc.length ? `bcc ${names(item.bcc)}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  const images = item.attachments.filter((file) => file.mime_type.startsWith("image/"));
  const others = item.attachments.filter((file) => !file.mime_type.startsWith("image/"));

  // App mails (no person sent them, or a task/payment mail) always show as a card.
  const card =
    item.card ?? (!item.sender || (item.kind !== "PERSONAL" && item.kind !== "TICKET") ? cardFromText(item) : null);

  function openLink() {
    const target = item.link;
    if (!target) return;
    try {
      if (window.opener && !window.opener.closed && window.opener.location.origin === window.location.origin) {
        window.opener.location.href = target;
        window.opener.focus();
        return;
      }
    } catch {
      // A different origin: open here instead.
    }
    window.open(target, "_blank", "noopener");
  }

  return (
    <li className={`mailx-message${item.status === "SCHEDULED" ? " scheduled" : ""}`}>
      {item.status === "SCHEDULED" && item.scheduled_at && (
        <div className="mailx-scheduled-bar">
          <CalendarClock aria-hidden="true" />
          <span>Send scheduled for {fullTime(item.scheduled_at)}</span>
          <button type="button" onClick={onUnschedule}>
            Cancel send
          </button>
        </div>
      )}
      <header>
        <Face person={item.sender} size={40} />
        <div className="mailx-from" onClick={onCollapse}>
          <span>
            <strong>{item.sender ? item.sender.name : "Adverse"}</strong>
            <small>{item.sender ? ROLE_LABEL[item.sender.role] : "From the app"}</small>
          </span>
          <button
            type="button"
            className="mailx-to"
            aria-expanded={details}
            onClick={(event) => {
              event.stopPropagation();
              setDetails((value) => !value);
            }}
          >
            {toLine || "to me"} <ChevronDown aria-hidden="true" />
          </button>
        </div>
        <time dateTime={item.created_at} title={fullTime(item.created_at)}>
          {shortTime(item.created_at)}
        </time>
        {item.status === "SENT" && (
          <span className="mailx-msg-actions">
            <button type="button" aria-label="Reply" title="Reply" onClick={() => onReply("reply")}>
              <Reply />
            </button>
            <span className="mailx-more">
              <button type="button" aria-label="More" aria-expanded={menu} onClick={() => setMenu((value) => !value)}>
                <ChevronDown />
              </button>
              {menu && (
                <span className="mailx-menu-pop" role="menu" onMouseLeave={() => setMenu(false)}>
                  <button type="button" role="menuitem" onClick={() => (setMenu(false), onReply("reply"))}>
                    <Reply aria-hidden="true" /> Reply
                  </button>
                  <button type="button" role="menuitem" onClick={() => (setMenu(false), onReply("all"))}>
                    <ReplyAll aria-hidden="true" /> Reply all
                  </button>
                  <button type="button" role="menuitem" onClick={() => (setMenu(false), onReply("forward"))}>
                    <Forward aria-hidden="true" /> Forward
                  </button>
                  <button type="button" role="menuitem" onClick={() => (setMenu(false), window.print())}>
                    <Printer aria-hidden="true" /> Print
                  </button>
                </span>
              )}
            </span>
          </span>
        )}
      </header>
      {details && (
        <dl className="mailx-details">
          <div>
            <dt>From</dt>
            <dd>{item.sender ? `${item.sender.name} (${ROLE_LABEL[item.sender.role]})` : "Adverse"}</dd>
          </div>
          {item.recipients.length > 0 && (
            <div>
              <dt>To</dt>
              <dd>{names(item.recipients)}</dd>
            </div>
          )}
          {item.cc.length > 0 && (
            <div>
              <dt>Cc</dt>
              <dd>{names(item.cc)}</dd>
            </div>
          )}
          {item.bcc.length > 0 && (
            <div>
              <dt>Bcc</dt>
              <dd>{names(item.bcc)}</dd>
            </div>
          )}
          <div>
            <dt>Date</dt>
            <dd>{fullTime(item.created_at)}</dd>
          </div>
          <div>
            <dt>Subject</dt>
            <dd>{item.subject}</dd>
          </div>
        </dl>
      )}
      {card ? (
        <MailCardView card={card} kind={item.kind} onOpen={item.link ? openLink : undefined} />
      ) : (
        <MailBody text={item.body} />
      )}
      {item.link && !card?.action && (
        <button type="button" className="mailx-open-link" onClick={openLink}>
          <ExternalLink aria-hidden="true" /> Open in Adverse
        </button>
      )}
      {item.attachments.length > 0 && (
        <div className="mailx-files">
          <span className="mailx-files-title">
            <Paperclip aria-hidden="true" /> {item.attachments.length}{" "}
            {item.attachments.length === 1 ? "attachment" : "attachments"}
          </span>
          <div>
            {images.map((file) => (
              <a
                key={file.id}
                className="mailx-file image"
                href={`/api/mail/attachments/${file.id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/mail/attachments/${file.id}`} alt={file.file_name} loading="lazy" />
                <span>{file.file_name}</span>
              </a>
            ))}
            {others.map((file) => (
              <a
                key={file.id}
                className="mailx-file"
                href={`/api/mail/attachments/${file.id}`}
                download={file.file_name}
              >
                <FileText aria-hidden="true" />
                <span>
                  {file.file_name}
                  <small>{sizeLabel(file.size_bytes)}</small>
                </span>
                <Download aria-hidden="true" className="dl" />
              </a>
            ))}
          </div>
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------------------------

/** Open a page of the app in the tab that opened Mail (or a new one). */
function openApp(path: string): void {
  try {
    if (window.opener && !window.opener.closed && window.opener.location.origin === window.location.origin) {
      window.opener.location.href = path;
      window.opener.focus();
      return;
    }
  } catch {
    // Not reachable: open a new tab instead.
  }
  window.open(path, "_blank", "noopener");
}

function MeetingBanner({ event, onError }: { event: MeetingCard; onError: (reason: unknown) => void }) {
  const [answer, setAnswer] = useState(event.my_response);
  // When the conversation was opened; Join is checked against it (it reopens on refresh).
  const [now] = useState(() => Date.now());
  const start = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(event.starts_at) ? event.starts_at : `${event.starts_at}Z`);
  const end = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(event.ends_at) ? event.ends_at : `${event.ends_at}Z`);
  const open = now >= start.getTime() - 10 * 60_000 && now <= end.getTime();
  const going = event.attendees.filter((item) => item.response === "YES").length;

  async function respond(response: "YES" | "NO" | "MAYBE") {
    try {
      const result = await fetch(`/api/agenda/events/${event.id}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response }),
      });
      if (!result.ok) throw new Error("Could not save your answer.");
      setAnswer(response);
    } catch (reason) {
      onError(reason);
    }
  }

  return (
    <div className="mailx-meeting-card">
      <span className="mailx-meeting-date" aria-hidden="true">
        <small>{start.toLocaleDateString("en-IN", { month: "short" })}</small>
        <b>{start.getDate()}</b>
      </span>
      <div>
        <strong>{event.title}</strong>
        <small>
          {event.all_day
            ? start.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })
            : `${start.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })} · ${start.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })} – ${end.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}`}
          {event.video ? " · Video call" : ""}
          {event.location ? ` · ${event.location}` : ""}
          {` · ${going + 1} going`}
        </small>
      </div>
      <span className="mailx-meeting-actions">
        {answer !== null && (
          <span className="mailx-rsvp" role="group" aria-label="Going?">
            {(["YES", "MAYBE", "NO"] as const).map((value) => (
              <button
                key={value}
                type="button"
                className={answer === value ? "active" : undefined}
                aria-pressed={answer === value}
                onClick={() => void respond(value)}
              >
                {value === "YES" ? "Yes" : value === "NO" ? "No" : "Maybe"}
              </button>
            ))}
          </span>
        )}
        {event.video && event.conversation_id && (
          <button
            type="button"
            className="mailx-join"
            disabled={!open}
            title={open ? "Join the call" : "Opens 10 minutes before the start"}
            onClick={() => event.conversation_id && startCall(event.conversation_id, "VIDEO", event.title)}
          >
            Join
          </button>
        )}
        <button type="button" className="mailx-tool" onClick={() => openApp(`/agenda?event=${event.id}`)}>
          <CalendarDays aria-hidden="true" /> Calendar
        </button>
      </span>
    </div>
  );
}

function TicketBar({
  ticket,
  people,
  isAdmin,
  onChange,
}: {
  ticket: Ticket;
  people: Person[];
  isAdmin: boolean;
  onChange: (change: Record<string, unknown>) => void;
}) {
  const staff = people.filter((person) => person.role !== "CLIENT");
  return (
    <div className="mailx-ticket-bar">
      <div className="mailx-ticket-facts">
        <span>
          <small>Ticket</small>
          <strong>{ticket.code}</strong>
        </span>
        <span>
          <small>Raised by</small>
          <strong>{ticket.raised_by?.name ?? "Someone"}</strong>
        </span>
        <span>
          <small>Opened</small>
          <strong>{shortTime(ticket.created_at)}</strong>
        </span>
      </div>
      <div className="mailx-ticket-controls">
        <label>
          <small>Status</small>
          {ticket.can_manage ? (
            <LooplessSelect
              value={ticket.status}
              ariaLabel="Ticket status"
              options={(Object.keys(STATUS_LABEL) as TicketStatus[]).map((value) => ({
                value,
                label: STATUS_LABEL[value],
              }))}
              onValueChange={(value) => onChange({ status: value })}
            />
          ) : (
            <i className={`mailx-ticket-pill ${ticket.status.toLowerCase()}`}>{STATUS_LABEL[ticket.status]}</i>
          )}
        </label>
        <label>
          <small>Priority</small>
          {isAdmin ? (
            <LooplessSelect
              value={ticket.priority}
              ariaLabel="Ticket priority"
              options={(Object.keys(PRIORITY_LABEL) as Priority[]).map((value) => ({
                value,
                label: PRIORITY_LABEL[value],
              }))}
              onValueChange={(value) => onChange({ priority: value })}
            />
          ) : (
            <i className={`mailx-priority ${ticket.priority.toLowerCase()}`}>{PRIORITY_LABEL[ticket.priority]}</i>
          )}
        </label>
        <label>
          <small>Assigned to</small>
          {isAdmin ? (
            <LooplessSelect
              value={ticket.assignee?.id ?? ""}
              ariaLabel="Assign the ticket"
              options={[
                { value: "", label: "Not assigned" },
                ...staff.map((person) => ({ value: person.id, label: `${person.name} · ${ROLE_LABEL[person.role]}` })),
              ]}
              onValueChange={(value) => onChange(value ? { assignee_id: value } : { unassign: true })}
            />
          ) : (
            <strong>{ticket.assignee?.name ?? "Not assigned yet"}</strong>
          )}
        </label>
      </div>
    </div>
  );
}

function TicketsView({
  data,
  filter,
  onFilter,
  onOpen,
  onRaise,
  onRefresh,
}: {
  data: { items: Ticket[]; counts: Record<string, number> } | null;
  filter: TicketStatus | "";
  onFilter: (value: TicketStatus | "") => void;
  onOpen: (ticket: Ticket) => void;
  onRaise: () => void;
  onRefresh: () => void;
}) {
  const counts = data?.counts ?? {};
  const total = (counts.OPEN ?? 0) + (counts.IN_PROGRESS ?? 0) + (counts.CLOSED ?? 0);
  const tabs: { value: TicketStatus | ""; label: string; count: number }[] = [
    { value: "", label: "All", count: total },
    { value: "OPEN", label: "Open", count: counts.OPEN ?? 0 },
    { value: "IN_PROGRESS", label: "In progress", count: counts.IN_PROGRESS ?? 0 },
    { value: "CLOSED", label: "Closed", count: counts.CLOSED ?? 0 },
  ];
  return (
    <section className="mailx-tickets" aria-label="Tickets">
      <div className="mailx-toolbar">
        <div className="mailx-tickets-tabs" role="tablist" aria-label="Ticket status">
          {tabs.map((tab) => (
            <button
              key={tab.label}
              type="button"
              role="tab"
              aria-selected={filter === tab.value}
              className={filter === tab.value ? "active" : undefined}
              onClick={() => onFilter(tab.value)}
            >
              {tab.label} <b>{tab.count}</b>
            </button>
          ))}
        </div>
        <button type="button" className="mailx-icon" aria-label="Refresh" onClick={onRefresh}>
          <RefreshCw />
        </button>
        <button type="button" className="mailx-primary small" onClick={onRaise}>
          <TicketIcon aria-hidden="true" /> Raise a ticket
        </button>
      </div>
      {!data ? (
        <div className="mailx-empty">
          <OrbitLoader size={64} label="Loading tickets" />
        </div>
      ) : data.items.length === 0 ? (
        <div className="mailx-empty">
          <LifeBuoy aria-hidden="true" />
          <strong>No tickets{filter ? ` ${STATUS_LABEL[filter].toLowerCase()}` : ""}.</strong>
          <span>Something not working? Raise a ticket and the admin will pick it up.</span>
        </div>
      ) : (
        <div className="mailx-ticket-table" role="table" aria-label="Tickets">
          <div className="mailx-ticket-head" role="row">
            <span role="columnheader">Ticket</span>
            <span role="columnheader">Raised by</span>
            <span role="columnheader">Priority</span>
            <span role="columnheader">Status</span>
            <span role="columnheader">Assigned to</span>
            <span role="columnheader">Updated</span>
          </div>
          {data.items.map((ticket) => (
            <button
              key={ticket.id}
              type="button"
              role="row"
              className="mailx-ticket-row"
              onClick={() => onOpen(ticket)}
            >
              <span role="cell" className="subject">
                <small>{ticket.code}</small>
                <strong>{ticket.subject}</strong>
              </span>
              <span role="cell">{ticket.raised_by?.name ?? "—"}</span>
              <span role="cell">
                <i className={`mailx-priority ${ticket.priority.toLowerCase()}`}>{PRIORITY_LABEL[ticket.priority]}</i>
              </span>
              <span role="cell">
                <i className={`mailx-ticket-pill ${ticket.status.toLowerCase()}`}>{STATUS_LABEL[ticket.status]}</i>
              </span>
              <span role="cell">{ticket.assignee?.name ?? <em>Not assigned</em>}</span>
              <span role="cell">{shortTime(ticket.last_at ?? ticket.updated_at)}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------------------

function RecipientField({
  label,
  value,
  people,
  onChange,
  autoFocus,
  extra,
}: {
  label: string;
  value: Person[];
  people: Person[];
  onChange: (people: Person[]) => void;
  autoFocus?: boolean;
  extra?: ReactNode;
}) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const matches = useMemo(() => {
    const term = text.trim().toLowerCase();
    return people
      .filter((person) => !value.some((chosen) => chosen.id === person.id))
      .filter(
        (person) =>
          !term || person.name.toLowerCase().includes(term) || ROLE_LABEL[person.role].toLowerCase().includes(term),
      )
      .slice(0, 8);
  }, [people, value, text]);

  function pick(person: Person) {
    onChange([...value, person]);
    setText("");
    setActive(0);
    input.current?.focus();
  }

  function onKey(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, matches.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if ((event.key === "Enter" || event.key === "," || event.key === "Tab") && text.trim() && matches[active]) {
      event.preventDefault();
      pick(matches[active]);
    } else if (event.key === "Backspace" && !text && value.length) {
      onChange(value.slice(0, -1));
    } else if (event.key === "Escape" && focused) {
      event.preventDefault();
      setFocused(false);
    }
  }

  return (
    <div className="mailx-field mailx-recipients" onClick={() => input.current?.focus()}>
      <span className="mailx-field-label">{label}</span>
      <div className="mailx-chips">
        {value.map((person) => (
          <span key={person.id} className="mailx-chip" title={`${person.name} · ${ROLE_LABEL[person.role]}`}>
            <Face person={person} size={20} />
            {person.name}
            <button
              type="button"
              aria-label={`Remove ${person.name}`}
              onClick={(event) => {
                event.stopPropagation();
                onChange(value.filter((item) => item.id !== person.id));
              }}
            >
              <X />
            </button>
          </span>
        ))}
        <input
          ref={input}
          value={text}
          autoFocus={autoFocus}
          aria-label={label === "To" ? "Add a recipient" : `Add ${label}`}
          role="combobox"
          aria-controls={listId}
          aria-expanded={focused && matches.length > 0 ? "true" : "false"}
          aria-autocomplete="list"
          onChange={(event) => {
            setText(event.target.value);
            setActive(0);
          }}
          onFocus={() => setFocused(true)}
          // Suggestions are picked on mousedown (focus stays), so the list can close at once.
          onBlur={() => setFocused(false)}
          onKeyDown={onKey}
        />
      </div>
      {extra}
      {focused && matches.length > 0 && (
        <ul id={listId} className="mailx-suggest" role="listbox" aria-label={`${label} suggestions`}>
          {matches.map((person, index) => (
            <li
              key={person.id}
              role="option"
              aria-selected={index === active}
              className={index === active ? "active" : undefined}
              onMouseDown={(event) => {
                event.preventDefault();
                pick(person);
              }}
            >
              <Face person={person} size={28} />
              <span>
                <strong>{person.name}</strong>
                <small>{ROLE_LABEL[person.role]}</small>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Composer({
  draft,
  people,
  me,
  inline = false,
  onChange,
  onSend,
  onSchedule,
  onDiscard,
  onSaved,
  onError,
}: {
  draft: Draft;
  people: Person[];
  me: Person | null;
  inline?: boolean;
  onChange: (draft: Draft) => void;
  onSend: (draft: Draft) => void;
  onSchedule: (draft: Draft) => void;
  onDiscard: (draft: Draft) => void;
  onSaved: () => void;
  onError: (reason: unknown) => void;
}) {
  const [saved, setSaved] = useState<string>("");
  const [problem, setProblem] = useState("");
  const [sendMenu, setSendMenu] = useState(false);
  const latest = useRef(draft);
  const saving = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const body = useRef<HTMLTextAreaElement>(null);
  const isTicket = Boolean(draft.ticket) && draft.mode === "new";
  const admins = people.filter((person) => person.role === "ADMIN");

  useEffect(() => {
    latest.current = draft;
  }, [draft]);

  useEffect(() => {
    if (draft.mode !== "new") body.current?.focus();
    if (draft.mode === "forward") body.current?.setSelectionRange(0, 0);
    // Focus once when the composer opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.key]);

  // Drafts save themselves a moment after you stop typing.
  const signature = `${draft.to.map((p) => p.id)}|${draft.cc.map((p) => p.id)}|${draft.bcc.map((p) => p.id)}|${draft.subject}|${draft.body}`;
  useEffect(() => {
    const current = latest.current;
    const hasContent = current.subject.trim() || current.body.trim() || current.to.length;
    if (!hasContent || current.mode === "forward") return;
    const timer = window.setTimeout(() => {
      if (saving.current) return;
      saving.current = true;
      const form = new FormData();
      const now = latest.current;
      if (now.draftId) form.append("draft_id", now.draftId);
      now.to.forEach((person) => form.append("to", person.id));
      now.cc.forEach((person) => form.append("cc", person.id));
      now.bcc.forEach((person) => form.append("bcc", person.id));
      form.append("subject", now.subject);
      form.append("body", now.body);
      if (now.replyTo) form.append("reply_to_id", now.replyTo);
      void mailApi<{ id: string; saved_at: string }>("/drafts", { method: "POST", body: form })
        .then((result) => {
          if (latest.current.key === now.key && !latest.current.draftId)
            onChange({ ...latest.current, draftId: result.id });
          setSaved(new Date().toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }));
          onSaved();
        })
        .catch(() => undefined)
        .finally(() => {
          saving.current = false;
        });
    }, 1600);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  function update(change: Partial<Draft>) {
    setProblem("");
    onChange({ ...draft, ...change });
  }

  function ready(): boolean {
    if (!isTicket && draft.to.length + draft.cc.length + draft.bcc.length === 0) {
      setProblem("Add at least one person.");
      return false;
    }
    if (!draft.subject.trim() && draft.mode === "new") {
      setProblem(isTicket ? "Say what the problem is in the subject." : "Add a subject.");
      return false;
    }
    if (!draft.body.trim() && draft.files.length === 0 && draft.mode !== "forward") {
      setProblem(isTicket ? "Describe the problem." : "Write a message or attach a file.");
      return false;
    }
    return true;
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (ready()) onSend(latest.current);
  }

  function addFiles(event: ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []);
    event.target.value = "";
    const big = picked.find((file) => file.size > 25 * 1024 * 1024);
    if (big) {
      onError(new Error(`${big.name} is larger than 25 MB.`));
      return;
    }
    update({ files: [...draft.files, ...picked].slice(0, 10) });
  }

  return (
    <form className={`mailx-composer${inline ? " inline" : ""}${isTicket ? " ticket" : ""}`} onSubmit={submit}>
      {inline && (
        <div className="mailx-inline-head">
          {draft.mode === "forward" ? (
            <Forward aria-hidden="true" />
          ) : draft.cc.length ? (
            <ReplyAll aria-hidden="true" />
          ) : (
            <Reply aria-hidden="true" />
          )}
          <span>{draft.mode === "forward" ? "Forward" : "Reply"}</span>
        </div>
      )}
      {isTicket && (
        <div className="mailx-ticket-note">
          <LifeBuoy aria-hidden="true" />
          <span>
            Goes to {admins.length ? admins.map((person) => person.name.split(" ")[0]).join(", ") : "the admin"} as a
            ticket. Replies stay in this conversation.
          </span>
          <LooplessSelect
            value={draft.ticket ?? "NORMAL"}
            ariaLabel="Ticket priority"
            options={(Object.keys(PRIORITY_LABEL) as Priority[]).map((value) => ({
              value,
              label: `${PRIORITY_LABEL[value]} priority`,
            }))}
            onValueChange={(value) => update({ ticket: value as Priority })}
          />
        </div>
      )}
      <RecipientField
        label="To"
        value={draft.to}
        people={people}
        autoFocus={draft.mode === "new" && !isTicket}
        onChange={(to) => update({ to })}
        extra={
          <span className="mailx-cc-toggles">
            {!draft.showCc && (
              <button type="button" onClick={() => update({ showCc: true })}>
                Cc
              </button>
            )}
            {!draft.showBcc && (
              <button type="button" onClick={() => update({ showBcc: true })}>
                Bcc
              </button>
            )}
          </span>
        }
      />
      {draft.showCc && <RecipientField label="Cc" value={draft.cc} people={people} onChange={(cc) => update({ cc })} />}
      {draft.showBcc && (
        <RecipientField label="Bcc" value={draft.bcc} people={people} onChange={(bcc) => update({ bcc })} />
      )}
      {(draft.mode === "new" || draft.mode === "forward") && (
        <label className="mailx-field">
          <span className="mailx-field-label">Subject</span>
          <input
            value={draft.subject}
            maxLength={200}
            aria-label="Subject"
            autoFocus={isTicket}
            placeholder={isTicket ? "What is the problem?" : undefined}
            onChange={(event) => update({ subject: event.target.value })}
          />
        </label>
      )}
      <textarea
        ref={body}
        className="mailx-text"
        value={draft.body}
        aria-label="Message"
        maxLength={20000}
        placeholder={
          isTicket
            ? "What happened, where, and what you expected…"
            : inline
              ? "Write your reply…"
              : "Write your message…"
        }
        onChange={(event) => update({ body: event.target.value })}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            submit();
          }
        }}
      />
      {draft.files.length > 0 && (
        <ul className="mailx-pending">
          {draft.files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <Paperclip aria-hidden="true" />
              <span>
                {file.name}
                <small>{sizeLabel(file.size)}</small>
              </span>
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                onClick={() => update({ files: draft.files.filter((_, i) => i !== index) })}
              >
                <X />
              </button>
            </li>
          ))}
        </ul>
      )}
      {draft.mode === "forward" && <p className="mailx-hint">Files from the original mail go with it.</p>}
      {draft.meeting && (
        <div className="mailx-meeting">
          <CalendarPlus aria-hidden="true" />
          <strong>Meeting</strong>
          <LooplessDate
            value={draft.meeting.day}
            ariaLabel="Meeting date"
            clearable={false}
            onValueChange={(value) =>
              update({ meeting: { ...(draft.meeting as NonNullable<Draft["meeting"]>), day: value } })
            }
          />
          <input
            type="time"
            aria-label="Meeting start"
            value={draft.meeting.start}
            onChange={(event) =>
              update({ meeting: { ...(draft.meeting as NonNullable<Draft["meeting"]>), start: event.target.value } })
            }
          />
          <span>to</span>
          <input
            type="time"
            aria-label="Meeting end"
            value={draft.meeting.end}
            onChange={(event) =>
              update({ meeting: { ...(draft.meeting as NonNullable<Draft["meeting"]>), end: event.target.value } })
            }
          />
          <label>
            <input
              type="checkbox"
              checked={draft.meeting.video}
              onChange={(event) =>
                update({
                  meeting: { ...(draft.meeting as NonNullable<Draft["meeting"]>), video: event.target.checked },
                })
              }
            />
            Video call
          </label>
          <small>Everyone in To, Cc and Bcc gets it on their calendar, with a reminder 10 minutes before.</small>
        </div>
      )}
      {problem && (
        <p className="mailx-problem" role="alert">
          {problem}
        </p>
      )}
      <footer>
        <div className="mailx-send">
          <button type="submit" className="mailx-primary" title="Send (Ctrl + Enter)">
            {isTicket ? <TicketIcon aria-hidden="true" /> : <SendHorizontal aria-hidden="true" />}
            {isTicket ? "Raise ticket" : "Send"}
          </button>
          {!isTicket && (
            <span className="mailx-send-more">
              <button
                type="button"
                aria-label="More send options"
                aria-expanded={sendMenu}
                onClick={() => setSendMenu((value) => !value)}
              >
                <ChevronDown />
              </button>
              {sendMenu && (
                <span className="mailx-menu-pop up" role="menu" onMouseLeave={() => setSendMenu(false)}>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setSendMenu(false);
                      if (ready()) onSchedule(latest.current);
                    }}
                  >
                    <CalendarClock aria-hidden="true" /> Schedule send
                  </button>
                </span>
              )}
            </span>
          )}
        </div>
        <button
          type="button"
          className="mailx-icon"
          aria-label="Attach files"
          title="Attach files (up to 25 MB each)"
          onClick={() => fileInput.current?.click()}
        >
          <Paperclip />
        </button>
        <input ref={fileInput} type="file" multiple hidden onChange={addFiles} />
        {draft.mode === "new" && me && me.role !== "CLIENT" && !isTicket && (
          <button
            type="button"
            className={`mailx-icon${draft.meeting ? " on" : ""}`}
            aria-label={draft.meeting ? "Remove the meeting" : "Add a meeting"}
            aria-pressed={Boolean(draft.meeting)}
            title={draft.meeting ? "Remove the meeting" : "Add a meeting to the calendar"}
            onClick={() => {
              if (draft.meeting) return update({ meeting: null });
              const start = new Date(Date.now() + 864e5);
              start.setHours(10, 0, 0, 0);
              const pad = (value: number) => String(value).padStart(2, "0");
              update({
                meeting: {
                  day: `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`,
                  start: "10:00",
                  end: "10:30",
                  video: true,
                },
              });
            }}
          >
            <CalendarPlus />
          </button>
        )}
        {draft.mode === "new" && me?.role && (
          <button
            type="button"
            className={`mailx-icon${isTicket ? " on" : ""}`}
            aria-label={isTicket ? "Make it a normal mail" : "Raise as a ticket"}
            aria-pressed={isTicket}
            title={isTicket ? "Make it a normal mail" : "Raise as a ticket"}
            onClick={() => update({ ticket: isTicket ? null : "NORMAL" })}
          >
            <TicketIcon />
          </button>
        )}
        <span className="mailx-saved">{saved ? `Draft saved ${saved}` : ""}</span>
        <button
          type="button"
          className="mailx-icon"
          aria-label="Discard draft"
          title="Discard draft"
          onClick={() => onDiscard(latest.current)}
        >
          <Trash2 />
        </button>
      </footer>
    </form>
  );
}

// ---------------------------------------------------------------------------------------------

function ScheduleDialog({ onClose, onPick }: { onClose: () => void; onPick: (when: Date) => void }) {
  const presets = useMemo(() => {
    const at = (days: number, hour: number) => {
      const date = new Date();
      date.setDate(date.getDate() + days);
      date.setHours(hour, 0, 0, 0);
      return date;
    };
    const monday = new Date();
    const add = (8 - monday.getDay()) % 7 || 7;
    return [
      { label: "Tomorrow morning", when: at(1, 8) },
      { label: "Tomorrow afternoon", when: at(1, 13) },
      { label: "Monday morning", when: at(add, 8) },
    ];
  }, []);
  const [day, setDay] = useState("");
  const [time, setTime] = useState("09:00");
  const [problem, setProblem] = useState("");

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [onClose]);

  return (
    <div className="mailx-modal-back" onClick={onClose}>
      <section
        className="mailx-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Schedule send"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <h2>
            <CalendarClock aria-hidden="true" /> Schedule send
          </h2>
          <button type="button" className="mailx-icon" aria-label="Close" onClick={onClose}>
            <X />
          </button>
        </header>
        <div className="mailx-presets">
          {presets.map((preset) => (
            <button key={preset.label} type="button" onClick={() => onPick(preset.when)}>
              <span>{preset.label}</span>
              <small>
                {preset.when.toLocaleString("en-IN", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </small>
            </button>
          ))}
        </div>
        <form
          className="mailx-custom-time"
          onSubmit={(event) => {
            event.preventDefault();
            const when = new Date(`${day}T${time}`);
            if (!day || Number.isNaN(when.getTime())) return setProblem("Pick a date and a time.");
            if (when.getTime() < Date.now() + 60_000) return setProblem("Pick a time in the future.");
            onPick(when);
          }}
        >
          <strong>Pick a date and time</strong>
          <div>
            <LooplessDate
              value={day}
              onValueChange={setDay}
              ariaLabel="Date"
              min={new Date().toISOString().slice(0, 10)}
            />
            <input type="time" value={time} aria-label="Time" onChange={(event) => setTime(event.target.value)} />
          </div>
          {problem && (
            <p className="mailx-problem" role="alert">
              {problem}
            </p>
          )}
          <footer>
            <button type="button" className="mailx-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="mailx-primary">
              Schedule send
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

function ShortcutsDialog({ onClose }: { onClose: () => void }) {
  const keys: [string, string][] = [
    ["c", "Compose"],
    ["/", "Search"],
    ["j / k", "Next / previous conversation"],
    ["o or Enter", "Open"],
    ["u or Esc", "Back to the list"],
    ["x", "Select"],
    ["e", "Archive"],
    ["#", "Delete"],
    ["s", "Star"],
    ["r", "Reply"],
    ["a", "Reply all"],
    ["f", "Forward"],
    ["Shift + I", "Mark as read"],
    ["Shift + U", "Mark as unread"],
    ["Ctrl + Enter", "Send"],
  ];
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape" || event.key === "?") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [onClose]);
  return (
    <div className="mailx-modal-back" onClick={onClose}>
      <section
        className="mailx-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <h2>
            <Keyboard aria-hidden="true" /> Keyboard shortcuts
          </h2>
          <button type="button" className="mailx-icon" aria-label="Close" onClick={onClose}>
            <X />
          </button>
        </header>
        <dl className="mailx-keys">
          {keys.map(([key, label]) => (
            <div key={key}>
              <dt>
                <kbd>{key}</kbd>
              </dt>
              <dd>{label}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}

export type { Role };
