"use client";

/*
 * Notifications (Phase 10): live bell in the top bar, toasts, desktop alerts with a sound, and a
 * full Notifications page. Data: /api/notifications (own notifications only) and the live
 * /api/realtime/stream. Sound and desktop preferences are kept per device in localStorage.
 */
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, BellRing, Check, CheckCheck, Inbox, Volume2, VolumeX, X } from "lucide-react";
import { subscribeRealtime } from "../realtime/realtime";
import "../styles/notifications.css";

export type AppNotification = {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string;
  data: Record<string, unknown>;
  read: boolean;
  created_at: string;
};
type NotificationList = { items: AppNotification[]; unread_count: number };

const SOUND_KEY = "adverse-notify-sound";
const DESKTOP_KEY = "adverse-notify-desktop";

function readPref(key: string): boolean {
  try {
    return window.localStorage.getItem(key) !== "off";
  } catch {
    return true;
  }
}

function writePref(key: string, on: boolean) {
  try {
    window.localStorage.setItem(key, on ? "on" : "off");
  } catch {
    // Not remembered; harmless.
  }
}

async function request<T>(url: string, method = "GET"): Promise<T> {
  const response = await fetch(url, { method, cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return (await response.json()) as T;
}

function parseTime(value: string): Date {
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
}

export function timeAgo(value: string): string {
  const seconds = Math.round((parseTime(value).getTime() - Date.now()) / 1000);
  const format = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const abs = Math.abs(seconds);
  if (abs < 45) return "just now";
  if (abs < 3600) return format.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return format.format(Math.round(seconds / 3600), "hour");
  if (abs < 604800) return format.format(Math.round(seconds / 86400), "day");
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" }).format(parseTime(value));
}

let audio: AudioContext | null = null;

/** Short two-note chime made with Web Audio (no sound file needed). */
export function playChime() {
  try {
    const Context =
      window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Context) return;
    audio = audio ?? new Context();
    const ctx = audio;
    const now = ctx.currentTime;
    [880, 1318.5].forEach((frequency, index) => {
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      const start = now + index * 0.12;
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.16, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.38);
      oscillator.connect(gain).connect(ctx.destination);
      oscillator.start(start);
      oscillator.stop(start + 0.4);
    });
  } catch {
    // Audio is blocked until the user interacts with the page; the visual alert still shows.
  }
}

function showDesktop(item: AppNotification, onOpen: () => void): boolean {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return false;
  try {
    const alert = new Notification(item.title, { body: item.body, tag: item.id });
    alert.onclick = () => {
      window.focus();
      onOpen();
      alert.close();
    };
    return true;
  } catch {
    return false;
  }
}

/* ------------------------------------------------------------------------------------- bell */

export function NotificationBell() {
  const router = useRouter();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [toasts, setToasts] = useState<AppNotification[]>([]);
  const root = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await request<NotificationList>("/api/notifications?limit=8");
      setItems(data.items);
      setUnread(data.unread_count);
    } catch {
      // The bell stays quiet if notifications cannot be loaded.
    }
  }, []);

  const go = useCallback(
    (item: AppNotification) => {
      setOpen(false);
      setToasts((current) => current.filter((entry) => entry.id !== item.id));
      if (!item.read) {
        setItems((current) => current.map((entry) => (entry.id === item.id ? { ...entry, read: true } : entry)));
        void request<{ unread_count: number }>(`/api/notifications/${item.id}/read`, "POST")
          .then((result) => setUnread(result.unread_count))
          .catch(() => undefined);
      }
      if (item.link) router.push(item.link);
    },
    [router],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type === "notification") {
        const item = event.data as unknown as AppNotification;
        setItems((current) => [item, ...current.filter((entry) => entry.id !== item.id)].slice(0, 8));
        setUnread((count) => count + 1);
        if (readPref(SOUND_KEY)) playChime();
        const onDesktop = document.hidden && readPref(DESKTOP_KEY) && showDesktop(item, () => go(item));
        if (!onDesktop) {
          setToasts((current) => [...current.slice(-2), item]);
          window.setTimeout(() => setToasts((current) => current.filter((entry) => entry.id !== item.id)), 6000);
        }
        window.dispatchEvent(new CustomEvent("adverse-notification", { detail: item }));
      } else if (event.type === "notification.read") {
        const count = Number((event.data as { unread_count?: number }).unread_count ?? 0);
        setUnread(count);
        if (count === 0) setItems((current) => current.map((entry) => ({ ...entry, read: true })));
      }
    });
    return () => {
      window.clearTimeout(timer);
      unsubscribe();
    };
  }, [load, go]);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function markAll() {
    try {
      const result = await request<{ unread_count: number }>("/api/notifications/read-all", "POST");
      setUnread(result.unread_count);
      setItems((current) => current.map((entry) => ({ ...entry, read: true })));
    } catch {
      // Leave as is; the user can retry.
    }
  }

  return (
    <div className="notify-bell" ref={root}>
      <button
        type="button"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          if (!open) void load();
          setOpen((value) => !value);
        }}
      >
        <Bell width={18} height={18} strokeWidth={1.8} aria-hidden="true" />
        {unread > 0 && <b className="notify-count">{unread > 99 ? "99+" : unread}</b>}
      </button>
      {open && (
        <div className="notify-panel" role="dialog" aria-label="Notifications">
          <header>
            <strong>Notifications</strong>
            {unread > 0 && (
              <button type="button" onClick={() => void markAll()}>
                <CheckCheck aria-hidden="true" /> Mark all read
              </button>
            )}
          </header>
          {items.length === 0 ? (
            <p className="notify-empty">
              <Inbox aria-hidden="true" />
              You&apos;re all caught up.
            </p>
          ) : (
            <ul>
              {items.map((item) => (
                <li key={item.id}>
                  <button type="button" className={item.read ? "" : "unread"} onClick={() => go(item)}>
                    <i aria-hidden="true" />
                    <span>
                      <strong>{item.title}</strong>
                      {item.body && <small>{item.body}</small>}
                      <em>{timeAgo(item.created_at)}</em>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <footer>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                router.push("/notifications");
              }}
            >
              View all notifications
            </button>
          </footer>
        </div>
      )}
      {toasts.length > 0 && (
        <div className="notify-toasts" aria-live="polite">
          {toasts.map((item) => (
            <div key={item.id} className="notify-toast">
              <BellRing aria-hidden="true" />
              <button type="button" onClick={() => go(item)}>
                <strong>{item.title}</strong>
                {item.body && <small>{item.body}</small>}
              </button>
              <button
                type="button"
                className="close"
                aria-label="Dismiss"
                onClick={() => setToasts((current) => current.filter((entry) => entry.id !== item.id))}
              >
                <X aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------------------------- page */

export function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);
  const [error, setError] = useState("");
  const [sound, setSound] = useState(true);
  const [desktop, setDesktop] = useState(true);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default");

  const load = useCallback(
    async (before?: string) => {
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams({ limit: "30" });
        if (filter === "unread") params.set("unread", "true");
        if (before) params.set("before", before);
        const data = await request<NotificationList>(`/api/notifications?${params}`);
        setItems((current) => (before ? [...current, ...data.items] : data.items));
        setUnread(data.unread_count);
        setMore(data.items.length === 30);
      } catch {
        setError("Unable to load notifications.");
      } finally {
        setLoading(false);
      }
    },
    [filter],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSound(readPref(SOUND_KEY));
      setDesktop(readPref(DESKTOP_KEY));
      setPermission(typeof Notification === "undefined" ? "unsupported" : Notification.permission);
      void load();
    }, 0);
    const onNew = (event: Event) => {
      const item = (event as CustomEvent<AppNotification>).detail;
      setItems((current) => [item, ...current.filter((entry) => entry.id !== item.id)]);
      setUnread((count) => count + 1);
    };
    window.addEventListener("adverse-notification", onNew);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("adverse-notification", onNew);
    };
  }, [load]);

  async function open(item: AppNotification) {
    if (!item.read) {
      setItems((current) => current.map((entry) => (entry.id === item.id ? { ...entry, read: true } : entry)));
      try {
        const result = await request<{ unread_count: number }>(`/api/notifications/${item.id}/read`, "POST");
        setUnread(result.unread_count);
      } catch {
        // Still navigate.
      }
    }
    if (item.link) router.push(item.link);
  }

  async function markAll() {
    try {
      const result = await request<{ unread_count: number }>("/api/notifications/read-all", "POST");
      setUnread(result.unread_count);
      setItems((current) => (filter === "unread" ? [] : current.map((entry) => ({ ...entry, read: true }))));
    } catch {
      setError("Unable to mark notifications as read.");
    }
  }

  async function toggleDesktop() {
    if (typeof Notification === "undefined") return;
    if (!desktop || Notification.permission !== "granted") {
      if (typeof Notification !== "undefined" && Notification.permission === "default") {
        const result = await Notification.requestPermission();
        setPermission(result);
        if (result !== "granted") return;
      }
      writePref(DESKTOP_KEY, true);
      setDesktop(true);
      return;
    }
    writePref(DESKTOP_KEY, false);
    setDesktop(false);
  }

  const today = new Date().toDateString();
  const groups = [
    { title: "Today", items: items.filter((item) => parseTime(item.created_at).toDateString() === today) },
    { title: "Earlier", items: items.filter((item) => parseTime(item.created_at).toDateString() !== today) },
  ].filter((group) => group.items.length > 0);
  const desktopOn = desktop && permission === "granted";

  return (
    <div className="dash-content notify-page">
      <header className="notify-page-head">
        <div>
          <h1>Notifications</h1>
          <p>{unread === 0 ? "You're all caught up." : `${unread} unread`}</p>
        </div>
        <div className="notify-page-actions">
          <div className="notify-tabs" role="group" aria-label="Show">
            <button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>
              All
            </button>
            <button type="button" className={filter === "unread" ? "active" : ""} onClick={() => setFilter("unread")}>
              Unread {unread > 0 && <b>{unread}</b>}
            </button>
          </div>
          <button type="button" className="notify-secondary" onClick={() => void markAll()} disabled={unread === 0}>
            <CheckCheck aria-hidden="true" /> Mark all read
          </button>
        </div>
      </header>

      <section className="notify-settings" aria-label="Alert settings">
        <button
          type="button"
          className={sound ? "on" : ""}
          aria-pressed={sound}
          onClick={() => {
            writePref(SOUND_KEY, !sound);
            setSound(!sound);
            if (!sound) playChime();
          }}
        >
          {sound ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
          <span>
            <strong>Sound</strong>
            <small>{sound ? "A chime plays for new notifications" : "Silent"}</small>
          </span>
        </button>
        <button
          type="button"
          className={desktopOn ? "on" : ""}
          aria-pressed={desktopOn}
          disabled={permission === "unsupported" || permission === "denied"}
          onClick={() => void toggleDesktop()}
        >
          <BellRing aria-hidden="true" />
          <span>
            <strong>Desktop alerts</strong>
            <small>
              {permission === "unsupported"
                ? "Not supported by this browser"
                : permission === "denied"
                  ? "Blocked in your browser settings"
                  : desktopOn
                    ? "Shown when this tab is in the background"
                    : "Off. Click to allow"}
            </small>
          </span>
        </button>
      </section>

      {error && <div className="notify-error">{error}</div>}

      {loading && items.length === 0 ? (
        <div className="notify-skeleton" aria-busy="true">
          {[1, 2, 3, 4].map((row) => (
            <i key={row} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="notify-page-empty">
          <Inbox aria-hidden="true" />
          <h3>{filter === "unread" ? "No unread notifications" : "No notifications yet"}</h3>
          <p>Task updates, payments and messages will appear here.</p>
        </div>
      ) : (
        groups.map((group) => (
          <section key={group.title} className="notify-group">
            <h2>{group.title}</h2>
            <ul>
              {group.items.map((item) => (
                <li key={item.id}>
                  <button type="button" className={item.read ? "" : "unread"} onClick={() => void open(item)}>
                    <i aria-hidden="true" />
                    <span>
                      <strong>{item.title}</strong>
                      {item.body && <small>{item.body}</small>}
                    </span>
                    <em>{timeAgo(item.created_at)}</em>
                    {!item.read && <Check className="mark" aria-label="Unread" />}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
      {more && (
        <button
          type="button"
          className="notify-more"
          disabled={loading}
          onClick={() => void load(items[items.length - 1]?.created_at)}
        >
          {loading ? "Loading…" : "Show older"}
        </button>
      )}
    </div>
  );
}
