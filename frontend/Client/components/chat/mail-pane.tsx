// Copy of frontend/shared/chat/mail-pane.tsx (the Client app has no shared alias). Keep in sync.
"use client";

/*
 * Internal mailbox inside Chat (owner request 2026-11-15): mail between people in the company
 * instead of email. Staff write to anyone on the team; clients only with the admins (and only
 * the admins write to clients). The app writes here too ("Adverse") about tasks, payments and
 * meetings. Folders: Inbox (from people), From Adverse, Sent. Each mail opens with its replies.
 */
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bell,
  ExternalLink,
  Inbox,
  Paperclip,
  PenSquare,
  Reply,
  Search,
  Send,
  Trash2,
  X,
} from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { subscribeRealtime } from "@/lib/realtime";
import { fileSize, initials, listTime } from "./chat-types";
import { OrbitLoader } from "@/components/loader/orbit-loader";
import "@/styles/mail.css";

type Role = "ADMIN" | "MANAGER" | "EMPLOYEE" | "CLIENT";
type Person = { id: string; name: string; role: Role; image?: string | null };
type MailFile = { id: string; file_name: string; mime_type: string; size_bytes: number };
type MailItem = {
  id: string;
  thread_id: string;
  kind: string;
  subject: string;
  preview: string;
  body: string;
  link: string;
  created_at: string;
  sender: Person | null;
  recipients: Person[];
  read: boolean;
  mine: boolean;
  attachments: MailFile[];
};
type Unread = { inbox: number; system: number; total: number };
type MailList = { items: MailItem[]; total: number; unread: Unread };
type Thread = { thread_id: string; subject: string; items: MailItem[] };
type Folder = "INBOX" | "SYSTEM" | "SENT";

const ROLE_LABEL: Record<Role, string> = { ADMIN: "Admin", MANAGER: "Manager", EMPLOYEE: "Employee", CLIENT: "Client" };

async function mailApi<T>(path: string, init?: RequestInit): Promise<T> {
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

function Face({ person, size = 36 }: { person: Person | null; size?: number }) {
  return (
    <span
      className={`chat-avatar mail-face${person ? "" : " app"}`}
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      aria-hidden="true"
    >
      {person ? (
        person.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={person.image} alt="" />
        ) : (
          initials(person.name)
        )
      ) : (
        <Bell />
      )}
    </span>
  );
}

function Linked({ text }: { text: string }) {
  const parts = text.split(/(https?:\/\/[^\s<>"]+)/g);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <a key={index} href={part} target="_blank" rel="noopener noreferrer">
            {part}
          </a>
        ) : (
          part
        ),
      )}
    </>
  );
}

export function MailPane({
  meId,
  role,
  openId,
  onOpenChange,
  onUnread,
}: {
  meId: string;
  role: Role;
  openId?: string | null;
  onOpenChange?: (open: boolean) => void;
  onUnread?: (count: number) => void;
}) {
  const router = useRouter();
  const [folder, setFolder] = useState<Folder>("INBOX");
  const [query, setQuery] = useState("");
  const [list, setList] = useState<MailList | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(openId ?? null);
  const [thread, setThread] = useState<Thread | null>(null);
  const [composing, setComposing] = useState<{ to: Person[]; subject: string; replyTo?: string } | null>(null);
  const [people, setPeople] = useState<Person[]>([]);

  const load = useCallback(async () => {
    try {
      const data = await mailApi<MailList>(`?folder=${folder}&q=${encodeURIComponent(query.trim())}`);
      setList(data);
      onUnread?.(data.unread.total);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load mail.");
    }
  }, [folder, query, onUnread]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  useEffect(() => {
    const timer = window.setTimeout(
      () =>
        void mailApi<{ people: Person[] }>("/people")
          .then((data) => setPeople(data.people))
          .catch(() => undefined),
      0,
    );
    return () => window.clearTimeout(timer);
  }, []);

  const openThread = useCallback(async (id: string) => {
    setThread(null);
    try {
      setThread(await mailApi<Thread>(`/${id}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not open that mail.");
    }
  }, []);

  useEffect(() => {
    if (!selected) return;
    const timer = window.setTimeout(() => void openThread(selected).then(() => void load()), 0);
    return () => window.clearTimeout(timer);
    // Reload the list (unread marks) only when another mail is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, openThread]);

  useEffect(() => {
    onOpenChange?.(Boolean(selected || composing));
  }, [selected, composing, onOpenChange]);

  useEffect(
    () =>
      subscribeRealtime((event) => {
        if (event.type !== "mail.new" && event.type !== "mail.read") return;
        void load();
        const data = event.data as { message_id?: string };
        if (event.type === "mail.new" && thread && data.message_id)
          void openThread(thread.items[0]?.id ?? data.message_id);
      }),
    [load, openThread, thread],
  );

  function reply(item: MailItem) {
    const to = item.mine
      ? item.recipients
      : [item.sender, ...item.recipients.filter((person) => person.id !== meId)].filter((person): person is Person =>
          Boolean(person),
        );
    const allowed = to.filter((person) => people.some((item) => item.id === person.id));
    setComposing({
      to: allowed,
      subject: item.subject.toLowerCase().startsWith("re:") ? item.subject : `Re: ${item.subject}`,
      replyTo: item.id,
    });
  }

  async function remove(item: MailItem) {
    try {
      await mailApi(`/${item.id}`, { method: "DELETE" });
      setSelected(null);
      setThread(null);
      void load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove that mail.");
    }
  }

  const folders: { key: Folder; label: string; count: number }[] = [
    { key: "INBOX", label: "Inbox", count: list?.unread.inbox ?? 0 },
    { key: "SYSTEM", label: "From Adverse", count: list?.unread.system ?? 0 },
    { key: "SENT", label: "Sent", count: 0 },
  ];

  return (
    <>
      <div className="chat-list mail-list">
        <header>
          <h2>Mail</h2>
          <button
            type="button"
            className="chat-icon-button primary"
            aria-label="New mail"
            title="New mail"
            onClick={() => {
              setSelected(null);
              setComposing({ to: [], subject: "" });
            }}
          >
            <PenSquare />
          </button>
        </header>
        <label className="chat-search">
          <Search aria-hidden="true" />
          <input
            value={query}
            placeholder="Search mail"
            aria-label="Search mail"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="chat-tabs" role="tablist" aria-label="Mail folders">
          {folders.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={folder === item.key}
              className={folder === item.key ? "active" : undefined}
              onClick={() => setFolder(item.key)}
            >
              {item.label}
              {item.count > 0 && <em className="mail-count">{item.count}</em>}
            </button>
          ))}
        </div>
        <div className="chat-list-body">
          {error && !list ? (
            <div className="chat-empty">{error}</div>
          ) : !list ? (
            <div className="chat-empty">
              <OrbitLoader size={48} label="Loading mail" />
            </div>
          ) : list.items.length === 0 ? (
            <div className="chat-empty">
              <Inbox aria-hidden="true" />
              {query
                ? "No mail matches."
                : folder === "SENT"
                  ? "Mail you send shows here."
                  : folder === "SYSTEM"
                    ? "Task, payment and meeting updates from the app show here."
                    : role === "CLIENT"
                      ? "Mail from your agency shows here. Write to them with the pen button."
                      : "No mail yet. Write one with the pen button."}
            </div>
          ) : (
            <ul className="chat-items">
              {list.items.map((item) => {
                const who = item.mine
                  ? `To ${item.recipients.map((person) => person.name.split(" ")[0]).join(", ")}`
                  : (item.sender?.name ?? "Adverse");
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`chat-item mail-item${item.thread_id === thread?.thread_id && selected ? " active" : ""}${item.read ? "" : " unread"}`}
                      onClick={() => {
                        setComposing(null);
                        setSelected(item.id);
                      }}
                    >
                      <Face person={item.mine ? (item.recipients[0] ?? null) : item.sender} />
                      <span className="chat-item-text">
                        <span className="chat-item-top">
                          <strong>{who}</strong>
                          <small>{listTime(item.created_at)}</small>
                        </span>
                        <span className="mail-subject">{item.subject}</span>
                        <span className="chat-item-bottom">
                          <span>
                            {item.attachments.length > 0 && <Paperclip className="mail-clip" aria-label="Has files" />}
                            {item.preview}
                          </span>
                          {!item.read && <i className="mail-dot" aria-label="Unread" />}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="chat-thread mail-reader">
        {composing ? (
          <Compose
            key={composing.replyTo ?? "new"}
            people={people}
            role={role}
            initial={composing}
            onCancel={() => setComposing(null)}
            onSent={(sent) => {
              setComposing(null);
              setFolder("SENT");
              setSelected(sent.items[sent.items.length - 1]?.id ?? null);
              setThread(sent);
              void load();
            }}
          />
        ) : selected && thread ? (
          <article className="mail-thread">
            <header className="chat-thread-head">
              <button
                type="button"
                className="chat-icon-button back mail-back"
                aria-label="Back to mail"
                onClick={() => {
                  setSelected(null);
                  setThread(null);
                }}
              >
                <ArrowLeft />
              </button>
              <div className="chat-thread-title">
                <strong>{thread.subject}</strong>
                <small>
                  {thread.items.length} {thread.items.length === 1 ? "message" : "messages"}
                </small>
              </div>
            </header>
            <div className="mail-messages">
              {thread.items.map((item) => (
                <section key={item.id} className="mail-message">
                  <header>
                    <Face person={item.sender} size={38} />
                    <div>
                      <strong>
                        {item.sender ? (item.mine ? "You" : item.sender.name) : "Adverse"}
                        {item.sender && !item.mine && <small> · {ROLE_LABEL[item.sender.role]}</small>}
                      </strong>
                      <small>
                        To {item.recipients.map((person) => (person.id === meId ? "you" : person.name)).join(", ")} ·{" "}
                        {new Date(item.created_at).toLocaleString("en-IN", {
                          day: "numeric",
                          month: "short",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </small>
                    </div>
                  </header>
                  {item.body && (
                    <p className="mail-body">
                      <Linked text={item.body} />
                    </p>
                  )}
                  {item.attachments.length > 0 && (
                    <ul className="mail-files">
                      {item.attachments.map((file) => (
                        <li key={file.id}>
                          <a href={`/api/mail/attachments/${file.id}`} target="_blank" rel="noopener noreferrer">
                            <Paperclip aria-hidden="true" /> {file.file_name} <small>{fileSize(file.size_bytes)}</small>
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="mail-actions">
                    {item.link && (
                      <button type="button" className="chat-btn primary" onClick={() => router.push(item.link)}>
                        <ExternalLink /> Open
                      </button>
                    )}
                    {item.sender && (
                      <button type="button" className="chat-btn" onClick={() => reply(item)}>
                        <Reply /> Reply
                      </button>
                    )}
                    <button type="button" className="chat-btn" onClick={() => void remove(item)}>
                      <Trash2 /> Remove
                    </button>
                  </div>
                </section>
              ))}
            </div>
          </article>
        ) : selected ? (
          <div className="chat-thread-empty">
            <OrbitLoader size={56} label="Opening mail" />
          </div>
        ) : (
          <div className="chat-thread-empty">
            <Inbox aria-hidden="true" />
            <strong>Pick a mail</strong>
            <span>
              {role === "CLIENT"
                ? "Mail with your agency's admin stays here."
                : "Work and payment updates from the app, and mail from your team."}
            </span>
          </div>
        )}
      </div>
    </>
  );
}

function Compose({
  people,
  role,
  initial,
  onCancel,
  onSent,
}: {
  people: Person[];
  role: Role;
  initial: { to: Person[]; subject: string; replyTo?: string };
  onCancel: () => void;
  onSent: (thread: Thread) => void;
}) {
  const [to, setTo] = useState<Person[]>(initial.to);
  const [subject, setSubject] = useState(initial.subject);
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement | null>(null);
  const choices = people.filter((person) => !to.some((item) => item.id === person.id));

  async function send(event: FormEvent) {
    event.preventDefault();
    if (to.length === 0) return setError("Choose who the mail is for.");
    setBusy(true);
    setError("");
    const form = new FormData();
    to.forEach((person) => form.append("to", person.id));
    form.append("subject", subject.trim());
    form.append("body", body);
    if (initial.replyTo) form.append("reply_to_id", initial.replyTo);
    files.forEach((file) => form.append("files", file));
    try {
      onSent(await mailApi<Thread>("", { method: "POST", body: form }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not send the mail.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mail-compose" onSubmit={(event) => void send(event)}>
      <header className="chat-thread-head">
        <button type="button" className="chat-icon-button back mail-back" aria-label="Back to mail" onClick={onCancel}>
          <ArrowLeft />
        </button>
        <div className="chat-thread-title">
          <strong>{initial.replyTo ? "Reply" : "New mail"}</strong>
          <small>{role === "CLIENT" ? "To your agency's admin" : "Inside the company, not email"}</small>
        </div>
        <button type="button" className="chat-icon-button" aria-label="Close" onClick={onCancel}>
          <X />
        </button>
      </header>
      <div className="mail-compose-body">
        {error && <p className="mail-error">{error}</p>}
        <div className="mail-field">
          <span>To</span>
          <div className="mail-to">
            {to.map((person) => (
              <span key={person.id} className="mail-chip">
                {person.name}
                <button
                  type="button"
                  aria-label={`Remove ${person.name}`}
                  onClick={() => setTo((current) => current.filter((item) => item.id !== person.id))}
                >
                  <X />
                </button>
              </span>
            ))}
            {choices.length > 0 && (
              <div className="mail-to-add">
                <LooplessSelect
                  value=""
                  ariaLabel="Add a recipient"
                  onValueChange={(value) => {
                    const person = people.find((item) => item.id === value);
                    if (person) setTo((current) => [...current, person]);
                  }}
                  options={[
                    { value: "", label: to.length ? "Add someone" : "Choose who" },
                    ...choices.map((person) => ({
                      value: person.id,
                      label: `${person.name} · ${ROLE_LABEL[person.role]}`,
                    })),
                  ]}
                />
              </div>
            )}
          </div>
        </div>
        <label className="mail-field">
          <span>Subject</span>
          <input value={subject} maxLength={200} required onChange={(event) => setSubject(event.target.value)} />
        </label>
        <label className="mail-field grow">
          <span>Message</span>
          <textarea value={body} maxLength={20000} rows={10} onChange={(event) => setBody(event.target.value)} />
        </label>
        {files.length > 0 && (
          <ul className="mail-files">
            {files.map((file, index) => (
              <li key={`${file.name}-${index}`}>
                <span>
                  <Paperclip aria-hidden="true" /> {file.name} <small>{fileSize(file.size)}</small>
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${file.name}`}
                  onClick={() => setFiles((current) => current.filter((_, at) => at !== index))}
                >
                  <X />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <footer className="mail-compose-foot">
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            const picked = Array.from(event.target.files ?? []);
            setFiles((current) => [...current, ...picked].slice(0, 10));
            event.target.value = "";
          }}
        />
        <button type="button" className="chat-btn" onClick={() => fileInput.current?.click()}>
          <Paperclip /> Attach
        </button>
        <button type="submit" className="chat-btn primary" disabled={busy}>
          <Send /> {busy ? "Sending…" : "Send"}
        </button>
      </footer>
    </form>
  );
}
