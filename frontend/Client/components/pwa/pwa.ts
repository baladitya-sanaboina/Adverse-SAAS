// Copy of frontend/shared/pwa/pwa.ts (the Client app has no shared alias). Keep in sync.
/*
 * Installable app + Web Push (owner request 2026-11-15). The service worker (public/sw.js) shows
 * notifications when the app is closed or in the background; this file registers it, subscribes
 * the browser to push after notifications are allowed, and keeps the browser's "Install app"
 * offer so our own card can show it.
 */
const PUSH_KEY = "adverse-push-endpoint";

type InstallPrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
let installPrompt: InstallPrompt | null = null;
const listeners = new Set<() => void>();

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event as InstallPrompt;
    listeners.forEach((listener) => listener());
  });
  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    listeners.forEach((listener) => listener());
  });
}

function stored(): string | null {
  try {
    return window.localStorage.getItem(PUSH_KEY);
  } catch {
    return null;
  }
}

function remember(endpoint: string | null): void {
  try {
    if (endpoint) window.localStorage.setItem(PUSH_KEY, endpoint);
    else window.localStorage.removeItem(PUSH_KEY);
  } catch {
    // Not remembered: the page also shows desktop alerts itself.
  }
}

export function registerWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return Promise.resolve(null);
  return navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => null);
}

function keyBytes(base64: string): Uint8Array<ArrayBuffer> {
  const padded = `${base64}${"=".repeat((4 - (base64.length % 4)) % 4)}`.replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
  return bytes;
}

/** Subscribe this browser to push (after notifications are allowed). Quietly does nothing when
 * the browser or the server does not support it. */
export async function enablePush(): Promise<boolean> {
  try {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return false;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
    await registerWorker();
    const registration = await navigator.serviceWorker.ready;
    const keyResponse = await fetch("/api/push/key", { cache: "no-store" });
    if (!keyResponse.ok) return false;
    const { enabled, public_key: publicKey } = (await keyResponse.json()) as { enabled: boolean; public_key: string };
    if (!enabled || !publicKey) return false;
    const subscription =
      (await registration.pushManager.getSubscription()) ??
      (await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) }));
    const saved = await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription.toJSON()),
    });
    if (!saved.ok) return false;
    remember(subscription.endpoint);
    return true;
  } catch {
    return false;
  }
}

export async function disablePush(): Promise<void> {
  try {
    const registration = await navigator.serviceWorker.getRegistration("/");
    const subscription = await registration?.pushManager.getSubscription();
    if (subscription) {
      await fetch("/api/push/unsubscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: subscription.endpoint }),
      }).catch(() => undefined);
      await subscription.unsubscribe();
    }
  } catch {
    // Nothing more to do.
  } finally {
    remember(null);
  }
}

/** Push is on for this browser: the service worker shows background alerts, not the page. */
export function pushActive(): boolean {
  return typeof Notification !== "undefined" && Notification.permission === "granted" && Boolean(stored());
}

export function canInstall(): boolean {
  return installPrompt !== null;
}

export function installed(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(display-mode: standalone)").matches;
}

export function onInstallChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function install(): Promise<boolean> {
  if (!installPrompt) return false;
  const prompt = installPrompt;
  installPrompt = null;
  await prompt.prompt();
  const choice = await prompt.userChoice.catch(() => ({ outcome: "dismissed" }));
  listeners.forEach((listener) => listener());
  return choice.outcome === "accepted";
}
