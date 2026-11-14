"use client";

/*
 * Chat (Phase 14, owner decisions 2026-11-14). Three panes like the owner's screenshot:
 * folders (Inbox, Clients, Team, Direct) | chats (All / Unread / Mine, search) | the thread.
 * Full screen: no hero; on wide screens the shell also hides its top bar and collapses the sidebar.
 * - Client rooms: the admin creates them and picks the managers and employees in them.
 * - Direct chats: anyone in the team with anyone in the team; a client only with the admin.
 * - Groups: the admin and managers create them.
 * Live over the shared realtime stream: new messages, edits, read receipts, typing.
 * The server enforces every rule; this page only hides what a person cannot do.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  ArrowLeft,
  Check,
  CheckCheck,
  Contact,
  Download,
  FileText,
  Inbox,
  MessageCirclePlus,
  MessageSquare,
  Paperclip,
  Pencil,
  RefreshCw,
  Reply,
  Search,
  Send,
  Settings2,
  Trash2,
  UsersRound,
  X,
} from "lucide-react";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { subscribeRealtime } from "../realtime/realtime";
import {
  ROLE_LABELS,
  STATUS_LABELS,
  chatApi,
  clock,
  dayLabel,
  fileSize,
  initials,
  jsonBody,
  listTime,
  type ChatMessage,
  type ChatPerson,
  type ChatRole,
  type ChatStatus,
  type Conversation,
} from "./chat-types";
import "../styles/chat.css";

type Folder = "INBOX" | "CLIENTS" | "TEAM" | "DIRECT";
type Tab = "ALL" | "UNREAD" | "MINE";
type Dialog = { kind: "direct" | "group" | "room" } | { kind: "people"; chat: Conversation } | null;

declare global {
  interface Window {
    __adverseActiveChat?: string;
  }
}

function Avatar({
  person,
  size = 36,
}: {
  person: Pick<ChatPerson, "name" | "image"> & { status?: ChatStatus };
  size?: number;
}) {
  return (
    <span className="chat-avatar" style={{ width: size, height: size, fontSize: size * 0.36 }}>
      {person.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={person.image} alt="" />
      ) : (
        initials(person.name)
      )}
      {person.status && <i className={`chat-dot ${person.status.toLowerCase()}`} aria-hidden="true" />}
    </span>
  );
}

function isClientChat(chat: Conversation): boolean {
  return chat.type === "CLIENT" || (chat.type === "DIRECT" && chat.members.some((m) => m.role === "CLIENT"));
}

export function ChatPage({ role }: { role: ChatRole }) {
  const [me, setMe] = useState<ChatPerson | null>(null);
  const [people, setPeople] = useState<ChatPerson[]>([]);
  const [chats, setChats] = useState<Conversation[] | null>(null);
  const [error, setError] = useState("");
  const [folder, setFolder] = useState<Folder>("INBOX");
  const [tab, setTab] = useState<Tab>("ALL");
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<ChatMessage[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notice, setNotice] = useState("");

  const loadChats = useCallback(async () => {
    try {
      const result = await chatApi<{ items: Conversation[] }>("/conversations");
      setChats(result.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load your chats.");
    }
  }, []);

  const loadPeople = useCallback(async () => {
    try {
      const result = await chatApi<{ me: ChatPerson; people: ChatPerson[] }>("/people");
      setMe(result.me);
      setPeople(result.people);
    } catch {
      // The list still works; statuses just are not shown.
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadChats();
      void loadPeople();
      const wanted = new URLSearchParams(window.location.search).get("c");
      if (wanted) setActiveId(wanted);
    }, 0);
    // Statuses and online dots change without events; refresh them now and then.
    const poll = window.setInterval(() => {
      void loadPeople();
      void loadChats();
    }, 30_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(poll);
    };
  }, [loadChats, loadPeople]);

  useEffect(() => {
    window.__adverseActiveChat = activeId ?? undefined;
    const url = new URL(window.location.href);
    if (activeId) url.searchParams.set("c", activeId);
    else url.searchParams.delete("c");
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
    return () => {
      window.__adverseActiveChat = undefined;
    };
  }, [activeId]);

  // Keep the list in step with live events; the open thread listens on its own.
  useEffect(
    () =>
      subscribeRealtime((event) => {
        if (event.type === "chat.message") {
          const data = event.data as { conversation_id: string; own?: boolean; message: ChatMessage };
          setChats((current) => {
            if (!current) return current;
            const chat = current.find((item) => item.id === data.conversation_id);
            if (!chat) {
              void loadChats();
              return current;
            }
            const open = window.__adverseActiveChat === data.conversation_id && !document.hidden;
            const updated: Conversation = {
              ...chat,
              last_message: {
                id: data.message.id,
                sender_id: data.message.sender.id,
                sender_name: data.message.sender.name,
                preview: data.message.body || (data.message.attachments.length ? "📎 File" : ""),
                created_at: data.message.created_at,
              },
              unread: data.own || open ? chat.unread : chat.unread + 1,
            };
            return [updated, ...current.filter((item) => item.id !== chat.id)];
          });
        } else if (event.type === "chat.conversation" || event.type === "chat.message.updated") {
          void loadChats();
        }
      }),
    [loadChats],
  );

  const active = chats?.find((chat) => chat.id === activeId) ?? null;
  const isStaff = role !== "CLIENT";

  const counts = useMemo(() => {
    const list = chats ?? [];
    const unread = (items: Conversation[]) => items.reduce((sum, chat) => sum + chat.unread, 0);
    return {
      INBOX: unread(list),
      CLIENTS: unread(list.filter(isClientChat)),
      TEAM: unread(list.filter((chat) => chat.type === "GROUP")),
      DIRECT: unread(list.filter((chat) => chat.type === "DIRECT" && !isClientChat(chat))),
    };
  }, [chats]);

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (chats ?? []).filter((chat) => {
      if (folder === "CLIENTS" && !isClientChat(chat)) return false;
      if (folder === "TEAM" && chat.type !== "GROUP") return false;
      if (folder === "DIRECT" && !(chat.type === "DIRECT" && !isClientChat(chat))) return false;
      if (tab === "UNREAD" && chat.unread === 0) return false;
      if (tab === "MINE" && chat.created_by_id !== me?.id) return false;
      if (term && !`${chat.title} ${chat.client_name ?? ""}`.toLowerCase().includes(term)) return false;
      return true;
    });
  }, [chats, folder, tab, query, me]);

  // Message search (2+ letters), alongside the title filter.
  useEffect(() => {
    const term = query.trim();
    const timer = window.setTimeout(async () => {
      if (term.length < 2) return setFound([]);
      try {
        setFound((await chatApi<{ items: ChatMessage[] }>(`/search?q=${encodeURIComponent(term)}`)).items);
      } catch {
        setFound([]);
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  async function changeStatus(status: string) {
    try {
      const result = await chatApi<{ me: ChatPerson; people: ChatPerson[] }>("/status", jsonBody("PUT", { status }));
      setMe(result.me);
      setPeople(result.people);
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Could not change your status.");
    }
  }

  function opened(chat: Conversation) {
    setChats((current) => [chat, ...(current ?? []).filter((item) => item.id !== chat.id)]);
    setActiveId(chat.id);
    setDialog(null);
  }

  const folders: { key: Folder; label: string; icon: typeof Inbox }[] = [
    { key: "INBOX", label: "Inbox", icon: Inbox },
    { key: "CLIENTS", label: "Clients", icon: Contact },
    { key: "TEAM", label: "Team", icon: UsersRound },
    { key: "DIRECT", label: "Direct", icon: MessageSquare },
  ];

  return (
    <>
      <div className="chat-screen">
        {notice && (
          <div className="chat-notice" role="status">
            <span>{notice}</span>
            <button type="button" aria-label="Dismiss" onClick={() => setNotice("")}>
              <X />
            </button>
          </div>
        )}
        <section className={`chat-app${active ? " thread-open" : ""}${isStaff ? "" : " client"}`} aria-label="Chat">
          {isStaff && (
            <nav className="chat-folders" aria-label="Chat folders">
              {folders.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  type="button"
                  className={folder === key ? "active" : undefined}
                  aria-pressed={folder === key}
                  onClick={() => setFolder(key)}
                >
                  <Icon aria-hidden="true" />
                  <span>{label}</span>
                  {counts[key] > 0 && <em>{counts[key]}</em>}
                </button>
              ))}
              {me && (
                <div className="chat-me">
                  <Avatar person={{ ...me, status: me.status }} size={34} />
                  <div>
                    <strong>{me.name}</strong>
                    <LooplessSelect
                      value={me.status === "OFFLINE" ? "AVAILABLE" : me.status}
                      onValueChange={(value) => void changeStatus(value)}
                      ariaLabel="My status"
                      options={(["AVAILABLE", "BUSY", "AWAY"] as const).map((value) => ({
                        value,
                        label: STATUS_LABELS[value],
                      }))}
                    />
                  </div>
                </div>
              )}
            </nav>
          )}

          <div className="chat-list">
            <header>
              <h2>{isStaff ? folders.find((item) => item.key === folder)?.label : "Messages"}</h2>
              <NewChatMenu role={role} onPick={(kind) => setDialog({ kind })} />
            </header>
            <label className="chat-search">
              <Search aria-hidden="true" />
              <input
                value={query}
                placeholder="Search chats and messages"
                aria-label="Search chats and messages"
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div className="chat-tabs" role="tablist" aria-label="Filter chats">
              {(["ALL", "UNREAD", "MINE"] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={tab === key}
                  className={tab === key ? "active" : undefined}
                  onClick={() => setTab(key)}
                >
                  {key === "ALL" ? "All" : key === "UNREAD" ? "Unread" : "Mine"}
                </button>
              ))}
            </div>
            <div className="chat-list-body">
              {error ? (
                <div className="chat-empty">
                  {error}
                  <button type="button" className="chat-btn" onClick={() => void loadChats()}>
                    <RefreshCw /> Retry
                  </button>
                </div>
              ) : chats === null ? (
                <div className="chat-empty">
                  <RefreshCw className="spin" /> Loading chats…
                </div>
              ) : visible.length === 0 && found.length === 0 ? (
                <div className="chat-empty">
                  {query
                    ? "Nothing found."
                    : role === "CLIENT"
                      ? "Your agency will add you to a room. You can also message the admin."
                      : "No chats here yet. Start one with the + button."}
                </div>
              ) : (
                <ul className="chat-items">
                  {visible.map((chat) => {
                    const other = chat.type === "DIRECT" ? chat.members.find((m) => m.id !== me?.id) : undefined;
                    return (
                      <li key={chat.id}>
                        <button
                          type="button"
                          className={`chat-item${chat.id === activeId ? " active" : ""}${chat.unread ? " unread" : ""}`}
                          onClick={() => setActiveId(chat.id)}
                        >
                          {other ? (
                            <Avatar person={other} />
                          ) : (
                            <span className={`chat-avatar group ${chat.type.toLowerCase()}`}>
                              {chat.type === "CLIENT" ? <Contact /> : <UsersRound />}
                            </span>
                          )}
                          <span className="chat-item-text">
                            <span className="chat-item-top">
                              <strong>{chat.title}</strong>
                              {chat.last_message && <small>{listTime(chat.last_message.created_at)}</small>}
                            </span>
                            <span className="chat-item-bottom">
                              <span>
                                {chat.type === "CLIENT" && chat.client_name && chat.title !== chat.client_name
                                  ? `${chat.client_name} · `
                                  : ""}
                                {chat.last_message
                                  ? `${chat.last_message.sender_id === me?.id ? "You" : chat.last_message.sender_name.split(" ")[0]}: ${chat.last_message.preview}`
                                  : chat.type === "DIRECT" && other
                                    ? `${ROLE_LABELS[other.role]} · ${STATUS_LABELS[other.status]}`
                                    : `${chat.members.length} people`}
                              </span>
                              {chat.unread > 0 && <em>{chat.unread}</em>}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                  {found.length > 0 && (
                    <>
                      <li className="chat-found-label">Messages</li>
                      {found.map((message) => {
                        const chat = chats.find((item) => item.id === message.conversation_id);
                        return (
                          <li key={message.id}>
                            <button
                              type="button"
                              className="chat-item found"
                              onClick={() => setActiveId(message.conversation_id)}
                            >
                              <Avatar person={message.sender} size={30} />
                              <span className="chat-item-text">
                                <span className="chat-item-top">
                                  <strong>{chat?.title ?? "Chat"}</strong>
                                  <small>{listTime(message.created_at)}</small>
                                </span>
                                <span className="chat-item-bottom">
                                  <span>
                                    {message.sender.name.split(" ")[0]}: {message.body}
                                  </span>
                                </span>
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </>
                  )}
                </ul>
              )}
            </div>
          </div>

          <div className="chat-thread">
            {active && me ? (
              <Thread
                key={active.id}
                chat={active}
                me={me}
                role={role}
                onBack={() => setActiveId(null)}
                onRead={() =>
                  setChats((current) =>
                    (current ?? []).map((item) => (item.id === active.id ? { ...item, unread: 0 } : item)),
                  )
                }
                onEditPeople={() => setDialog({ kind: "people", chat: active })}
                onError={setNotice}
              />
            ) : (
              <div className="chat-thread-empty">
                <MessageSquare aria-hidden="true" />
                <strong>Pick a chat</strong>
                <span>
                  {role === "CLIENT"
                    ? "Your rooms and your chat with the admin are on the left."
                    : "Or start a new one with the + button."}
                </span>
              </div>
            )}
          </div>
        </section>
      </div>

      {dialog && dialog.kind !== "people" && (
        <NewChatDialog
          kind={dialog.kind}
          role={role}
          people={people}
          onClose={() => setDialog(null)}
          onOpened={opened}
        />
      )}
      {dialog?.kind === "people" && (
        <PeopleDialog
          chat={dialog.chat}
          people={people}
          me={me}
          onClose={() => setDialog(null)}
          onSaved={(chat) => {
            setChats((current) => (current ?? []).map((item) => (item.id === chat.id ? chat : item)));
            setDialog(null);
          }}
        />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ new chat */

function NewChatMenu({ role, onPick }: { role: ChatRole; onPick: (kind: "direct" | "group" | "room") => void }) {
  const [open, setOpen] = useState(false);
  const options: { kind: "direct" | "group" | "room"; label: string }[] = [
    { kind: "direct", label: role === "CLIENT" ? "Message the admin" : "Direct message" },
    ...(role === "ADMIN" || role === "MANAGER" ? [{ kind: "group" as const, label: "New team group" }] : []),
    ...(role === "ADMIN" ? [{ kind: "room" as const, label: "New client room" }] : []),
  ];
  return (
    <div className="chat-new">
      <button
        type="button"
        className="chat-icon-button primary"
        aria-label="New chat"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <MessageCirclePlus />
      </button>
      {open && (
        <ul className="chat-menu" role="menu">
          {options.map((option) => (
            <li key={option.kind}>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  onPick(option.kind);
                }}
              >
                {option.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PeoplePicker({
  people,
  selected,
  multiple,
  onToggle,
}: {
  people: ChatPerson[];
  selected: string[];
  multiple: boolean;
  onToggle: (id: string) => void;
}) {
  const [term, setTerm] = useState("");
  const shown = people.filter((person) => person.name.toLowerCase().includes(term.trim().toLowerCase()));
  return (
    <div className="chat-picker">
      <label className="chat-search small">
        <Search aria-hidden="true" />
        <input
          value={term}
          placeholder="Search people"
          aria-label="Search people"
          onChange={(event) => setTerm(event.target.value)}
        />
      </label>
      <ul>
        {shown.map((person) => {
          const on = selected.includes(person.id);
          return (
            <li key={person.id}>
              <button
                type="button"
                className={on ? "on" : undefined}
                aria-pressed={on}
                onClick={() => onToggle(person.id)}
              >
                <Avatar person={person} size={30} />
                <span>
                  <strong>{person.name}</strong>
                  <small>
                    {ROLE_LABELS[person.role]} · {STATUS_LABELS[person.status]}
                  </small>
                </span>
                {multiple && (
                  <i className="chat-check" aria-hidden="true">
                    {on && <Check />}
                  </i>
                )}
              </button>
            </li>
          );
        })}
        {shown.length === 0 && <li className="chat-picker-empty">Nobody found.</li>}
      </ul>
    </div>
  );
}

function NewChatDialog({
  kind,
  role,
  people,
  onClose,
  onOpened,
}: {
  kind: "direct" | "group" | "room";
  role: ChatRole;
  people: ChatPerson[];
  onClose: () => void;
  onOpened: (chat: Conversation) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [clientId, setClientId] = useState("");
  const [clients, setClients] = useState<{ id: string; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const team = people.filter((person) => person.role !== "CLIENT");
  const pool =
    kind === "direct"
      ? role === "CLIENT"
        ? people.filter((p) => p.role === "ADMIN")
        : people
      : team.filter((p) => (kind === "room" ? p.role !== "ADMIN" : true));

  useEffect(() => {
    if (kind !== "room") return;
    void fetch("/api/company/clients?page_size=100", { cache: "no-store" })
      .then((response) => response.json())
      .then((body: { items?: { id: string; name: string; status: string }[] }) =>
        setClients(
          (body.items ?? [])
            .filter((item) => item.status === "ACTIVE")
            .map((item) => ({ id: item.id, name: item.name })),
        ),
      )
      .catch(() => setClients([]));
  }, [kind]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      setBusy(true);
      if (kind === "direct") {
        if (!selected[0]) return setMessage("Pick a person.");
        onOpened(await chatApi<Conversation>("/direct", jsonBody("POST", { user_id: selected[0] })));
      } else if (kind === "group") {
        if (!title.trim()) return setMessage("Give the group a name.");
        if (!selected.length) return setMessage("Add at least one person.");
        onOpened(await chatApi<Conversation>("/groups", jsonBody("POST", { title, member_ids: selected })));
      } else {
        if (!clientId) return setMessage("Choose the client.");
        if (!title.trim()) return setMessage("Give the room a name.");
        onOpened(
          await chatApi<Conversation>("/rooms", jsonBody("POST", { client_id: clientId, title, member_ids: selected })),
        );
      }
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not start the chat.");
    } finally {
      setBusy(false);
    }
  }

  const heading =
    kind === "direct"
      ? role === "CLIENT"
        ? "Message the admin"
        : "Direct message"
      : kind === "group"
        ? "New team group"
        : "New client room";
  return (
    <ChatDialog title={heading} onClose={onClose} busy={busy}>
      <form className="chat-form" onSubmit={submit} noValidate>
        {message && (
          <div className="chat-form-message" role="alert">
            {message}
          </div>
        )}
        {kind === "room" && (
          <label className="chat-field">
            <span>Client</span>
            <LooplessSelect
              value={clientId}
              onValueChange={(value) => {
                setClientId(value);
                const client = clients.find((item) => item.id === value);
                if (client && !title) setTitle(`${client.name} · Videos`);
              }}
              ariaLabel="Client"
              options={[
                { value: "", label: "Choose a client" },
                ...clients.map((item) => ({ value: item.id, label: item.name })),
              ]}
            />
          </label>
        )}
        {kind !== "direct" && (
          <label className="chat-field">
            <span>{kind === "room" ? "Room name" : "Group name"}</span>
            <input
              value={title}
              maxLength={120}
              placeholder={kind === "room" ? "e.g. Diwali campaign" : "e.g. Editing team"}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
        )}
        <div className="chat-field">
          <span>
            {kind === "direct"
              ? "Person"
              : kind === "room"
                ? "Team members in this room (the client and you are added)"
                : "Members (you are added)"}
          </span>
          <PeoplePicker
            people={pool}
            selected={selected}
            multiple={kind !== "direct"}
            onToggle={(id) =>
              setSelected((current) =>
                kind === "direct"
                  ? [id]
                  : current.includes(id)
                    ? current.filter((item) => item !== id)
                    : [...current, id],
              )
            }
          />
        </div>
        <footer>
          <button type="button" className="chat-btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="chat-btn primary" disabled={busy}>
            {busy && <RefreshCw className="spin" />}
            {kind === "direct" ? "Open chat" : "Create"}
          </button>
        </footer>
      </form>
    </ChatDialog>
  );
}

function PeopleDialog({
  chat,
  people,
  me,
  onClose,
  onSaved,
}: {
  chat: Conversation;
  people: ChatPerson[];
  me: ChatPerson | null;
  onClose: () => void;
  onSaved: (chat: Conversation) => void;
}) {
  const fixed = new Set([chat.created_by_id, ...chat.members.filter((m) => m.role === "CLIENT").map((m) => m.id)]);
  const [title, setTitle] = useState(chat.title);
  const [selected, setSelected] = useState<string[]>(chat.members.map((m) => m.id).filter((id) => !fixed.has(id)));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const pool = people.filter((person) => person.role !== "CLIENT" && !fixed.has(person.id) && person.id !== me?.id);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      onSaved(
        await chatApi<Conversation>(
          `/conversations/${chat.id}`,
          jsonBody("PATCH", { title, member_ids: selected.length ? selected : [chat.created_by_id] }),
        ),
      );
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ChatDialog title={chat.type === "CLIENT" ? "Room settings" : "Group settings"} onClose={onClose} busy={busy}>
      <form className="chat-form" onSubmit={submit} noValidate>
        {message && (
          <div className="chat-form-message" role="alert">
            {message}
          </div>
        )}
        <label className="chat-field">
          <span>Name</span>
          <input value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <div className="chat-field">
          <span>
            {chat.type === "CLIENT" ? "Team members (the client and the room's creator always stay)" : "Members"}
          </span>
          <PeoplePicker
            people={pool}
            selected={selected}
            multiple
            onToggle={(id) =>
              setSelected((current) =>
                current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
              )
            }
          />
        </div>
        <footer>
          <button type="button" className="chat-btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="chat-btn primary" disabled={busy}>
            Save
          </button>
        </footer>
      </form>
    </ChatDialog>
  );
}

function ChatDialog({
  title,
  busy,
  onClose,
  children,
}: {
  title: string;
  busy: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => event.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);
  return (
    <div
      className="chat-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}
    >
      <section className="chat-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <h2>{title}</h2>
          <button type="button" className="chat-icon-button" aria-label="Close" onClick={onClose} disabled={busy}>
            <X />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ thread */

function Thread({
  chat,
  me,
  role,
  onBack,
  onRead,
  onEditPeople,
  onError,
}: {
  chat: Conversation;
  me: ChatPerson;
  role: ChatRole;
  onBack: () => void;
  onRead: () => void;
  onEditPeople: () => void;
  onError: (message: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [reads, setReads] = useState<Record<string, string | null>>(() =>
    Object.fromEntries(chat.members.map((member) => [member.id, member.last_read_at])),
  );
  const [typing, setTyping] = useState<Record<string, { name: string; until: number }>>({});
  const [reply, setReply] = useState<ChatMessage | null>(null);
  const [editing, setEditing] = useState<ChatMessage | null>(null);
  const [removing, setRemoving] = useState<ChatMessage | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const scroller = useRef<HTMLDivElement | null>(null);
  const stick = useRef(true);

  const markRead = useCallback(async () => {
    if (document.hidden) return;
    try {
      await chatApi(`/conversations/${chat.id}/read`, { method: "POST" });
      onRead();
    } catch {
      // Read receipts are best effort.
    }
  }, [chat.id, onRead]);

  useEffect(() => {
    let cancelled = false;
    void chatApi<{ items: ChatMessage[]; has_more: boolean }>(`/conversations/${chat.id}/messages?limit=50`)
      .then((result) => {
        if (cancelled) return;
        setMessages(result.items);
        setHasMore(result.has_more);
        void markRead();
      })
      .catch((reason) => onError(reason instanceof Error ? reason.message : "Could not load messages."));
    return () => {
      cancelled = true;
    };
  }, [chat.id, markRead, onError]);

  useEffect(
    () =>
      subscribeRealtime((event) => {
        const data = event.data as { conversation_id?: string };
        if (data.conversation_id !== chat.id) return;
        if (event.type === "chat.message" || event.type === "chat.message.updated") {
          const message = (event.data as { message: ChatMessage }).message;
          setMessages((current) => {
            const list = current ?? [];
            return list.some((item) => item.id === message.id)
              ? list.map((item) => (item.id === message.id ? message : item))
              : [...list, message];
          });
          if (event.type === "chat.message") {
            setTyping((current) => {
              const next = { ...current };
              delete next[message.sender.id];
              return next;
            });
            if (message.sender.id !== me.id) void markRead();
          }
        } else if (event.type === "chat.read") {
          const read = event.data as { user_id: string; last_read_at: string };
          setReads((current) => ({ ...current, [read.user_id]: read.last_read_at }));
        } else if (event.type === "chat.typing") {
          const who = event.data as { user_id: string; name: string };
          setTyping((current) => ({ ...current, [who.user_id]: { name: who.name, until: Date.now() + 4000 } }));
        }
      }),
    [chat.id, me.id, markRead],
  );

  // Clear typing labels that have run out.
  useEffect(() => {
    const timer = window.setInterval(() => {
      setTyping((current) => {
        const now = Date.now();
        const next = Object.fromEntries(Object.entries(current).filter(([, value]) => value.until > now));
        return Object.keys(next).length === Object.keys(current).length ? current : next;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  // Back on the tab: mark what arrived meanwhile as read.
  useEffect(() => {
    const onVisible = () => !document.hidden && void markRead();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [markRead]);

  useEffect(() => {
    if (stick.current) bottom.current?.scrollIntoView({ block: "end" });
  }, [messages, typing]);

  async function older() {
    const first = messages?.[0];
    if (!first) return;
    const box = scroller.current;
    const height = box?.scrollHeight ?? 0;
    try {
      const result = await chatApi<{ items: ChatMessage[]; has_more: boolean }>(
        `/conversations/${chat.id}/messages?limit=50&before=${encodeURIComponent(first.created_at)}`,
      );
      stick.current = false;
      setMessages((current) => [...result.items, ...(current ?? [])]);
      setHasMore(result.has_more);
      window.requestAnimationFrame(() => box && (box.scrollTop = box.scrollHeight - height));
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Could not load older messages.");
    }
  }

  const others = chat.members.filter((member) => member.id !== me.id);
  const direct = chat.type === "DIRECT" ? others[0] : undefined;
  const canManage =
    chat.type !== "DIRECT" && (role === "ADMIN" || (chat.type === "GROUP" && chat.created_by_id === me.id));
  const typingNames = Object.entries(typing)
    .filter(([id]) => id !== me.id)
    .map(([, value]) => value.name.split(" ")[0]);

  // "Seen" on my latest message once everyone else has read up to it.
  const lastMine = [...(messages ?? [])].reverse().find((message) => message.sender.id === me.id && !message.deleted);
  const seenBy = lastMine
    ? others.filter((member) => {
        const read = reads[member.id];
        return read && new Date(read) >= new Date(lastMine.created_at);
      })
    : [];

  let lastDay = "";
  return (
    <div className="chat-thread-inner">
      <header className="chat-thread-head">
        <button type="button" className="chat-icon-button back" aria-label="Back to chats" onClick={onBack}>
          <ArrowLeft />
        </button>
        {direct ? (
          <Avatar person={direct} size={38} />
        ) : (
          <span className={`chat-avatar group ${chat.type.toLowerCase()}`} style={{ width: 38, height: 38 }}>
            {chat.type === "CLIENT" ? <Contact /> : <UsersRound />}
          </span>
        )}
        <div className="chat-thread-title">
          <strong>{chat.title}</strong>
          <small>
            {direct
              ? `${ROLE_LABELS[direct.role]} · ${STATUS_LABELS[direct.status]}`
              : `${chat.type === "CLIENT" ? `Client room${chat.client_name ? ` · ${chat.client_name}` : ""} · ` : ""}${chat.members.length} people`}
          </small>
        </div>
        {!direct && (
          <div className="chat-faces" aria-label="People in this chat">
            {chat.members.slice(0, 5).map((member) => (
              <span
                key={member.id}
                title={`${member.name} · ${ROLE_LABELS[member.role]} · ${STATUS_LABELS[member.status]}`}
              >
                <Avatar person={member} size={28} />
              </span>
            ))}
            {chat.members.length > 5 && <em>+{chat.members.length - 5}</em>}
          </div>
        )}
        {canManage && (
          <button
            type="button"
            className="chat-icon-button"
            aria-label="Room settings"
            title="Name and people"
            onClick={onEditPeople}
          >
            <Settings2 />
          </button>
        )}
      </header>

      <div
        className="chat-messages"
        ref={scroller}
        onScroll={(event) => {
          const box = event.currentTarget;
          stick.current = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
        }}
      >
        {hasMore && (
          <button type="button" className="chat-older" onClick={() => void older()}>
            Load earlier messages
          </button>
        )}
        {messages === null ? (
          <div className="chat-empty">
            <RefreshCw className="spin" /> Loading messages…
          </div>
        ) : messages.length === 0 ? (
          <div className="chat-empty">No messages yet. Say hello 👋</div>
        ) : (
          messages.map((message, index) => {
            const day = dayLabel(message.created_at);
            const showDay = day !== lastDay;
            lastDay = day;
            const mine = message.sender.id === me.id;
            const previous = messages[index - 1];
            const grouped =
              !showDay &&
              previous &&
              previous.sender.id === message.sender.id &&
              new Date(message.created_at).getTime() - new Date(previous.created_at).getTime() < 5 * 60_000;
            return (
              <div key={message.id}>
                {showDay && (
                  <div className="chat-day">
                    <span>{day}</span>
                  </div>
                )}
                <div className={`chat-message${mine ? " mine" : ""}${grouped ? " grouped" : ""}`}>
                  {!mine && !grouped && <Avatar person={message.sender} size={30} />}
                  <div className="chat-bubble-wrap">
                    {!mine && !grouped && chat.type !== "DIRECT" && (
                      <span className="chat-sender">
                        {message.sender.name} <small>{ROLE_LABELS[message.sender.role]}</small>
                      </span>
                    )}
                    <div className={`chat-bubble${message.deleted ? " deleted" : ""}`}>
                      {message.reply_to && !message.deleted && (
                        <div className="chat-quote">
                          <strong>{message.reply_to.sender_name}</strong>
                          <span>{message.reply_to.preview}</span>
                        </div>
                      )}
                      {message.deleted ? (
                        <em>This message was deleted</em>
                      ) : (
                        <>
                          {message.body && <p>{message.body}</p>}
                          {message.attachments.map((file) =>
                            file.mime_type.startsWith("image/") ? (
                              <a
                                key={file.id}
                                className="chat-image"
                                href={`/api/chat/attachments/${file.id}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img src={`/api/chat/attachments/${file.id}`} alt={file.file_name} loading="lazy" />
                              </a>
                            ) : (
                              <a
                                key={file.id}
                                className="chat-file"
                                href={`/api/chat/attachments/${file.id}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <FileText />
                                <span>
                                  <strong>{file.file_name}</strong>
                                  <small>{fileSize(file.size_bytes)}</small>
                                </span>
                                <Download />
                              </a>
                            ),
                          )}
                        </>
                      )}
                      <span className="chat-meta">
                        {message.edited && "edited · "}
                        {clock(message.created_at)}
                        {mine && message.id === lastMine?.id && (
                          <span
                            className={`chat-seen${seenBy.length === others.length && others.length > 0 ? " all" : ""}`}
                            title={seenBy.length ? `Seen by ${seenBy.map((m) => m.name).join(", ")}` : "Sent"}
                          >
                            {seenBy.length ? <CheckCheck /> : <Check />}
                          </span>
                        )}
                      </span>
                    </div>
                    {!message.deleted && (
                      <div className="chat-actions">
                        <button type="button" aria-label="Reply" title="Reply" onClick={() => setReply(message)}>
                          <Reply />
                        </button>
                        {mine && (
                          <button type="button" aria-label="Edit" title="Edit" onClick={() => setEditing(message)}>
                            <Pencil />
                          </button>
                        )}
                        {(mine || role === "ADMIN") && (
                          <button type="button" aria-label="Delete" title="Delete" onClick={() => setRemoving(message)}>
                            <Trash2 />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
        {lastMine && seenBy.length > 0 && chat.type !== "DIRECT" && (
          <div className="chat-seen-line">Seen by {seenBy.map((member) => member.name.split(" ")[0]).join(", ")}</div>
        )}
        <div ref={bottom} />
      </div>

      <div className="chat-typing" aria-live="polite">
        {typingNames.length > 0 && `${typingNames.join(", ")} ${typingNames.length === 1 ? "is" : "are"} typing…`}
      </div>

      <Composer
        chatId={chat.id}
        reply={reply}
        editing={editing}
        onCancel={() => {
          setReply(null);
          setEditing(null);
        }}
        onSent={(message) => {
          stick.current = true;
          setReply(null);
          setEditing(null);
          setMessages((current) => {
            const list = current ?? [];
            return list.some((item) => item.id === message.id)
              ? list.map((item) => (item.id === message.id ? message : item))
              : [...list, message];
          });
        }}
        onError={onError}
      />

      <ConfirmationDialog
        open={removing !== null}
        title="Delete this message?"
        description="Everyone in the chat will see “This message was deleted”. Attached files are removed."
        confirmLabel="Delete"
        tone="danger"
        onCancel={() => setRemoving(null)}
        onConfirm={async () => {
          const target = removing;
          setRemoving(null);
          if (!target) return;
          try {
            const updated = await chatApi<ChatMessage>(`/messages/${target.id}`, { method: "DELETE" });
            setMessages((current) => (current ?? []).map((item) => (item.id === updated.id ? updated : item)));
          } catch (reason) {
            onError(reason instanceof Error ? reason.message : "Could not delete the message.");
          }
        }}
      />
    </div>
  );
}

function Composer({
  chatId,
  reply,
  editing,
  onCancel,
  onSent,
  onError,
}: {
  chatId: string;
  reply: ChatMessage | null;
  editing: ChatMessage | null;
  onCancel: () => void;
  onSent: (message: ChatMessage) => void;
  onError: (message: string) => void;
}) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const lastTyping = useRef(0);
  const box = useRef<HTMLTextAreaElement | null>(null);

  // Starting an edit puts the message's text in the box (state derived during render).
  const [editingId, setEditingId] = useState<string | null>(null);
  if ((editing?.id ?? null) !== editingId) {
    setEditingId(editing?.id ?? null);
    if (editing) setText(editing.body);
  }

  useEffect(() => {
    if (editing || reply) box.current?.focus();
  }, [editing, reply]);

  function typed(value: string) {
    setText(value);
    const now = Date.now();
    if (!editing && value && now - lastTyping.current > 3000) {
      lastTyping.current = now;
      void chatApi(`/conversations/${chatId}/typing`, { method: "POST" }).catch(() => undefined);
    }
  }

  async function send() {
    const body = text.trim();
    if (busy || (!body && files.length === 0)) return;
    setBusy(true);
    try {
      if (editing) {
        onSent(await chatApi<ChatMessage>(`/messages/${editing.id}`, jsonBody("PATCH", { body })));
      } else {
        const form = new FormData();
        form.append("body", body);
        if (reply) form.append("reply_to_id", reply.id);
        files.forEach((file) => form.append("files", file));
        onSent(await chatApi<ChatMessage>(`/conversations/${chatId}/messages`, { method: "POST", body: form }));
      }
      setText("");
      setFiles([]);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Could not send the message.");
    } finally {
      setBusy(false);
      box.current?.focus();
    }
  }

  return (
    <div className="chat-composer">
      {(reply || editing) && (
        <div className="chat-composer-context">
          {editing ? <Pencil /> : <Reply />}
          <span>
            <strong>{editing ? "Editing your message" : `Replying to ${reply?.sender.name}`}</strong>
            <small>{(editing ?? reply)?.body || "📎 File"}</small>
          </span>
          <button
            type="button"
            className="chat-icon-button"
            aria-label="Cancel"
            onClick={() => {
              setText("");
              onCancel();
            }}
          >
            <X />
          </button>
        </div>
      )}
      {files.length > 0 && (
        <ul className="chat-pending-files">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <Paperclip /> {file.name} <small>{fileSize(file.size)}</small>
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}
              >
                <X />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="chat-composer-row">
        {!editing && (
          <label className="chat-icon-button" title="Attach files (up to 25 MB each)">
            <Paperclip />
            <input
              type="file"
              multiple
              aria-label="Attach files"
              onChange={(event) => {
                const picked = Array.from(event.target.files ?? []);
                setFiles((current) => [...current, ...picked].slice(0, 10));
                event.target.value = "";
              }}
            />
          </label>
        )}
        <textarea
          ref={box}
          rows={1}
          value={text}
          maxLength={4000}
          placeholder="Write a message… (Enter to send, Shift+Enter for a new line)"
          aria-label="Message"
          onChange={(event) => typed(event.target.value)}
          onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
            if (event.key === "Escape" && (reply || editing)) {
              setText("");
              onCancel();
            }
          }}
        />
        <button
          type="button"
          className="chat-icon-button primary"
          aria-label={editing ? "Save" : "Send"}
          disabled={busy}
          onClick={() => void send()}
        >
          {busy ? <RefreshCw className="spin" /> : editing ? <Check /> : <Send />}
        </button>
      </div>
    </div>
  );
}
