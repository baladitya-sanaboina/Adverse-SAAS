"use client";

/*
 * Meetings on calendars (owner request 2026-11-14): meetings scheduled in chats show on every
 * role's calendar, with a Join button from 10 minutes before the start until the end.
 */
import { useCallback, useEffect, useState } from "react";
import { Phone, Video } from "lucide-react";
import { useLiveRefresh } from "../realtime/realtime";
import { startCall } from "../chat/call-manager";

export type CalendarMeeting = {
  id: string;
  conversation_id: string;
  conversation_title: string;
  title: string;
  notes: string;
  starts_at: string;
  ends_at: string;
  duration_minutes: number;
  kind: "AUDIO" | "VIDEO";
  created_by_name: string;
};

export function localDay(value: string): string {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function useMeetings(start: string, end: string): CalendarMeeting[] {
  const [items, setItems] = useState<CalendarMeeting[]>([]);
  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        start: new Date(`${start}T00:00:00`).toISOString(),
        end: new Date(`${end}T23:59:59`).toISOString(),
      });
      const response = await fetch(`/api/chat/meetings?${params}`, { cache: "no-store" });
      if (!response.ok) return setItems([]);
      setItems(((await response.json()) as { items: CalendarMeeting[] }).items);
    } catch {
      setItems([]);
    }
  }, [start, end]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  useLiveRefresh(["chat.meeting"], () => void load());
  return items;
}

export function meetingTime(meeting: CalendarMeeting): string {
  return new Date(meeting.starts_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

export function MeetingCard({ meeting, now }: { meeting: CalendarMeeting; now: number }) {
  const open = now >= new Date(meeting.starts_at).getTime() - 10 * 60_000 && now <= new Date(meeting.ends_at).getTime();
  const Icon = meeting.kind === "VIDEO" ? Video : Phone;
  return (
    <article className="cal-card meeting">
      <div className="cal-card-title static">
        <small>
          <Icon aria-hidden="true" /> {meetingTime(meeting)} · {meeting.duration_minutes} min ·{" "}
          {meeting.conversation_title}
        </small>
        <strong>{meeting.title}</strong>
        {meeting.notes && <small>{meeting.notes}</small>}
      </div>
      <div className="cal-card-foot">
        <button
          type="button"
          className="cal-join"
          disabled={!open}
          title={open ? "Join now" : "Opens 10 minutes before the start"}
          onClick={() => startCall(meeting.conversation_id, meeting.kind, meeting.conversation_title)}
        >
          <Icon aria-hidden="true" /> Join
        </button>
        <span>Set by {meeting.created_by_name}</span>
      </div>
    </article>
  );
}
