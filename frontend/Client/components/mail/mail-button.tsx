// Copy of frontend/shared/mail/mail-button.tsx (the Client app has no shared alias). Keep in sync.
"use client";

/*
 * The mail icon next to the bell (owner request 2026-11-15): a red count of unread mail, and a
 * click opens Mail in its own tab (one tab, reused).
 */
import { useCallback, useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { subscribeRealtime } from "@/lib/realtime";
import { mailApi, openMail, type Counts } from "./mail-types";
import "@/styles/mail-button.css";

export function MailButton() {
  const [unread, setUnread] = useState(0);

  const load = useCallback(async () => {
    try {
      const counts = await mailApi<Counts>("/unread");
      setUnread(counts.total);
    } catch {
      // The icon stays without a count.
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    let refresh: number | undefined;
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type !== "mail.new" && event.type !== "mail.read") return;
      window.clearTimeout(refresh);
      refresh = window.setTimeout(() => void load(), 300);
    });
    // Reading mail in the other tab updates this count when you come back.
    const onFocus = () => void load();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(refresh);
      unsubscribe();
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);

  return (
    <button
      type="button"
      className="mail-top-button"
      aria-label={unread ? `Mail, ${unread} unread` : "Mail"}
      title="Open Mail (new tab)"
      onClick={() => openMail("/mail")}
    >
      <Mail width={18} height={18} strokeWidth={1.8} aria-hidden="true" />
      {unread > 0 && <b className="mail-top-count">{unread > 99 ? "99+" : unread}</b>}
    </button>
  );
}
