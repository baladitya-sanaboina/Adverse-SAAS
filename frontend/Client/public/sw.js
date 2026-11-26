/*
 * Adverse service worker (owner request 2026-11-15): makes each app installable, shows push
 * notifications when the app is closed or in the background, and opens the right page when one
 * is clicked. Pages are always loaded from the network; when there is no connection a small
 * offline page is shown. Copied into each app's public/ folder; keep the copies the same.
 */
const OFFLINE = "/offline.html";
const CACHE = "adverse-offline-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll([OFFLINE, "/logos/adverse-favicon-192.png"]))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE)));
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: "Adverse", body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      // Every push must show a notification: Safari/iPhone cancel the subscription after a few
      // pushes that show nothing. When the app is open in front, the page already chimes, so
      // this one is silent.
      const inFront = windows.some((client) => client.visibilityState === "visible" && client.focused);
      await self.registration.showNotification(data.title || "Adverse", {
        body: data.body || "",
        tag: data.tag || undefined,
        renotify: Boolean(data.tag) && !inFront,
        silent: inFront,
        icon: "/logos/adverse-favicon-192.png",
        badge: "/logos/adverse-favicon-192.png",
        data: { link: data.link || "/" },
      });
    })(),
  );
});

function keyBytes(base64) {
  const padded = `${base64}${"=".repeat((4 - (base64.length % 4)) % 4)}`.replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}

// The browser replaced this device's push subscription: subscribe again and tell the server,
// so alerts keep arriving without the app having to be opened first.
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    (async () => {
      const response = await fetch("/api/push/key", { cache: "no-store", credentials: "include" });
      if (!response.ok) return;
      const { enabled, public_key: publicKey } = await response.json();
      if (!enabled || !publicKey) return;
      const subscription = await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(publicKey),
      });
      await fetch("/api/push/subscribe", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(subscription.toJSON()),
      });
    })().catch(() => undefined),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.link) || "/", self.location.origin);
  const isMail = target.pathname === "/mail";
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      // Mail opens in the mail tab; everything else in an app tab.
      const match = windows.find((client) => new URL(client.url).pathname.startsWith("/mail") === isMail);
      if (match) {
        await match.focus();
        return match.navigate(target.href);
      }
      return self.clients.openWindow(target.href);
    })(),
  );
});
