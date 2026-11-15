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
      // The app is open and in front: the page shows its own alert and plays the chime.
      if (windows.some((client) => client.visibilityState === "visible" && client.focused)) return;
      await self.registration.showNotification(data.title || "Adverse", {
        body: data.body || "",
        tag: data.tag || undefined,
        renotify: Boolean(data.tag),
        icon: "/logos/adverse-favicon-192.png",
        badge: "/logos/adverse-favicon-192.png",
        data: { link: data.link || "/" },
      });
    })(),
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
