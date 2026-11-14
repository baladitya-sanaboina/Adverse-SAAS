// Copy of frontend/shared/realtime/realtime.ts (the Client app cannot import shared/). Keep in sync.
/*
 * One live connection per browser tab to /api/realtime/stream (Server-Sent Events).
 * Events are { type, data }: "notification", "notification.read", and chat events (Phase 14).
 * EventSource reconnects by itself; if the server closes the stream (e.g. signed out) we retry later.
 */

export type RealtimeEvent = { type: string; data: Record<string, unknown> };
type Handler = (event: RealtimeEvent) => void;

const handlers = new Set<Handler>();
let source: EventSource | null = null;
let retryTimer: number | null = null;

function connect() {
  if (typeof window === "undefined" || source) return;
  source = new EventSource("/api/realtime/stream");
  source.onmessage = (message) => {
    let event: RealtimeEvent;
    try {
      event = JSON.parse(message.data) as RealtimeEvent;
    } catch {
      return;
    }
    handlers.forEach((handler) => {
      try {
        handler(event);
      } catch {
        // One broken listener must not stop the others.
      }
    });
  };
  source.onerror = () => {
    if (source && source.readyState === EventSource.CLOSED) {
      source.close();
      source = null;
      if (retryTimer === null) {
        retryTimer = window.setTimeout(() => {
          retryTimer = null;
          connect();
        }, 15000);
      }
    }
  };
}

/** Listen to live events. Returns an unsubscribe function. The connection stays open. */
export function subscribeRealtime(handler: Handler): () => void {
  handlers.add(handler);
  connect();
  return () => {
    handlers.delete(handler);
  };
}
