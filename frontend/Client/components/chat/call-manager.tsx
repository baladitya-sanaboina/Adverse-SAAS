// Copy of frontend/shared/chat/call-manager.tsx (the Client app has no shared alias). Keep in sync.
"use client";

/*
 * Calls and meetings (owner request 2026-11-14: "like Google Meet / Zoom"). Rendered once by
 * each app's dashboard shell, so a call keeps going and an incoming call rings on every page.
 * Audio and video go browser to browser (WebRTC, one connection per pair of people); the server
 * only says who is in the call and passes offers, answers and network candidates between them.
 * Pages start or join a call with startCall() / joinCall().
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Maximize2, Mic, MicOff, Minimize2, MonitorUp, Phone, PhoneOff, Video, VideoOff } from "lucide-react";
import { subscribeRealtime } from "@/lib/realtime";
import { chatApi, initials, jsonBody } from "./chat-types";
import "@/styles/chat.css";

type Kind = "AUDIO" | "VIDEO";
type Seat = { id: string; name: string; role: string; image: string | null; joined_at: string };
type Call = {
  id: string;
  conversation_id: string;
  kind: Kind;
  started_by_id: string;
  started_at: string;
  ended_at: string | null;
  participants: Seat[];
};
type Ring = {
  call_id: string;
  conversation_id: string;
  kind: Kind;
  title: string;
  from: { id: string; name: string };
};

// Public STUN server so two browsers can find each other. A TURN relay (not set up yet) is needed
// for people behind strict office or mobile networks.
const ICE: RTCConfiguration = {
  iceServers: [{ urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] }],
};

declare global {
  interface Window {
    __adverseCallId?: string;
  }
}

export function startCall(conversationId: string, kind: Kind, title: string) {
  window.dispatchEvent(new CustomEvent("adverse-call", { detail: { action: "start", conversationId, kind, title } }));
}

export function joinCall(callId: string, conversationId: string, kind: Kind, title: string) {
  window.dispatchEvent(
    new CustomEvent("adverse-call", { detail: { action: "join", callId, conversationId, kind, title } }),
  );
}

let ringContext: AudioContext | null = null;
function ringOnce() {
  try {
    ringContext = ringContext ?? new AudioContext();
    const start = ringContext.currentTime;
    [0, 0.35].forEach((offset) => {
      const tone = ringContext!.createOscillator();
      const gain = ringContext!.createGain();
      tone.type = "sine";
      tone.frequency.value = offset ? 660 : 880;
      gain.gain.setValueAtTime(0.0001, start + offset);
      gain.gain.exponentialRampToValueAtTime(0.16, start + offset + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + offset + 0.3);
      tone.connect(gain).connect(ringContext!.destination);
      tone.start(start + offset);
      tone.stop(start + offset + 0.32);
    });
  } catch {
    // Sound is blocked until the person has clicked on the page; the card still shows.
  }
}

function Tile({
  name,
  stream,
  mine,
  image,
  kind,
}: {
  name: string;
  stream: MediaStream | null;
  mine?: boolean;
  image?: string | null;
  kind: Kind;
}) {
  const hasVideo =
    kind === "VIDEO" && Boolean(stream?.getVideoTracks().some((track) => track.readyState === "live" && track.enabled));
  return (
    <figure className={`call-tile${mine ? " mine" : ""}`}>
      {hasVideo ? (
        <video
          autoPlay
          playsInline
          muted
          ref={(element) => {
            if (element && element.srcObject !== stream) element.srcObject = stream;
          }}
        />
      ) : (
        <span className="call-tile-avatar">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {image ? <img src={image} alt="" /> : initials(name)}
        </span>
      )}
      <figcaption>{mine ? `${name} (you)` : name}</figcaption>
    </figure>
  );
}

function clockSince(start: number, now: number): string {
  const seconds = Math.max(0, Math.floor((now - start) / 1000));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h ? `${h}:` : ""}${String(m).padStart(h ? 2 : 1, "0")}:${String(s).padStart(2, "0")}`;
}

export function CallManager() {
  const [me, setMe] = useState<{ id: string; name: string } | null>(null);
  const [ring, setRing] = useState<Ring | null>(null);
  const [call, setCall] = useState<Call | null>(null);
  const [title, setTitle] = useState("");
  const [local, setLocal] = useState<MediaStream | null>(null);
  const [remote, setRemote] = useState<Record<string, MediaStream>>({});
  const [muted, setMuted] = useState(false);
  const [cameraOff, setCameraOff] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [screen, setScreen] = useState<MediaStream | null>(null);
  const [minimized, setMinimized] = useState(false);
  const [notice, setNotice] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const peers = useRef(new Map<string, RTCPeerConnection>());
  const queued = useRef(new Map<string, RTCIceCandidateInit[]>());
  const localRef = useRef<MediaStream | null>(null);
  const screenRef = useRef<MediaStream | null>(null);
  const callRef = useRef<Call | null>(null);
  const meRef = useRef<{ id: string; name: string } | null>(null);

  useEffect(() => {
    callRef.current = call;
    window.__adverseCallId = call?.id;
  }, [call]);

  const whoAmI = useCallback(async () => {
    if (meRef.current) return meRef.current;
    const people = await chatApi<{ me: { id: string; name: string } }>("/people");
    meRef.current = { id: people.me.id, name: people.me.name };
    setMe(meRef.current);
    return meRef.current;
  }, []);

  const signal = useCallback((to: string, kind: "offer" | "answer" | "ice", data: unknown) => {
    const current = callRef.current;
    if (!current) return;
    void chatApi(`/calls/${current.id}/signal`, jsonBody("POST", { to_user_id: to, kind, data })).catch(
      () => undefined,
    );
  }, []);

  const dropPeer = useCallback((userId: string) => {
    peers.current.get(userId)?.close();
    peers.current.delete(userId);
    queued.current.delete(userId);
    setRemote((current) => {
      if (!(userId in current)) return current;
      const next = { ...current };
      delete next[userId];
      return next;
    });
  }, []);

  const peerFor = useCallback(
    (userId: string) => {
      const existing = peers.current.get(userId);
      if (existing) return existing;
      const connection = new RTCPeerConnection(ICE);
      localRef.current?.getTracks().forEach((track) => connection.addTrack(track, localRef.current!));
      connection.onicecandidate = (event) => event.candidate && signal(userId, "ice", event.candidate.toJSON());
      connection.ontrack = (event) => {
        const stream = event.streams[0] ?? new MediaStream([event.track]);
        setRemote((current) => ({ ...current, [userId]: stream }));
      };
      connection.onconnectionstatechange = () => {
        if (connection.connectionState === "failed")
          setNotice("Could not connect to someone: their network may block calls.");
      };
      peers.current.set(userId, connection);
      return connection;
    },
    [signal],
  );

  const cleanup = useCallback(() => {
    peers.current.forEach((connection) => connection.close());
    peers.current.clear();
    queued.current.clear();
    localRef.current?.getTracks().forEach((track) => track.stop());
    screenRef.current?.getTracks().forEach((track) => track.stop());
    localRef.current = null;
    screenRef.current = null;
    setScreen(null);
    setLocal(null);
    setRemote({});
    setCall(null);
    setSharing(false);
    setMuted(false);
    setCameraOff(false);
    setMinimized(false);
  }, []);

  const leave = useCallback(async () => {
    const current = callRef.current;
    cleanup();
    if (current) await chatApi(`/calls/${current.id}/leave`, { method: "POST" }).catch(() => undefined);
  }, [cleanup]);

  const enter = useCallback(
    async (action: "start" | "join", conversationId: string, kind: Kind, label: string, callId?: string) => {
      if (callRef.current) {
        if (callRef.current.conversation_id === conversationId) return setMinimized(false);
        await leave();
      }
      setRing(null);
      setNotice("");
      let media: MediaStream;
      try {
        media = await navigator.mediaDevices.getUserMedia({ audio: true, video: kind === "VIDEO" });
      } catch {
        try {
          media = await navigator.mediaDevices.getUserMedia({ audio: true });
          if (kind === "VIDEO") setNotice("Camera not available: joined with audio only.");
        } catch {
          setNotice("Allow the microphone in your browser to join the call.");
          return;
        }
      }
      localRef.current = media;
      setLocal(media);
      try {
        const self = await whoAmI();
        const joined =
          action === "start"
            ? await chatApi<Call>(`/conversations/${conversationId}/calls`, jsonBody("POST", { kind }))
            : await chatApi<Call>(`/calls/${callId}/join`, { method: "POST" });
        setTitle(label);
        setCall(joined);
        callRef.current = joined;
        // The newcomer calls everyone already there.
        for (const seat of joined.participants) {
          if (seat.id === self.id) continue;
          const connection = peerFor(seat.id);
          const offer = await connection.createOffer();
          await connection.setLocalDescription(offer);
          signal(seat.id, "offer", offer);
        }
      } catch (reason) {
        media.getTracks().forEach((track) => track.stop());
        localRef.current = null;
        setLocal(null);
        setNotice(reason instanceof Error ? reason.message : "Could not join the call.");
      }
    },
    [leave, whoAmI, peerFor, signal],
  );

  // Start / join requests from pages.
  useEffect(() => {
    const onRequest = (event: Event) => {
      const detail = (event as CustomEvent).detail as {
        action: "start" | "join";
        conversationId: string;
        kind: Kind;
        title: string;
        callId?: string;
      };
      void enter(detail.action, detail.conversationId, detail.kind, detail.title, detail.callId);
    };
    window.addEventListener("adverse-call", onRequest);
    return () => window.removeEventListener("adverse-call", onRequest);
  }, [enter]);

  // Live events: ringing, people joining/leaving, WebRTC signals.
  useEffect(
    () =>
      subscribeRealtime((event) => {
        const data = event.data as Record<string, unknown>;
        if (event.type === "call.ring") {
          const incoming = data as unknown as Ring;
          if (callRef.current?.id === incoming.call_id) return;
          setRing(incoming);
        } else if (event.type === "call.update") {
          const update = data.call as Call;
          setRing((current) => (current && current.call_id === update.id && update.ended_at ? null : current));
          const current = callRef.current;
          if (!current || current.id !== update.id) return;
          if (update.ended_at) return cleanup();
          setCall(update);
          const here = new Set(update.participants.map((seat) => seat.id));
          [...peers.current.keys()].forEach((id) => !here.has(id) && dropPeer(id));
        } else if (event.type === "call.declined") {
          const declined = data as { call_id: string; name: string; direct: boolean };
          const current = callRef.current;
          if (current?.id === declined.call_id) {
            setNotice(`${declined.name} declined.`);
            if (declined.direct && current.participants.length <= 1) void leave();
          }
        } else if (event.type === "call.signal") {
          const message = data as {
            call_id: string;
            from_user_id: string;
            kind: "offer" | "answer" | "ice";
            data: unknown;
          };
          const current = callRef.current;
          if (!current || current.id !== message.call_id) return;
          const from = message.from_user_id;
          void (async () => {
            const connection = peerFor(from);
            if (message.kind === "offer") {
              await connection.setRemoteDescription(message.data as RTCSessionDescriptionInit);
              const answer = await connection.createAnswer();
              await connection.setLocalDescription(answer);
              signal(from, "answer", answer);
            } else if (message.kind === "answer") {
              await connection.setRemoteDescription(message.data as RTCSessionDescriptionInit);
            } else if (connection.remoteDescription) {
              await connection.addIceCandidate(message.data as RTCIceCandidateInit).catch(() => undefined);
              return;
            } else {
              queued.current.set(from, [...(queued.current.get(from) ?? []), message.data as RTCIceCandidateInit]);
              return;
            }
            for (const candidate of queued.current.get(from) ?? []) {
              await connection.addIceCandidate(candidate).catch(() => undefined);
            }
            queued.current.delete(from);
          })();
        }
      }),
    [cleanup, dropPeer, leave, peerFor, signal],
  );

  // Notices ("X declined") go away by themselves so they never sit on top of other controls.
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // Ring tone while a call is coming in; give up after 40 seconds.
  useEffect(() => {
    if (!ring) return;
    ringOnce();
    const tone = window.setInterval(ringOnce, 2200);
    const stop = window.setTimeout(() => setRing(null), 40_000);
    return () => {
      window.clearInterval(tone);
      window.clearTimeout(stop);
    };
  }, [ring]);

  // Still here: keeps my seat, and the clock ticking.
  useEffect(() => {
    if (!call) return;
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    const ping = window.setInterval(() => {
      const current = callRef.current;
      if (current) void chatApi(`/calls/${current.id}/ping`, { method: "POST" }).catch(() => cleanup());
    }, 10_000);
    const bye = () => {
      const current = callRef.current;
      if (current) navigator.sendBeacon?.(`/api/chat/calls/${current.id}/leave`);
    };
    window.addEventListener("pagehide", bye);
    return () => {
      window.clearInterval(tick);
      window.clearInterval(ping);
      window.removeEventListener("pagehide", bye);
    };
  }, [call, cleanup]);

  function toggleMic() {
    const next = !muted;
    localRef.current?.getAudioTracks().forEach((track) => (track.enabled = !next));
    setMuted(next);
  }

  function toggleCamera() {
    const next = !cameraOff;
    localRef.current?.getVideoTracks().forEach((track) => (track.enabled = !next));
    setCameraOff(next);
  }

  async function toggleShare() {
    const camera = localRef.current?.getVideoTracks()[0] ?? null;
    const swap = (track: MediaStreamTrack | null) =>
      peers.current.forEach((connection) => {
        const sender = connection.getSenders().find((item) => item.track?.kind === "video" || item.track === null);
        void sender?.replaceTrack(track);
      });
    if (sharing) {
      screenRef.current?.getTracks().forEach((track) => track.stop());
      screenRef.current = null;
      setScreen(null);
      swap(camera);
      setSharing(false);
      return;
    }
    try {
      const display = await navigator.mediaDevices.getDisplayMedia({ video: true });
      screenRef.current = display;
      setScreen(display);
      const track = display.getVideoTracks()[0];
      swap(track);
      track.onended = () => {
        swap(localRef.current?.getVideoTracks()[0] ?? null);
        screenRef.current = null;
        setScreen(null);
        setSharing(false);
      };
      setSharing(true);
    } catch {
      // The person closed the screen picker.
    }
  }

  const others = (call?.participants ?? []).filter((seat) => seat.id !== me?.id);
  const started = call ? new Date(call.started_at).getTime() : now;
  const shownLocal = sharing && screen ? screen : local;

  return (
    <>
      {/* Remote sound plays here, even with the call window minimised. */}
      {Object.entries(remote).map(([id, stream]) => (
        <audio
          key={id}
          autoPlay
          ref={(element) => {
            if (element && element.srcObject !== stream) element.srcObject = stream;
          }}
        />
      ))}

      {ring && !call && (
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
                onClick={() => void enter("join", ring.conversation_id, "VIDEO", ring.title, ring.call_id)}
              >
                <Video />
              </button>
            )}
            <button
              type="button"
              className="call-round accept"
              aria-label="Accept with audio"
              onClick={() => void enter("join", ring.conversation_id, "AUDIO", ring.title, ring.call_id)}
            >
              <Phone />
            </button>
          </div>
        </div>
      )}

      {notice && !call && (
        <div className="call-toast" role="status">
          {notice}
          <button type="button" onClick={() => setNotice("")} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}

      {call && minimized && (
        <div className="call-mini" role="region" aria-label="Call in progress">
          <span className="call-live" aria-hidden="true" />
          <button type="button" className="call-mini-title" onClick={() => setMinimized(false)}>
            <strong>{title || "Call"}</strong>
            <small>
              {clockSince(started, now)} · {call.participants.length} in call
            </small>
          </button>
          <button
            type="button"
            className={`call-round small${muted ? " off" : ""}`}
            aria-label={muted ? "Unmute" : "Mute"}
            onClick={toggleMic}
          >
            {muted ? <MicOff /> : <Mic />}
          </button>
          <button
            type="button"
            className="call-round small"
            aria-label="Open the call"
            onClick={() => setMinimized(false)}
          >
            <Maximize2 />
          </button>
          <button
            type="button"
            className="call-round small decline"
            aria-label="Leave call"
            onClick={() => void leave()}
          >
            <PhoneOff />
          </button>
        </div>
      )}

      {call && !minimized && (
        <div className="call-overlay" role="dialog" aria-modal="true" aria-label={`Call: ${title}`}>
          <header>
            <div>
              <strong>{title || "Call"}</strong>
              <small>
                <span className="call-live" aria-hidden="true" /> {call.kind === "VIDEO" ? "Video call" : "Voice call"}{" "}
                · {clockSince(started, now)} · {call.participants.length}{" "}
                {call.participants.length === 1 ? "person" : "people"}
              </small>
            </div>
            <button
              type="button"
              className="call-round small ghost"
              aria-label="Minimise"
              title="Keep working; the call continues"
              onClick={() => setMinimized(true)}
            >
              <Minimize2 />
            </button>
          </header>
          {notice && <p className="call-notice">{notice}</p>}
          <div className={`call-grid count-${Math.min(others.length + 1, 6)}`}>
            <Tile
              name={me?.name ?? "You"}
              stream={shownLocal}
              mine
              kind={call.kind === "VIDEO" && !cameraOff ? "VIDEO" : sharing ? "VIDEO" : "AUDIO"}
            />
            {others.map((seat) => (
              <Tile
                key={seat.id}
                name={seat.name}
                image={seat.image}
                stream={remote[seat.id] ?? null}
                kind={call.kind}
              />
            ))}
            {others.length === 0 && <p className="call-waiting">Waiting for others to join…</p>}
          </div>
          <footer>
            <button
              type="button"
              className={`call-round${muted ? " off" : ""}`}
              aria-label={muted ? "Unmute" : "Mute"}
              title={muted ? "Unmute" : "Mute"}
              onClick={toggleMic}
            >
              {muted ? <MicOff /> : <Mic />}
            </button>
            {call.kind === "VIDEO" && (
              <>
                <button
                  type="button"
                  className={`call-round${cameraOff ? " off" : ""}`}
                  aria-label={cameraOff ? "Turn camera on" : "Turn camera off"}
                  title="Camera"
                  onClick={toggleCamera}
                >
                  {cameraOff ? <VideoOff /> : <Video />}
                </button>
                <button
                  type="button"
                  className={`call-round${sharing ? " on" : ""}`}
                  aria-label={sharing ? "Stop sharing" : "Share screen"}
                  title="Share screen"
                  onClick={() => void toggleShare()}
                >
                  <MonitorUp />
                </button>
              </>
            )}
            <button
              type="button"
              className="call-round decline wide"
              aria-label="Leave call"
              onClick={() => void leave()}
            >
              <PhoneOff /> Leave
            </button>
          </footer>
        </div>
      )}
    </>
  );
}
