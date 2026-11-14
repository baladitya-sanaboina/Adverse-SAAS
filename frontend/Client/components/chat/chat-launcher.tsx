// Copy of frontend/shared/chat/chat-launcher.tsx (the Client app has no shared alias). Keep in sync.
"use client";

/*
 * Floating chat button, bottom right on every page except the chat itself (owner request
 * 2026-11-14), with the number of unread messages. Rendered by each app's dashboard shell.
 */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { subscribeRealtime } from "@/lib/realtime";
import "@/styles/chat.css";

export function ChatLauncher() {
  const router = useRouter();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let active = true;
    const load = () =>
      void fetch("/api/chat/unread", { cache: "no-store" })
        .then((response) => (response.ok ? response.json() : null))
        .then((body: { unread_total?: number } | null) => {
          if (active && body) setUnread(Number(body.unread_total ?? 0));
        })
        .catch(() => undefined);
    load();
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type === "chat.message" && !(event.data as { own?: boolean }).own) setUnread((count) => count + 1);
      // Chats read elsewhere (another tab or device) lower the count.
      if (event.type === "notification.read") load();
    });
    window.addEventListener("focus", load);
    return () => {
      active = false;
      unsubscribe();
      window.removeEventListener("focus", load);
    };
  }, []);

  return (
    <button
      type="button"
      className="chat-launcher"
      aria-label={unread ? `Open chat, ${unread} unread` : "Open chat"}
      title="Chat"
      onClick={() => router.push("/chat")}
    >
      <MessagesSquare aria-hidden="true" />
      {unread > 0 && <em>{unread > 99 ? "99+" : unread}</em>}
    </button>
  );
}
