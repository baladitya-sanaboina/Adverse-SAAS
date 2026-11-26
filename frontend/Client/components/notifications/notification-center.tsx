// Copy of frontend/shared/notifications/notification-center.tsx (the Client app cannot import shared/). Keep in sync.
"use client";

/*
 * Notifications (Phase 10): live bell in the top bar, toasts, desktop alerts with a sound, and a
 * full Notifications page. Data: /api/notifications (own notifications only) and the live
 * /api/realtime/stream. Sound and desktop preferences are kept per device in localStorage.
 */
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Bell, BellRing, Check, CheckCheck, Cookie, Download, Inbox, Volume2, VolumeX, X } from "lucide-react";
import { MAIL_WINDOW } from "@/components/mail/mail-types";
import {
  canInstall,
  disablePush,
  enablePush,
  install,
  installed,
  onInstallChange,
  pushActive,
  registerWorker,
} from "@/components/pwa/pwa";
import { subscribeRealtime } from "@/lib/realtime";
import "@/styles/notifications.css";

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

function audioContext(): AudioContext | null {
  const Context =
    window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Context) return null;
  audio = audio ?? new Context();
  return audio;
}

/**
 * Browsers keep audio locked until the person clicks or types once on the page. We unlock it on
 * the first interaction so a chime can play when a notification arrives later.
 */
function unlockAudioOnce() {
  const unlock = () => {
    try {
      void audioContext()?.resume();
    } catch {
      // Sound stays off; the visual alert still shows.
    }
  };
  window.addEventListener("pointerdown", unlock, { once: true, capture: true });
  window.addEventListener("keydown", unlock, { once: true, capture: true });
}

/** Soft three-note bell made with Web Audio (no sound file needed). */
export function playChime() {
  try {
    const ctx = audioContext();
    if (!ctx) return;
    if (ctx.state === "suspended") void ctx.resume();
    const now = ctx.currentTime + 0.02;
    const master = ctx.createGain();
    master.gain.value = 0.22;
    master.connect(ctx.destination);
    // E6, G#6, B6: a bright, friendly major arpeggio with a soft bell overtone.
    [1318.5, 1661.2, 1975.5].forEach((frequency, index) => {
      const start = now + index * 0.09;
      [
        { ratio: 1, level: 1, type: "sine" as OscillatorType },
        { ratio: 2.01, level: 0.18, type: "sine" as OscillatorType },
        { ratio: 0.5, level: 0.12, type: "triangle" as OscillatorType },
      ].forEach((partial) => {
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = partial.type;
        oscillator.frequency.value = frequency * partial.ratio;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(partial.level, start + 0.012);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.9);
        oscillator.connect(gain).connect(master);
        oscillator.start(start);
        oscillator.stop(start + 0.95);
      });
    });
  } catch {
    // Audio is blocked until the user interacts with the page; the visual alert still shows.
  }
}

/** Phones (Android Chrome) refuse `new Notification()`; there only the service worker can show one. */
function showThroughWorker(title: string, body: string, tag: string, link: string): boolean {
  if (!("serviceWorker" in navigator)) return false;
  void navigator.serviceWorker.ready
    .then((registration) => registration.showNotification(title, { body, tag, data: { link } }))
    .catch(() => undefined);
  return true;
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
    return showThroughWorker(item.title, item.body, item.id, item.link || "/");
  }
}

/** Renders fixed overlays on <body>: the top bar's backdrop-filter would otherwise trap them inside it. */
function BodyPortal({ children }: { children: ReactNode }) {
  return typeof document === "undefined" ? null : createPortal(children, document.body);
}

/* --------------------------------------------------------------------------- permission cards */

const COOKIE_KEY = "adverse-cookie-consent";
const ASKED_KEY = "adverse-notify-asked";
const INSTALL_KEY = "adverse-install-asked";
const ASK_AGAIN_MS = 3 * 24 * 60 * 60 * 1000;

function stored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Two small cards, one at a time, in the app's own style (owner request 2026-11-14):
 * 1. cookies: we only use the sign-in cookies that keep you logged in for 7 days;
 * 2. notifications: asks the browser for permission to show alerts and play a sound.
 * "Not now" on the alerts card asks again after 3 days.
 */
/** iPhone/iPad Safari has no notifications at all until the app is added to the Home Screen. */
function iosNeedsHomeScreen(): boolean {
  const ios =
    /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return ios && !installed() && Date.now() - Number(stored(INSTALL_KEY) ?? 0) > ASK_AGAIN_MS;
}

function PermissionPrompts() {
  const [step, setStep] = useState<"cookies" | "alerts" | "install" | "ios" | null>(null);

  useEffect(() => {
    const offerInstall = () =>
      canInstall() && !installed() && Date.now() - Number(stored(INSTALL_KEY) ?? 0) > ASK_AGAIN_MS;
    const timer = window.setTimeout(() => {
      if (stored(COOKIE_KEY) !== "accepted") return setStep("cookies");
      if (typeof Notification !== "undefined" && Notification.permission === "default") {
        const asked = Number(stored(ASKED_KEY) ?? 0);
        if (Date.now() - asked > ASK_AGAIN_MS) return setStep("alerts");
      }
      if (iosNeedsHomeScreen()) return setStep("ios");
      if (offerInstall()) setStep("install");
    }, 1200);
    // The browser can offer "Install" a little after the page loads.
    const off = onInstallChange(() => setStep((current) => current ?? (offerInstall() ? "install" : null)));
    return () => {
      window.clearTimeout(timer);
      off();
    };
  }, []);

  const nextAfterCookies = () => {
    writeRaw(COOKIE_KEY, "accepted");
    const askAlerts =
      typeof Notification !== "undefined" &&
      Notification.permission === "default" &&
      Date.now() - Number(stored(ASKED_KEY) ?? 0) > 3 * 24 * 60 * 60 * 1000;
    setStep(askAlerts ? "alerts" : iosNeedsHomeScreen() ? "ios" : null);
  };

  const allowAlerts = async () => {
    writeRaw(ASKED_KEY, String(Date.now()));
    setStep(null);
    try {
      void audioContext()?.resume();
      const result = await Notification.requestPermission();
      if (result === "granted") {
        writePref(DESKTOP_KEY, true);
        writePref(SOUND_KEY, true);
        // Also when the app is closed (Web Push). First, so a failing test alert cannot skip it.
        void enablePush();
        playChime();
        const title = "Notifications are on";
        const body = "You will hear a chime for new updates.";
        try {
          new Notification(title, { body });
        } catch {
          showThroughWorker(title, body, "notifications-on", "/");
        }
      }
    } catch {
      // The browser refused to ask; the setting stays available on the Notifications page.
    }
  };

  if (!step) return null;
  return (
    <BodyPortal>
      <div
        className="notify-consent"
        role="dialog"
        aria-live="polite"
        aria-label={
          step === "cookies" ? "Cookies" : step === "install" || step === "ios" ? "Install the app" : "Notifications"
        }
      >
        <span className="notify-consent-icon" aria-hidden="true">
          {step === "cookies" ? <Cookie /> : step === "install" || step === "ios" ? <Download /> : <BellRing />}
        </span>
        <div>
          <strong>
            {step === "cookies"
              ? "We use cookies"
              : step === "install"
                ? "Install Adverse as an app"
                : step === "ios"
                  ? "Get alerts on this iPhone"
                  : "Turn on notifications?"}
          </strong>
          <p>
            {step === "cookies"
              ? "Only the sign-in cookies that keep you logged in for 7 days on this device. No ads, no tracking."
              : step === "install"
                ? "Open it from your dock, taskbar or home screen like any app. Alerts arrive even when it is closed."
                : step === "ios"
                  ? "Tap Share, then Add to Home Screen. Open Adverse from that icon and allow notifications; alerts then arrive even when it is closed."
                  : "Get an alert with a sound when a task is assigned, approved or paid, even when Adverse is closed."}
          </p>
          <div className="notify-consent-actions">
            {step === "cookies" ? (
              <button type="button" className="primary" onClick={nextAfterCookies}>
                Accept
              </button>
            ) : step === "ios" ? (
              <button
                type="button"
                className="primary"
                onClick={() => {
                  writeRaw(INSTALL_KEY, String(Date.now()));
                  setStep(null);
                }}
              >
                Got it
              </button>
            ) : step === "install" ? (
              <>
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    writeRaw(INSTALL_KEY, String(Date.now()));
                    setStep(null);
                    void install();
                  }}
                >
                  Install
                </button>
                <button
                  type="button"
                  onClick={() => {
                    writeRaw(INSTALL_KEY, String(Date.now()));
                    setStep(null);
                  }}
                >
                  Not now
                </button>
              </>
            ) : (
              <>
                <button type="button" className="primary" onClick={() => void allowAlerts()}>
                  Allow
                </button>
                <button
                  type="button"
                  onClick={() => {
                    writeRaw(ASKED_KEY, String(Date.now()));
                    setStep(null);
                  }}
                >
                  Not now
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </BodyPortal>
  );
}

function writeRaw(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Not remembered; the card may show again.
  }
}

/* ------------------------------------------------------------------------------------- bell */

// Mail lives in its own tab (2026-11-15): mail links open (or reuse) that tab.
function follow(link: string, push: (href: string) => void): void {
  if (link === "/mail" || link.startsWith("/mail?")) {
    window.open(link, MAIL_WINDOW)?.focus();
    return;
  }
  push(link);
}

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
      if (item.link) follow(item.link, router.push);
    },
    [router],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
      // The installable app and Web Push (2026-11-15): keep this browser subscribed.
      void registerWorker().then(() => {
        if (typeof Notification !== "undefined" && Notification.permission === "granted" && readPref(DESKTOP_KEY)) {
          void enablePush();
        }
      });
    }, 0);
    unlockAudioOnce();
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type === "notification") {
        const item = event.data as unknown as AppNotification & { replaced?: boolean };
        setItems((current) => [item, ...current.filter((entry) => entry.id !== item.id)].slice(0, 8));
        // A chat notification that counts up ("3 new messages") is already in the unread count.
        if (!item.replaced) setUnread((count) => count + 1);
        const away = document.hidden || !document.hasFocus();
        // No alert for a chat that is open on screen; reading it clears the notification.
        const openChat = (window as { __adverseActiveChat?: string }).__adverseActiveChat;
        if (item.type === "chat.message" && !away && openChat && openChat === item.data?.conversation_id) return;
        if (readPref(SOUND_KEY)) playChime();
        // With Web Push on, the service worker shows the alert when the app is in the background.
        const byWorker = away && pushActive();
        const onDesktop = !byWorker && away && readPref(DESKTOP_KEY) && showDesktop(item, () => go(item));
        if (!onDesktop && !byWorker) {
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
      <PermissionPrompts />
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
        <BodyPortal>
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
        </BodyPortal>
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
    if (item.link) follow(item.link, router.push);
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
      void enablePush();
      return;
    }
    writePref(DESKTOP_KEY, false);
    setDesktop(false);
    void disablePush();
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
