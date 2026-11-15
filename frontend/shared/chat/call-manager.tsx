"use client";

/*
 * Calls (owner requests 2026-11-14): a call opens in its own tab, like Google Meet, at
 * /call/<code> (see call-room.tsx). This component is rendered once by each app's dashboard
 * shell and only rings: an incoming call shows a card on every page with Join (opens the call
 * tab) and Decline.
 * Pages start or join a call with startCall() / joinCall(), and open a meet link with openMeet().
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Phone, PhoneOff, Video } from "lucide-react";
import { subscribeRealtime } from "../realtime/realtime";
import { chatApi, initials } from "./chat-types";
import { repeat, sounds } from "./call-sounds";
import "../styles/chat.css";

type Kind = "AUDIO" | "VIDEO";
type Ring = {
  call_id: string;
  conversation_id: string;
  kind: Kind;
  title: string;
  code?: string | null;
  from: { id: string; name: string };
};

/** One named window for calls, so a second Join brings the same tab forward. */
function openCallTab(path: string): void {
  const tab = window.open(path, "adverse-call");
  if (tab) tab.focus();
  else window.location.assign(path); // pop-ups blocked: open the call here
}

/** Start a call in a chat (or join the one already running there) in the call tab. */
export function startCall(conversationId: string, kind: Kind, title?: string): void {
  void title;
  openCallTab(`/call/new?c=${encodeURIComponent(conversationId)}&kind=${kind}`);
}

/** Join the call running in a chat, in the call tab. */
export function joinCall(callId: string, conversationId: string, kind: Kind, title?: string): void {
  void callId;
  startCall(conversationId, kind, title);
}

/** Open a meet link by its code. */
export function openMeet(code: string, kind?: Kind): void {
  openCallTab(`/call/${encodeURIComponent(code)}${kind ? `?kind=${kind}` : ""}`);
}

/** The full meet link to share. */
export function meetUrl(code: string): string {
  return `${window.location.origin}/call/${code}`;
}

/** The chat's meet link (members only), copied to the clipboard. Returns the link. */
export async function copyMeetLink(conversationId: string): Promise<string> {
  const { code } = await chatApi<{ code: string }>(`/conversations/${conversationId}/link`);
  const url = meetUrl(code);
  await navigator.clipboard?.writeText(url).catch(() => undefined);
  return url;
}

export function CallManager() {
  const [ring, setRing] = useState<Ring | null>(null);
  const meRef = useRef<string | null>(null);

  const whoAmI = useCallback(async () => {
    if (meRef.current) return meRef.current;
    const people = await chatApi<{ me: { id: string } }>("/people").catch(() => null);
    meRef.current = people?.me.id ?? null;
    return meRef.current;
  }, []);

  useEffect(
    () =>
      subscribeRealtime((event) => {
        const data = event.data as Record<string, unknown>;
        if (event.type === "call.ring") {
          setRing(data as unknown as Ring);
        } else if (event.type === "call.update") {
          const update = data.call as { id: string; ended_at: string | null; participants: { id: string }[] };
          void whoAmI().then((me) =>
            setRing((current) => {
              if (!current || current.call_id !== update.id) return current;
              // Stop ringing once the call ends or I have joined it in the call tab.
              if (update.ended_at || update.participants.some((seat) => seat.id === me)) return null;
              return current;
            }),
          );
        }
      }),
    [whoAmI],
  );

  // Ring tone while a call is coming in; give up after 40 seconds.
  useEffect(() => {
    if (!ring) return;
    const stopTone = repeat(sounds.ring, 2600);
    const stop = window.setTimeout(() => setRing(null), 40_000);
    return () => {
      stopTone();
      window.clearTimeout(stop);
    };
  }, [ring]);

  if (!ring) return null;

  function accept(kind: Kind) {
    if (!ring) return;
    openCallTab(ring.code ? `/call/${ring.code}?kind=${kind}` : `/call/new?c=${ring.conversation_id}&kind=${kind}`);
    setRing(null);
  }

  return (
    <div className="call-incoming" role="alertdialog" aria-label={`Incoming call from ${ring.from.name}`}>
      <span className="call-incoming-avatar">{initials(ring.from.name)}</span>
      <div>
        <strong>{ring.from.name}</strong>
        <small>
          {ring.kind === "VIDEO" ? "Video call" : "Voice call"}
          {ring.title && ring.title !== ring.from.name ? ` · ${ring.title}` : ""}
        </small>
      </div>
      <div className="call-incoming-actions">
        <button
          type="button"
          className="call-round decline"
          aria-label="Decline"
          title="Decline"
          onClick={() => {
            void chatApi(`/calls/${ring.call_id}/decline`, { method: "POST" }).catch(() => undefined);
            setRing(null);
          }}
        >
          <PhoneOff />
        </button>
        {ring.kind === "VIDEO" && (
          <button
            type="button"
            className="call-round accept"
            aria-label="Accept with video"
            title="Join with video"
            onClick={() => accept("VIDEO")}
          >
            <Video />
          </button>
        )}
        <button
          type="button"
          className="call-round accept"
          aria-label="Accept with audio"
          title="Join with audio"
          onClick={() => accept("AUDIO")}
        >
          <Phone />
        </button>
      </div>
    </div>
  );
}
