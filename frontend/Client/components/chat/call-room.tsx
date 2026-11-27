// Copy of frontend/shared/chat/call-room.tsx (the Client app has no shared alias). Keep in sync.
"use client";

/*
 * The call tab, /call/<code> (owner requests 2026-11-14: "like Google Meet", "call vere tab lo
 * ravali", "sounds anni sariga ravali", "admit cheyataniki permission", "meet link fully
 * functional").
 *
 * 1. Before joining: camera and microphone preview, devices, and who is already in the call.
 *    The Join click also turns on sound for this tab (browsers block sound until a click).
 * 2. Chat members join straight away. Anyone else in the company asks to join and waits until
 *    the host or an admin in the call admits them (backend call_service).
 * 3. In the call: audio and video go browser to browser (WebRTC, one connection per pair).
 *    The server only says who is in the call and passes offers, answers and network candidates.
 *    A small data channel per pair carries mic / camera / screen-share / raised-hand state for
 *    the tiles, reactions, and "please mute" from the host or an admin.
 * 4. More in the call (owner request 2026-11-15: "in call UI enka advanced, meeting and chat
 *    same layout lo"): the chat beside the video (saved in the chat as well), raise hand,
 *    reactions, pin, layouts, settings with speaker choice, full screen and keyboard shortcuts.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import {
  ArrowLeft,
  Check,
  Flame,
  HandHeart,
  Heart,
  Laugh,
  PartyPopper,
  Star,
  ThumbsUp,
  Copy,
  Hand,
  Info,
  Keyboard,
  LayoutGrid,
  Link2,
  Maximize2,
  MessageSquareText,
  Mic,
  MicOff,
  Minimize2,
  MonitorUp,
  Paperclip,
  PhoneOff,
  Pin,
  PinOff,
  SendHorizontal,
  Settings,
  Smile,
  Users,
  Video,
  VideoOff,
  Volume2,
  X,
} from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { subscribeRealtime } from "@/lib/realtime";
import { chatApi, clock, initials, jsonBody, photoSrc, type ChatMessage } from "./chat-types";
import { audioContext, repeat, sounds, unlockSounds } from "./call-sounds";
import { OrbitLoader } from "@/components/loader/orbit-loader";
import "@/styles/call.css";

type Kind = "AUDIO" | "VIDEO";
type Role = "ADMIN" | "MANAGER" | "EMPLOYEE" | "CLIENT";
type Seat = { id: string; name: string; role: Role; image: string | null; joined_at: string };
type Call = {
  id: string;
  conversation_id: string;
  kind: Kind;
  started_by_id: string;
  started_at: string;
  ended_at: string | null;
  participants: Seat[];
  code: string | null;
};
type MeetInfo = {
  code: string;
  title: string;
  type: "DIRECT" | "GROUP" | "CLIENT";
  member: boolean;
  conversation_id: string | null;
  kind: Kind;
  live: boolean;
  in_call: string[];
  host_name: string | null;
  call: Call | null;
  admission: "WAITING" | "ADMITTED" | "DENIED" | null;
  can_admit: boolean;
};
type Waiting = { id: string; name: string; role: Role; image: string | null; requested_at: string };
type Me = { id: string; name: string; image: string | null };
type PeerState = { mic: boolean; cam: boolean; sharing: boolean; hand?: boolean };
type Phase = "loading" | "missing" | "prejoin" | "asking" | "denied" | "joining" | "incall" | "left" | "ended";
type Device = { value: string; label: string };
type Panel = "people" | "chat" | "info";
type Layout = "auto" | "tiled" | "spotlight";
type Floating = { id: number; emoji: string; name: string; left: number };
/** What goes over a data channel besides the state: a reaction, or "please mute" from the host. */
type ChannelMessage = { type: "reaction"; emoji: string } | { type: "mute" };

// Reactions are the app's own line icons, not emojis (owner request 2026-11-15).
const REACTION_ICONS = {
  like: { label: "Like", Icon: ThumbsUp },
  love: { label: "Love", Icon: Heart },
  haha: { label: "Haha", Icon: Laugh },
  agree: { label: "Agree", Icon: Check },
  star: { label: "Great", Icon: Star },
  party: { label: "Celebrate", Icon: PartyPopper },
  thanks: { label: "Thanks", Icon: HandHeart },
  fire: { label: "Fire", Icon: Flame },
} as const;
type ReactionKey = keyof typeof REACTION_ICONS;
const REACTION_KEYS = Object.keys(REACTION_ICONS) as ReactionKey[];
const LAYOUTS: { value: Layout; label: string; hint: string }[] = [
  { value: "auto", label: "Auto", hint: "Everyone in a grid; whoever presents goes big" },
  { value: "tiled", label: "Tiled", hint: "Everyone the same size" },
  { value: "spotlight", label: "Spotlight", hint: "The person talking (or pinned) goes big" },
];
const SHORTCUTS: [string, string][] = [
  ["Ctrl + D", "Microphone on / off"],
  ["Ctrl + E", "Camera on / off"],
  ["Ctrl + Alt + H", "Raise / lower hand"],
  ["Ctrl + Alt + C", "Open chat"],
  ["Ctrl + Alt + P", "Open people"],
  ["Ctrl + Alt + F", "Full screen"],
];

// Public STUN servers so two browsers can find each other. People behind strict office or mobile
// networks also need the TURN relay: the backend adds it with short-lived credentials when it is
// set up (production), and this list is the fallback.
const ICE: RTCConfiguration = {
  iceServers: [{ urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] }],
};
const ROLE_LABEL: Record<Role, string> = { ADMIN: "Admin", MANAGER: "Manager", EMPLOYEE: "Employee", CLIENT: "Client" };

// A reload (or the dev server refreshing the page) drops the call; this note lets the tab rejoin
// by itself. Per tab only, so closing the tab forgets it.
const REJOIN_MS = 120_000;
function rememberCall(code: string): void {
  try {
    sessionStorage.setItem(`adverse-call:${code}`, String(Date.now()));
  } catch {
    // Storage blocked: the person rejoins with one click instead.
  }
}
function forgetCall(code: string): void {
  try {
    sessionStorage.removeItem(`adverse-call:${code}`);
  } catch {
    // Nothing stored.
  }
}
function recentlyInCall(code: string): boolean {
  try {
    const at = Number(sessionStorage.getItem(`adverse-call:${code}`));
    return at > 0 && Date.now() - at < REJOIN_MS;
  } catch {
    return false;
  }
}

function clockSince(start: number, now: number): string {
  const seconds = Math.max(0, Math.floor((now - start) / 1000));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h ? `${h}:` : ""}${String(m).padStart(h ? 2 : 1, "0")}:${String(s).padStart(2, "0")}`;
}

function listNames(names: string[]): string {
  if (names.length === 0) return "";
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, 2).join(", ")} and ${names.length - 2} more`;
}

/** Who is talking: a level meter on each stream, read four times a second. */
function useSpeaking(streams: Record<string, MediaStream | null>, active: boolean): Set<string> {
  const [speaking, setSpeaking] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    if (!active) return;
    const audio = audioContext();
    if (!audio) return;
    const meters = Object.entries(streams).flatMap(([id, stream]) => {
      if (!stream || stream.getAudioTracks().length === 0) return [];
      try {
        const source = audio.createMediaStreamSource(stream);
        const analyser = audio.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        return [{ id, source, analyser, data: new Uint8Array(analyser.fftSize) }];
      } catch {
        return [];
      }
    });
    const timer = window.setInterval(() => {
      const next = new Set<string>();
      for (const meter of meters) {
        meter.analyser.getByteTimeDomainData(meter.data);
        let sum = 0;
        for (const value of meter.data) {
          const level = (value - 128) / 128;
          sum += level * level;
        }
        if (Math.sqrt(sum / meter.data.length) > 0.035) next.add(meter.id);
      }
      setSpeaking((current) =>
        current.size === next.size && [...next].every((id) => current.has(id)) ? current : next,
      );
    }, 250);
    return () => {
      window.clearInterval(timer);
      meters.forEach((meter) => meter.source.disconnect());
    };
  }, [streams, active]);
  return speaking;
}

/** A steady colour per person for avatars without a photo (Meet-style). */
const AVATAR_COLOURS = ["#0876ed", "#7c5cff", "#0f9d8a", "#e0692b", "#c2408c", "#3f7d20", "#b8860b", "#5865f2"];
function colourFor(name: string): string {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return AVATAR_COLOURS[hash % AVATAR_COLOURS.length];
}

function Avatar({ name, image, size = "md" }: { name: string; image?: string | null; size?: "md" | "lg" }) {
  // The photo when it loads, else the first letter (owner request 2026-11-28).
  const src = photoSrc(image);
  const [failed, setFailed] = useState("");
  const showPhoto = Boolean(src) && failed !== src;
  return (
    <span className={`callroom-avatar ${size}`} style={showPhoto ? undefined : { background: colourFor(name) }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {showPhoto && src ? <img src={src} alt="" onError={() => setFailed(src)} /> : initials(name)}
    </span>
  );
}

type Box = { width: number; height: number };

/** The size of an element, kept up to date. */
function useBox<T extends HTMLElement>(): [(element: T | null) => void, Box] {
  const [box, setBox] = useState<Box>({ width: 0, height: 0 });
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((element: T | null) => {
    observer.current?.disconnect();
    if (!element) return;
    observer.current = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setBox((current) =>
        Math.abs(current.width - width) < 1 && Math.abs(current.height - height) < 1 ? current : { width, height },
      );
    });
    observer.current.observe(element);
  }, []);
  return [ref, box];
}

/**
 * Tiles as large as they can be, all the same size and shape, in centred rows (like Google
 * Meet): try every column count and keep the one that gives the biggest tile.
 */
function fitTiles(count: number, box: Box, gap: number): Box {
  if (count === 0 || box.width === 0 || box.height === 0) return { width: 0, height: 0 };
  const aspect = box.width / box.height < 0.85 ? 3 / 4 : 16 / 9; // phones held upright: taller tiles
  let best: Box = { width: 0, height: 0 };
  for (let columns = 1; columns <= count; columns += 1) {
    const rows = Math.ceil(count / columns);
    const maxWidth = (box.width - gap * (columns - 1)) / columns;
    const maxHeight = (box.height - gap * (rows - 1)) / rows;
    const width = Math.min(maxWidth, maxHeight * aspect);
    if (width > best.width) best = { width: Math.floor(width), height: Math.floor(width / aspect) };
  }
  return best;
}

function Tile({
  name,
  image,
  stream,
  video,
  mic,
  mine,
  screen,
  speaking,
  role,
  hand,
  pinned,
  onPin,
  size,
  className,
}: {
  name: string;
  image?: string | null;
  stream: MediaStream | null;
  video: boolean;
  mic: boolean;
  mine?: boolean;
  screen?: boolean;
  speaking?: boolean;
  role?: string;
  hand?: boolean;
  pinned?: boolean;
  onPin?: () => void;
  size?: Box;
  className?: string;
}) {
  return (
    <figure
      className={`callroom-tile${speaking ? " speaking" : ""}${screen ? " screen" : ""}${pinned ? " pinned" : ""}${
        className ? ` ${className}` : ""
      }`}
      style={size && size.width > 0 ? { width: size.width, height: size.height } : undefined}
    >
      {video && stream ? (
        <video
          className={mine && !screen ? "mirror" : undefined}
          autoPlay
          playsInline
          muted
          ref={(element) => {
            if (element && element.srcObject !== stream) element.srcObject = stream;
          }}
        />
      ) : (
        <span className="callroom-tile-face">
          <Avatar name={name} image={image} size="lg" />
        </span>
      )}
      {hand && (
        <span className="callroom-tile-hand" aria-label={`${mine ? "Your" : `${name}'s`} hand is raised`}>
          <Hand />
        </span>
      )}
      {!mic && (
        <span className="callroom-tile-muted" aria-label={`${mine ? "You are" : `${name} is`} muted`}>
          <MicOff />
        </span>
      )}
      {onPin && (
        <button
          type="button"
          className="callroom-tile-pin"
          aria-label={pinned ? `Unpin ${name}` : `Pin ${name}`}
          title={pinned ? "Unpin" : "Pin to the main screen"}
          onClick={onPin}
        >
          {pinned ? <PinOff /> : <Pin />}
        </button>
      )}
      <figcaption>
        <span>{screen ? `${mine ? "You are" : `${name} is`} presenting` : mine ? "You" : name}</span>
        {role && !mine && !screen && <small>{role}</small>}
      </figcaption>
    </figure>
  );
}

/** A live level meter for the microphone in Settings: speak and the bars move. */
function MicMeter({ stream }: { stream: MediaStream | null }) {
  const [level, setLevel] = useState(0);
  useEffect(() => {
    const audio = audioContext();
    if (!audio || !stream || stream.getAudioTracks().length === 0) return;
    let frame = 0;
    let source: MediaStreamAudioSourceNode | null = null;
    try {
      source = audio.createMediaStreamSource(stream);
    } catch {
      return;
    }
    const analyser = audio.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.fftSize);
    const read = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (const value of data) sum += ((value - 128) / 128) ** 2;
      setLevel(Math.min(1, Math.sqrt(sum / data.length) * 6));
      frame = window.requestAnimationFrame(read);
    };
    frame = window.requestAnimationFrame(read);
    return () => {
      window.cancelAnimationFrame(frame);
      source?.disconnect();
    };
  }, [stream]);
  const lit = Math.round(level * 14);
  return (
    <span
      className="callroom-meter"
      role="meter"
      aria-label="Microphone level"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(level * 100)}
    >
      {Array.from({ length: 14 }, (_, index) => (
        <i key={index} className={index < lit ? "on" : undefined} />
      ))}
    </span>
  );
}

/** Small drawings of each layout for the Settings picker. */
function LayoutPicture({ kind }: { kind: Layout }) {
  return (
    <span className={`callroom-layout-pic ${kind}`} aria-hidden="true">
      {kind === "spotlight" ? (
        <>
          <i className="big" />
          <span>
            <i />
            <i />
            <i />
          </span>
        </>
      ) : (
        Array.from({ length: kind === "tiled" ? 6 : 4 }, (_, index) => <i key={index} />)
      )}
    </span>
  );
}

/** Links in chat lines become clickable; everything else stays plain text (no HTML). */
function Linked({ text }: { text: string }) {
  const parts = text.split(/(https?:\/\/[^\s<>"]+)/g);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <a key={index} href={part} target="_blank" rel="noopener noreferrer">
            {part}
          </a>
        ) : (
          part
        ),
      )}
    </>
  );
}

export function CallRoom({
  code: initialCode,
  conversationId,
  kindHint,
}: {
  code: string;
  conversationId?: string;
  kindHint?: Kind;
}) {
  const [code, setCode] = useState(initialCode === "new" ? "" : initialCode.toLowerCase());
  const [phase, setPhase] = useState<Phase>("loading");
  const [problem, setProblem] = useState("");
  const [info, setInfo] = useState<MeetInfo | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [call, setCall] = useState<Call | null>(null);
  const [local, setLocal] = useState<MediaStream | null>(null);
  const [remote, setRemote] = useState<Record<string, MediaStream>>({});
  const [peerState, setPeerState] = useState<Record<string, PeerState>>({});
  const [micOn, setMicOn] = useState(true);
  const [camOn, setCamOn] = useState(kindHint !== "AUDIO");
  const [camBlocked, setCamBlocked] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [screen, setScreen] = useState<MediaStream | null>(null);
  const [mics, setMics] = useState<Device[]>([]);
  const [cams, setCams] = useState<Device[]>([]);
  const [micId, setMicId] = useState("");
  const [camId, setCamId] = useState("");
  const [lobby, setLobby] = useState<Waiting[]>([]);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [notices, setNotices] = useState<{ id: number; text: string }[]>([]);
  const [copied, setCopied] = useState(false);
  const [elsewhere, setElsewhere] = useState(false);
  const [soundOff, setSoundOff] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [lines, setLines] = useState<ChatMessage[]>([]);
  const [unread, setUnread] = useState(0);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [hand, setHand] = useState(false);
  const [floating, setFloating] = useState<Floating[]>([]);
  const [tray, setTray] = useState(false);
  const [pinned, setPinned] = useState<string | null>(null);
  const [layout, setLayout] = useState<Layout>("auto");
  const [settings, setSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState<"audio" | "video" | "layout">("audio");
  const [speakers, setSpeakers] = useState<Device[]>([]);
  const [speakerId, setSpeakerId] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const [lastSpeaker, setLastSpeaker] = useState<string | null>(null);

  const peers = useRef(new Map<string, RTCPeerConnection>());
  const iceRef = useRef<RTCConfiguration>(ICE);
  useEffect(() => {
    let live = true;
    fetch("/api/chat/ice-servers", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body: RTCConfiguration | null) => {
        if (live && body?.iceServers?.length) iceRef.current = body;
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  const channels = useRef(new Map<string, RTCDataChannel>());
  const queued = useRef(new Map<string, RTCIceCandidateInit[]>());
  const localRef = useRef<MediaStream | null>(null);
  const screenRef = useRef<MediaStream | null>(null);
  const callRef = useRef<Call | null>(null);
  const meRef = useRef<Me | null>(null);
  const stateRef = useRef<PeerState>({ mic: true, cam: kindHint !== "AUDIO", sharing: false, hand: false });
  const phaseRef = useRef<Phase>("loading");
  const seenRef = useRef<Set<string>>(new Set());
  const noticeId = useRef(0);
  const autoJoin = useRef(false);
  const codeRef = useRef(code);
  const panelRef = useRef<Panel | null>(null);
  const handsRef = useRef<Set<string>>(new Set());
  const speakerRef = useRef("");
  const linesEnd = useRef<HTMLLIElement | null>(null);
  const lineIds = useRef<Set<string>>(new Set());
  const muteRequest = useRef<(from: string) => void>(() => undefined);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);
  useEffect(() => {
    callRef.current = call;
  }, [call]);
  useEffect(() => {
    codeRef.current = code;
  }, [code]);
  useEffect(() => {
    panelRef.current = panel;
  }, [panel]);
  useEffect(() => {
    speakerRef.current = speakerId;
  }, [speakerId]);

  const notify = useCallback((text: string) => {
    noticeId.current += 1;
    const id = noticeId.current;
    setNotices((current) => [...current.slice(-2), { id, text }]);
    window.setTimeout(() => setNotices((current) => current.filter((item) => item.id !== id)), 6000);
  }, []);

  // -- who am I, which chat, and what the link says -------------------------------------------

  const loadInfo = useCallback(async (meetCode: string) => {
    const next = await chatApi<MeetInfo>(`/meet/${meetCode}`);
    setInfo(next);
    return next;
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const people = await chatApi<{ me: Me }>("/people");
        meRef.current = people.me;
        if (!cancelled) setMe(people.me);
        let meetCode = code;
        if (!meetCode) {
          if (!conversationId) throw new Error("This call link is not complete.");
          meetCode = (await chatApi<{ code: string }>(`/conversations/${conversationId}/link`)).code;
          window.history.replaceState(null, "", `/call/${meetCode}${kindHint ? `?kind=${kindHint}` : ""}`);
          if (!cancelled) setCode(meetCode);
        }
        const next = await loadInfo(meetCode);
        if (cancelled) return;
        if (next.admission === "DENIED") setPhase("denied");
        else {
          autoJoin.current = next.live && (next.member || next.admission === "ADMITTED") && recentlyInCall(meetCode);
          setPhase("prejoin");
        }
      } catch (reason) {
        if (cancelled) return;
        setProblem(reason instanceof Error ? reason.message : "This meeting link does not exist.");
        setPhase("missing");
      }
    })();
    return () => {
      cancelled = true;
    };
    // Runs once per link; `code` is set here only for /call/new.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (info) document.title = `${info.title} · Call`;
  }, [info]);

  // Keep the "who is in the call" line fresh while deciding to join.
  useEffect(() => {
    if (phase !== "prejoin" || !code) return;
    const timer = window.setInterval(() => void loadInfo(code).catch(() => undefined), 5000);
    return () => window.clearInterval(timer);
  }, [phase, code, loadInfo]);

  // -- camera and microphone ---------------------------------------------------------------

  const callKind: Kind = call?.kind ?? (info?.live ? info.kind : (kindHint ?? "VIDEO"));
  const wantsVideo = callKind === "VIDEO";

  const refreshDevices = useCallback(async () => {
    const devices = await navigator.mediaDevices?.enumerateDevices().catch(() => []);
    const shape = (kind: MediaDeviceKind, fallback: string) =>
      (devices ?? [])
        .filter((device) => device.kind === kind && device.deviceId)
        .map((device, index) => ({ value: device.deviceId, label: device.label || `${fallback} ${index + 1}` }));
    setMics(shape("audioinput", "Microphone"));
    setCams(shape("videoinput", "Camera"));
    // Choosing the speaker works in browsers that support it (Chrome, Edge).
    const canPick = typeof HTMLMediaElement !== "undefined" && "setSinkId" in HTMLMediaElement.prototype;
    setSpeakers(canPick ? shape("audiooutput", "Speaker") : []);
  }, []);

  const acquire = useCallback(
    async (video: boolean, mic = micId, cam = camId) => {
      const audio: MediaTrackConstraints | boolean = mic ? { deviceId: { exact: mic } } : true;
      let stream: MediaStream | null = null;
      let blocked = false;
      if (video) {
        stream = await navigator.mediaDevices
          .getUserMedia({ audio, video: cam ? { deviceId: { exact: cam } } : true })
          .catch(() => null);
        blocked = stream === null;
      }
      if (!stream) stream = await navigator.mediaDevices.getUserMedia({ audio }).catch(() => null);
      setCamBlocked(video && blocked);
      if (stream) {
        stream.getAudioTracks().forEach((track) => (track.enabled = stateRef.current.mic));
        stream.getVideoTracks().forEach((track) => (track.enabled = stateRef.current.cam));
        const audioId = stream.getAudioTracks()[0]?.getSettings().deviceId;
        const videoId = stream.getVideoTracks()[0]?.getSettings().deviceId;
        if (audioId) setMicId(audioId);
        if (videoId) setCamId(videoId);
      }
      void refreshDevices();
      return stream;
    },
    [micId, camId, refreshDevices],
  );

  // Preview on the join screen (the same stream is used in the call: one permission prompt).
  useEffect(() => {
    if (phase !== "prejoin" || localRef.current) return;
    let cancelled = false;
    void acquire(wantsVideo).then((stream) => {
      if (cancelled) return stream?.getTracks().forEach((track) => track.stop());
      localRef.current = stream;
      setLocal(stream);
    });
    return () => {
      cancelled = true;
    };
  }, [phase, wantsVideo, acquire]);

  const stopLocal = useCallback(() => {
    localRef.current?.getTracks().forEach((track) => track.stop());
    screenRef.current?.getTracks().forEach((track) => track.stop());
    localRef.current = null;
    screenRef.current = null;
    setLocal(null);
    setScreen(null);
    setSharing(false);
    stateRef.current = { ...stateRef.current, sharing: false };
  }, []);

  // -- WebRTC --------------------------------------------------------------------------------

  const broadcastState = useCallback(() => {
    const text = JSON.stringify(stateRef.current);
    channels.current.forEach((channel) => channel.readyState === "open" && channel.send(text));
  }, []);

  const signal = useCallback((to: string, kind: "offer" | "answer" | "ice", data: unknown) => {
    const current = callRef.current;
    if (!current) return;
    void chatApi(`/calls/${current.id}/signal`, jsonBody("POST", { to_user_id: to, kind, data })).catch(
      () => undefined,
    );
  }, []);

  const float = useCallback((emoji: string, name: string) => {
    noticeId.current += 1;
    const id = noticeId.current;
    const left = 8 + Math.round(Math.random() * 18);
    setFloating((current) => [...current.slice(-14), { id, emoji, name, left }]);
    window.setTimeout(() => setFloating((current) => current.filter((item) => item.id !== id)), 4200);
  }, []);

  const watchChannel = useCallback(
    (userId: string, channel: RTCDataChannel) => {
      channels.current.set(userId, channel);
      channel.onopen = () => channel.send(JSON.stringify(stateRef.current));
      channel.onmessage = (event) => {
        let parsed: (PeerState & { type?: undefined }) | ChannelMessage;
        try {
          parsed = JSON.parse(String(event.data));
        } catch {
          return; // not ours
        }
        const name = callRef.current?.participants.find((seat) => seat.id === userId)?.name ?? "Someone";
        if (parsed.type === "reaction") {
          if ((REACTION_KEYS as string[]).includes(parsed.emoji)) float(parsed.emoji, name);
          return;
        }
        if (parsed.type === "mute") {
          muteRequest.current(userId);
          return;
        }
        const state = parsed;
        const raised = Boolean(state.hand);
        if (raised && !handsRef.current.has(userId)) {
          sounds.hand();
          notify(`${name} raised a hand`);
        }
        if (raised) handsRef.current.add(userId);
        else handsRef.current.delete(userId);
        setPeerState((current) => ({ ...current, [userId]: state }));
      };
    },
    [float, notify],
  );

  const dropPeer = useCallback((userId: string) => {
    peers.current.get(userId)?.close();
    peers.current.delete(userId);
    channels.current.delete(userId);
    queued.current.delete(userId);
    handsRef.current.delete(userId);
    setPinned((current) => (current === userId ? null : current));
    setRemote((current) => {
      if (!(userId in current)) return current;
      const next = { ...current };
      delete next[userId];
      return next;
    });
  }, []);

  const peerFor = useCallback(
    (userId: string, initiator: boolean) => {
      const existing = peers.current.get(userId);
      if (existing) return existing;
      const connection = new RTCPeerConnection(iceRef.current);
      const stream = localRef.current;
      stream?.getTracks().forEach((track) => connection.addTrack(track, stream));
      // While I share my screen, newcomers get the screen instead of the camera.
      const screenTrack = screenRef.current?.getVideoTracks()[0];
      if (screenTrack) {
        const sender = connection.getSenders().find((item) => item.track?.kind === "video");
        void sender?.replaceTrack(screenTrack);
      }
      if (initiator) watchChannel(userId, connection.createDataChannel("state"));
      connection.ondatachannel = (event) => watchChannel(userId, event.channel);
      connection.onicecandidate = (event) => event.candidate && signal(userId, "ice", event.candidate.toJSON());
      connection.ontrack = (event) => {
        const incoming = event.streams[0] ?? new MediaStream([event.track]);
        setRemote((current) => ({ ...current, [userId]: incoming }));
      };
      connection.onconnectionstatechange = () => {
        if (connection.connectionState === "failed")
          notify("Could not connect to someone. Their network may block calls.");
      };
      peers.current.set(userId, connection);
      return connection;
    },
    [notify, signal, watchChannel],
  );

  const teardown = useCallback(() => {
    peers.current.forEach((connection) => connection.close());
    peers.current.clear();
    channels.current.clear();
    queued.current.clear();
    seenRef.current = new Set();
    setRemote({});
    setPeerState({});
    setLobby([]);
    setPanel(null);
    setLines([]);
    lineIds.current = new Set();
    setUnread(0);
    setHand(false);
    setTray(false);
    setSettings(false);
    setPinned(null);
    setFloating([]);
    handsRef.current = new Set();
    stateRef.current = { ...stateRef.current, hand: false };
    setCall(null);
    callRef.current = null;
  }, []);

  const enter = useCallback(
    async (joined: Call) => {
      const self = meRef.current;
      setCall(joined);
      callRef.current = joined;
      seenRef.current = new Set(joined.participants.map((seat) => seat.id));
      setPhase("incall");
      if (codeRef.current) rememberCall(codeRef.current);
      if (audioContext()?.state === "suspended") setSoundOff(true);
      // Audio-only call: do not send the camera.
      if (joined.kind === "AUDIO") {
        localRef.current?.getVideoTracks().forEach((track) => {
          track.stop();
          localRef.current?.removeTrack(track);
        });
      }
      // The newcomer calls everyone already there.
      for (const seat of joined.participants) {
        if (seat.id === self?.id) continue;
        const connection = peerFor(seat.id, true);
        const offer = await connection.createOffer();
        await connection.setLocalDescription(offer);
        signal(seat.id, "offer", offer);
      }
    },
    [peerFor, signal],
  );

  // -- joining, asking, leaving --------------------------------------------------------------

  const join = useCallback(async () => {
    unlockSounds();
    if (!info || !code) return;
    setProblem("");
    if (!localRef.current) {
      const stream = await acquire(wantsVideo);
      localRef.current = stream;
      setLocal(stream);
    }
    if (!localRef.current) {
      setProblem("Allow the microphone for this site in your browser, then try again.");
      return;
    }
    setPhase("joining");
    try {
      if (info.member && info.conversation_id) {
        const kind = info.live ? info.kind : (kindHint ?? "VIDEO");
        await enter(await chatApi<Call>(`/conversations/${info.conversation_id}/calls`, jsonBody("POST", { kind })));
      } else if (info.admission === "ADMITTED" && info.call) {
        await enter(await chatApi<Call>(`/calls/${info.call.id}/join`, { method: "POST" }));
      } else {
        const next = await chatApi<MeetInfo>(`/meet/${code}/knock`, { method: "POST" });
        setInfo(next);
        if (next.admission === "ADMITTED" && next.call) {
          sounds.admitted();
          await enter(await chatApi<Call>(`/calls/${next.call.id}/join`, { method: "POST" }));
        } else setPhase(next.admission === "DENIED" ? "denied" : "asking");
      }
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "Could not join the call.");
      setPhase("prejoin");
      void loadInfo(code).catch(() => undefined);
    }
  }, [info, code, acquire, wantsVideo, kindHint, enter, loadInfo]);

  const cancelAsk = useCallback(async () => {
    if (code) await chatApi(`/meet/${code}/knock`, { method: "DELETE" }).catch(() => undefined);
    setPhase("prejoin");
  }, [code]);

  const leave = useCallback(
    async (next: Phase = "left") => {
      const current = callRef.current;
      teardown();
      stopLocal();
      sounds.end();
      if (codeRef.current) forgetCall(codeRef.current);
      setPhase(next);
      if (current) await chatApi(`/calls/${current.id}/leave`, { method: "POST" }).catch(() => undefined);
    },
    [teardown, stopLocal],
  );

  const rejoin = useCallback(async () => {
    if (!code) return;
    setPhase("loading");
    const next = await loadInfo(code).catch(() => null);
    setPhase(next ? (next.admission === "DENIED" ? "denied" : "prejoin") : "missing");
  }, [code, loadInfo]);

  // While asking: say "still here" every few seconds and pick up the answer.
  useEffect(() => {
    if (phase !== "asking" || !code) return;
    const check = async () => {
      const next = await chatApi<MeetInfo>(`/meet/${code}/knock`, { method: "POST" }).catch(() => null);
      if (!next || phaseRef.current !== "asking") return;
      setInfo(next);
      if (next.admission === "ADMITTED" && next.call) {
        sounds.admitted();
        setPhase("joining");
        try {
          await enter(await chatApi<Call>(`/calls/${next.call.id}/join`, { method: "POST" }));
        } catch (reason) {
          setProblem(reason instanceof Error ? reason.message : "Could not join the call.");
          setPhase("prejoin");
        }
      } else if (next.admission === "DENIED") setPhase("denied");
      else if (!next.live) {
        setProblem("The call ended before you were let in.");
        setPhase("prejoin");
      }
    };
    const timer = window.setInterval(() => void check(), 8000);
    const off = subscribeRealtime((event) => {
      if (event.type === "call.admission") void check();
    });
    const bye = () => void fetch(`/api/chat/meet/${code}/knock`, { method: "DELETE", keepalive: true });
    window.addEventListener("pagehide", bye);
    return () => {
      window.clearInterval(timer);
      off();
      window.removeEventListener("pagehide", bye);
    };
  }, [phase, code, enter]);

  // -- in the call ---------------------------------------------------------------------------

  const loadLobby = useCallback(async () => {
    const current = callRef.current;
    if (!current) return;
    const result = await chatApi<{ items: Waiting[] }>(`/calls/${current.id}/lobby`).catch(() => null);
    if (result) setLobby(result.items);
  }, []);

  const loadLines = useCallback(async () => {
    const current = callRef.current;
    if (!current) return;
    const result = await chatApi<{ items: ChatMessage[] }>(`/calls/${current.id}/messages`).catch(() => null);
    if (!result) return;
    result.items.forEach((item) => lineIds.current.add(item.id));
    setLines(result.items);
  }, []);

  useEffect(() => {
    if (phase !== "incall") return;
    const first = window.setTimeout(() => {
      void loadLobby();
      void loadLines();
    }, 0);
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    const ping = window.setInterval(() => {
      const current = callRef.current;
      if (!current) return;
      if (codeRef.current) rememberCall(codeRef.current);
      void chatApi(`/calls/${current.id}/ping`, { method: "POST" }).catch(() => {
        notify("You were disconnected from the call.");
        void leave("left");
      });
    }, 10_000);
    const lobbyTimer = window.setInterval(() => void loadLobby(), 15_000);
    const bye = () => {
      const current = callRef.current;
      if (current) navigator.sendBeacon?.(`/api/chat/calls/${current.id}/leave`);
    };
    window.addEventListener("pagehide", bye);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(tick);
      window.clearInterval(ping);
      window.clearInterval(lobbyTimer);
      window.removeEventListener("pagehide", bye);
    };
  }, [phase, loadLobby, loadLines, leave, notify]);

  // Live events: people joining and leaving, the lobby, WebRTC signals.
  useEffect(
    () =>
      subscribeRealtime((event) => {
        const data = event.data as Record<string, unknown>;
        const current = callRef.current;
        if (event.type === "call.update") {
          const update = data.call as Call;
          if (!current || current.id !== update.id) return;
          if (update.ended_at) {
            void leave("ended");
            return;
          }
          const self = meRef.current?.id;
          const here = new Set(update.participants.map((seat) => seat.id));
          const before = seenRef.current;
          const joined = update.participants.filter((seat) => seat.id !== self && !before.has(seat.id));
          const gone = [...before].filter((id) => id !== self && !here.has(id));
          if (joined.length) sounds.join();
          else if (gone.length) sounds.leave();
          joined.forEach((seat) => notify(`${seat.name} joined`));
          gone.forEach((id) => {
            const name = current.participants.find((seat) => seat.id === id)?.name;
            if (name) notify(`${name} left`);
          });
          seenRef.current = here;
          setCall(update);
          [...peers.current.keys()].forEach((id) => !here.has(id) && dropPeer(id));
        } else if (event.type === "call.knock") {
          if (!current || data.call_id !== current.id) return;
          sounds.knock();
          void loadLobby();
        } else if (event.type === "call.lobby") {
          if (current && data.call_id === current.id) void loadLobby();
        } else if (event.type === "call.chat") {
          if (!current || data.call_id !== current.id) return;
          const line = data.message as ChatMessage;
          if (lineIds.current.has(line.id)) return;
          lineIds.current.add(line.id);
          setLines((items) => (items.some((item) => item.id === line.id) ? items : [...items, line]));
          if (line.sender.id === meRef.current?.id || panelRef.current === "chat") return;
          setUnread((count) => count + 1);
          sounds.message();
          notify(`${line.sender.name}: ${line.body.length > 80 ? `${line.body.slice(0, 80)}…` : line.body}`);
        } else if (event.type === "call.declined") {
          const declined = data as { call_id: string; name: string; direct: boolean };
          if (current?.id !== declined.call_id) return;
          notify(`${declined.name} declined the call.`);
          if (declined.direct && current.participants.length <= 1) void leave("left");
        } else if (event.type === "call.signal") {
          const message = data as {
            call_id: string;
            from_user_id: string;
            kind: "offer" | "answer" | "ice";
            data: unknown;
          };
          if (!current || current.id !== message.call_id) return;
          const from = message.from_user_id;
          void (async () => {
            const connection = peerFor(from, false);
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
    [dropPeer, leave, loadLobby, notify, peerFor, signal],
  );

  // The caller hears ringback in a one-to-one call until the other person picks up.
  const alone = phase === "incall" && (call?.participants.length ?? 0) <= 1;
  const ringback = alone && info?.type === "DIRECT" && call?.started_by_id === me?.id;
  useEffect(() => {
    if (!ringback) return;
    const stop = repeat(sounds.ringback, 4000);
    const quit = window.setTimeout(stop, 45_000);
    return () => {
      stop();
      window.clearTimeout(quit);
    };
  }, [ringback]);

  // One tab per call: a second tab asks the first one to hand over.
  useEffect(() => {
    if (!code || typeof BroadcastChannel === "undefined") return;
    const channel = new BroadcastChannel(`adverse-call-${code}`);
    channel.onmessage = (event) => {
      if (event.data === "who" && phaseRef.current === "incall") channel.postMessage("here");
      else if (event.data === "here" && phaseRef.current === "prejoin") setElsewhere(true);
      else if (event.data === "takeover" && phaseRef.current === "incall") {
        notify("This call moved to another tab.");
        void leave("left");
      }
    };
    channel.postMessage("who");
    return () => channel.close();
  }, [code, leave, notify]);

  // Back after a reload while in the call: join again by itself once the camera is ready.
  useEffect(() => {
    if (phase !== "prejoin" || !local || !autoJoin.current) return;
    autoJoin.current = false;
    const timer = window.setTimeout(() => void join(), 0);
    return () => window.clearTimeout(timer);
  }, [phase, local, join]);

  // Browsers keep sound off after a reload until a click: the first click anywhere turns it on.
  const turnSoundOn = useCallback(() => {
    unlockSounds();
    document.querySelectorAll("audio").forEach((element) => void element.play().catch(() => undefined));
    setSoundOff(false);
  }, []);
  useEffect(() => {
    if (!soundOff) return;
    document.addEventListener("pointerdown", turnSoundOn, { once: true });
    return () => document.removeEventListener("pointerdown", turnSoundOn);
  }, [soundOff, turnSoundOn]);

  // -- controls ------------------------------------------------------------------------------

  function setState(next: Partial<PeerState>) {
    stateRef.current = { ...stateRef.current, ...next };
    broadcastState();
  }

  function toggleMic() {
    const next = !micOn;
    localRef.current?.getAudioTracks().forEach((track) => (track.enabled = next));
    setMicOn(next);
    setState({ mic: next });
  }

  function toggleCamera() {
    const next = !camOn;
    localRef.current?.getVideoTracks().forEach((track) => (track.enabled = next));
    setCamOn(next);
    setState({ cam: next });
  }

  function replaceVideo(track: MediaStreamTrack | null) {
    peers.current.forEach((connection) => {
      const sender = connection.getSenders().find((item) => item.track?.kind === "video" || item.track === null);
      void sender?.replaceTrack(track);
    });
  }

  async function toggleShare() {
    if (sharing) {
      screenRef.current?.getTracks().forEach((track) => track.stop());
      screenRef.current = null;
      setScreen(null);
      replaceVideo(localRef.current?.getVideoTracks()[0] ?? null);
      setSharing(false);
      setState({ sharing: false });
      return;
    }
    try {
      const display = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const track = display.getVideoTracks()[0];
      screenRef.current = display;
      setScreen(display);
      replaceVideo(track);
      setSharing(true);
      setState({ sharing: true });
      track.onended = () => {
        replaceVideo(localRef.current?.getVideoTracks()[0] ?? null);
        screenRef.current = null;
        setScreen(null);
        setSharing(false);
        setState({ sharing: false });
      };
    } catch {
      // The person closed the screen picker.
    }
  }

  async function switchDevice(kind: "audio" | "video", deviceId: string) {
    if (kind === "audio") setMicId(deviceId);
    else setCamId(deviceId);
    const fresh = await navigator.mediaDevices
      .getUserMedia(
        kind === "audio" ? { audio: { deviceId: { exact: deviceId } } } : { video: { deviceId: { exact: deviceId } } },
      )
      .catch(() => null);
    const track = fresh?.getTracks()[0];
    const stream = localRef.current;
    if (!track || !stream) return;
    track.enabled = kind === "audio" ? stateRef.current.mic : stateRef.current.cam;
    const old = kind === "audio" ? stream.getAudioTracks()[0] : stream.getVideoTracks()[0];
    if (old) {
      stream.removeTrack(old);
      old.stop();
    }
    stream.addTrack(track);
    peers.current.forEach((connection) => {
      const sender = connection
        .getSenders()
        .find((item) => item.track?.kind === kind || (item.track === null && kind === "video"));
      if (kind === "video" && screenRef.current) return; // keep presenting; camera returns after
      void sender?.replaceTrack(track);
    });
    const copy = new MediaStream(stream.getTracks());
    localRef.current = copy;
    setLocal(copy);
  }

  async function decide(person: Waiting, admit: boolean) {
    const current = callRef.current;
    if (!current) return;
    setLobby((items) => items.filter((item) => item.id !== person.id));
    try {
      await chatApi(`/calls/${current.id}/lobby/${person.id}`, jsonBody("POST", { admit }));
      notify(admit ? `${person.name} was let in` : `${person.name} was not let in`);
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Could not answer the request.");
      void loadLobby();
    }
  }

  async function copyLink() {
    if (!code) return;
    await navigator.clipboard?.writeText(`${window.location.origin}/call/${code}`).catch(() => undefined);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  function toggleHand() {
    const next = !hand;
    setHand(next);
    setState({ hand: next });
    if (next) sounds.hand();
  }

  function react(emoji: string) {
    const text = JSON.stringify({ type: "reaction", emoji } satisfies ChannelMessage);
    channels.current.forEach((channel) => channel.readyState === "open" && channel.send(text));
    float(emoji, "You");
    setTray(false);
  }

  /** Host or admin: ask someone to turn their microphone off (only they can turn it back on). */
  function askToMute(userId: string) {
    const channel = channels.current.get(userId);
    if (channel?.readyState !== "open") return;
    channel.send(JSON.stringify({ type: "mute" } satisfies ChannelMessage));
    const name = call?.participants.find((seat) => seat.id === userId)?.name;
    notify(`You muted ${name ?? "them"}`);
  }

  function openPanel(next: Panel) {
    setPanel((current) => (current === next ? null : next));
    if (next === "chat") setUnread(0);
  }

  async function say(event?: FormEvent) {
    event?.preventDefault();
    const current = callRef.current;
    const text = draft.trim();
    if (!current || !text || sending) return;
    setSending(true);
    try {
      const line = await chatApi<ChatMessage>(`/calls/${current.id}/messages`, jsonBody("POST", { body: text }));
      lineIds.current.add(line.id);
      setLines((items) => (items.some((item) => item.id === line.id) ? items : [...items, line]));
      setDraft("");
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Could not send the message.");
    } finally {
      setSending(false);
    }
  }

  function draftKeys(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) void say(event);
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      notify("Full screen is not available here.");
    }
  }

  function pickSpeaker(deviceId: string) {
    setSpeakerId(deviceId);
    document.querySelectorAll("audio").forEach((element) => {
      const sink = element as HTMLAudioElement & { setSinkId?: (id: string) => Promise<void> };
      void sink.setSinkId?.(deviceId).catch(() => undefined);
    });
  }

  // Someone asked me to mute: only the host or an admin in the call may (checked here too).
  useEffect(() => {
    muteRequest.current = (from: string) => {
      const seat = callRef.current?.participants.find((item) => item.id === from);
      if (!seat || (seat.role !== "ADMIN" && seat.id !== callRef.current?.started_by_id)) return;
      if (stateRef.current.mic) {
        localRef.current?.getAudioTracks().forEach((track) => (track.enabled = false));
        setMicOn(false);
        stateRef.current = { ...stateRef.current, mic: false };
        broadcastState();
      }
      notify(`${seat.name} muted you`);
    };
  }, [broadcastState, notify]);

  useEffect(() => {
    const change = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", change);
    return () => document.removeEventListener("fullscreenchange", change);
  }, []);

  // Keyboard shortcuts in the call (the same keys as Google Meet).
  const keys = useRef<Record<string, () => void>>({});
  useEffect(() => {
    keys.current = {
      d: toggleMic,
      e: () => callKind === "VIDEO" && toggleCamera(),
      h: toggleHand,
      c: () => openPanel("chat"),
      p: () => openPanel("people"),
      f: () => void toggleFullscreen(),
    };
  });
  useEffect(() => {
    if (phase !== "incall") return;
    const press = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.repeat) return;
      const key = event.key.toLowerCase();
      const simple = (key === "d" || key === "e") && !event.altKey && !event.shiftKey;
      const withAlt = ["h", "c", "p", "f"].includes(event.code.replace("Key", "").toLowerCase()) && event.altKey;
      if (!simple && !withAlt) return;
      event.preventDefault();
      keys.current[simple ? key : event.code.replace("Key", "").toLowerCase()]?.();
    };
    window.addEventListener("keydown", press);
    return () => window.removeEventListener("keydown", press);
  }, [phase]);

  // The chat panel follows the newest line.
  useEffect(() => {
    if (panel === "chat") linesEnd.current?.scrollIntoView({ block: "end" });
  }, [panel, lines]);

  // -- view ----------------------------------------------------------------------------------

  const others = useMemo(() => (call?.participants ?? []).filter((seat) => seat.id !== me?.id), [call, me]);
  const meters = useMemo(() => {
    const streams: Record<string, MediaStream | null> = { ...remote };
    if (me) streams[me.id] = local;
    return streams;
  }, [remote, local, me]);
  const speaking = useSpeaking(meters, phase === "incall");
  const [gridRef, gridBox] = useBox<HTMLDivElement>();
  const [mainRef, mainBox] = useBox<HTMLDivElement>();
  // Spotlight layout follows whoever else spoke last.
  useEffect(() => {
    const talker = [...speaking].find((id) => id !== me?.id);
    if (!talker) return;
    const timer = window.setTimeout(() => setLastSpeaker(talker), 0);
    return () => window.clearTimeout(timer);
  }, [speaking, me]);
  const presenter = sharing ? me?.id : others.find((seat) => peerState[seat.id]?.sharing)?.id;
  const myRole = call?.participants.find((seat) => seat.id === me?.id)?.role;
  const canMute = Boolean(me && call && (call.started_by_id === me.id || myRole === "ADMIN"));
  const hands = others.filter((seat) => peerState[seat.id]?.hand).map((seat) => seat.id);
  const started = call ? new Date(call.started_at).getTime() : now;
  const hasCamera = Boolean(local?.getVideoTracks().length);
  const linkText = code ? `${typeof window === "undefined" ? "" : window.location.host}/call/${code}` : "";

  if (phase === "loading" || phase === "joining") {
    return (
      <main className="callroom center">
        <OrbitLoader size={72} label={phase === "joining" ? "Joining" : "Opening the call"} />
        <p>{phase === "joining" ? "Joining…" : "Opening the call…"}</p>
      </main>
    );
  }

  if (phase === "missing") {
    return (
      <main className="callroom center">
        <h1>Can&apos;t open this call</h1>
        <p>{problem || "Check the link and try again."}</p>
        <Link className="callroom-button" href="/chat">
          <ArrowLeft /> Go to chat
        </Link>
      </main>
    );
  }

  if (phase === "left" || phase === "ended" || phase === "denied") {
    const heading =
      phase === "ended" ? "The call has ended" : phase === "denied" ? "You can't join this call" : "You left the call";
    return (
      <main className="callroom center">
        <h1>{heading}</h1>
        {phase === "denied" && <p>Someone in the call declined your request to join.</p>}
        {info && <p className="muted">{info.title}</p>}
        <div className="callroom-row">
          {phase !== "denied" && (
            <button type="button" className="callroom-button primary" onClick={() => void rejoin()}>
              {phase === "ended" ? "Back to the link" : "Rejoin"}
            </button>
          )}
          <Link className="callroom-button" href="/chat">
            Go to chat
          </Link>
        </div>
      </main>
    );
  }

  if (phase === "prejoin" || phase === "asking") {
    const outsider = info && !info.member && info.admission !== "ADMITTED";
    const waitingForHost = outsider && !info?.live;
    const people = info?.in_call ?? [];
    return (
      <main className="callroom prejoin">
        <Link className="callroom-back" href="/chat" aria-label="Back to chat">
          <ArrowLeft />
        </Link>
        <section className="callroom-preview">
          <div className="callroom-preview-video">
            {wantsVideo && camOn && hasCamera ? (
              <video
                className="mirror"
                autoPlay
                playsInline
                muted
                ref={(element) => {
                  if (element && element.srcObject !== local) element.srcObject = local;
                }}
              />
            ) : (
              <div className="callroom-preview-off">
                <Avatar name={me?.name ?? "You"} image={me?.image} size="lg" />
                <span>
                  {!local
                    ? "Allow camera and microphone to be seen and heard"
                    : wantsVideo
                      ? "Camera is off"
                      : "Voice call"}
                </span>
              </div>
            )}
            <span className="callroom-preview-name">{me?.name}</span>
            <div className="callroom-preview-controls">
              <button
                type="button"
                className={`callroom-round${micOn ? "" : " off"}`}
                aria-label={micOn ? "Turn microphone off" : "Turn microphone on"}
                title={micOn ? "Turn microphone off" : "Turn microphone on"}
                onClick={toggleMic}
              >
                {micOn ? <Mic /> : <MicOff />}
              </button>
              {wantsVideo && (
                <button
                  type="button"
                  className={`callroom-round${camOn && !camBlocked ? "" : " off"}`}
                  aria-label={camOn ? "Turn camera off" : "Turn camera on"}
                  title={camBlocked ? "Camera not available" : camOn ? "Turn camera off" : "Turn camera on"}
                  disabled={camBlocked}
                  onClick={toggleCamera}
                >
                  {camOn && !camBlocked ? <Video /> : <VideoOff />}
                </button>
              )}
            </div>
          </div>
          {(mics.length > 0 || (wantsVideo && cams.length > 0)) && (
            <div className="callroom-devices">
              {mics.length > 0 && (
                <label>
                  <Mic aria-hidden="true" />
                  <LooplessSelect
                    value={micId}
                    options={mics}
                    onValueChange={(value) => void switchDevice("audio", value)}
                    ariaLabel="Microphone"
                  />
                </label>
              )}
              {wantsVideo && cams.length > 0 && (
                <label>
                  <Video aria-hidden="true" />
                  <LooplessSelect
                    value={camId}
                    options={cams}
                    onValueChange={(value) => void switchDevice("video", value)}
                    ariaLabel="Camera"
                  />
                </label>
              )}
            </div>
          )}
        </section>

        <section className="callroom-ready">
          {phase === "asking" ? (
            <>
              <h1>Asking to join…</h1>
              <p>You&apos;ll join when someone in the call lets you in.</p>
              <OrbitLoader size={56} label="Waiting to be let in" />
              <button type="button" className="callroom-button" onClick={() => void cancelAsk()}>
                Cancel
              </button>
            </>
          ) : (
            <>
              <h1>{waitingForHost ? "Waiting for the host" : outsider ? "Ask to join?" : "Ready to join?"}</h1>
              <p className="callroom-title">{info?.title}</p>
              <p className="muted">
                {people.length
                  ? `${listNames(people)} ${people.length === 1 ? "is" : "are"} in this call`
                  : waitingForHost
                    ? "The call has not started yet. This page checks every few seconds."
                    : "No one else is here yet"}
              </p>
              {elsewhere && (
                <p className="callroom-warning">
                  You&apos;re already in this call in another tab.{" "}
                  <button
                    type="button"
                    onClick={() => {
                      new BroadcastChannel(`adverse-call-${code}`).postMessage("takeover");
                      setElsewhere(false);
                    }}
                  >
                    Use this tab instead
                  </button>
                </p>
              )}
              {problem && <p className="callroom-warning">{problem}</p>}
              <div className="callroom-row">
                <button
                  type="button"
                  className="callroom-button primary"
                  disabled={Boolean(waitingForHost) || elsewhere}
                  onClick={() => void join()}
                >
                  {outsider ? <Hand /> : null}
                  {outsider ? "Ask to join" : info?.live ? "Join now" : "Start call"}
                </button>
                {info?.member && (
                  <button type="button" className="callroom-button" onClick={() => void copyLink()}>
                    {copied ? <Check /> : <Link2 />} {copied ? "Link copied" : "Copy link"}
                  </button>
                )}
              </div>
              {outsider && !waitingForHost && (
                <p className="muted small">
                  You&apos;re not in this chat, so {info?.host_name ?? "the host"} or an admin in the call needs to let
                  you in.
                </p>
              )}
            </>
          )}
        </section>
      </main>
    );
  }

  // In the call.
  const tiles = [
    ...(me
      ? [
          {
            id: me.id,
            name: me.name,
            image: me.image,
            role: "",
            stream: sharing && screen ? screen : local,
            video: sharing ? true : callKind === "VIDEO" && camOn && hasCamera,
            mic: micOn,
            mine: true,
            screen: sharing,
            hand,
          },
        ]
      : []),
    ...others.map((seat) => {
      const state = peerState[seat.id];
      return {
        id: seat.id,
        name: seat.name,
        image: seat.image,
        role: ROLE_LABEL[seat.role] ?? "",
        stream: remote[seat.id] ?? null,
        video: callKind === "VIDEO" && (state ? state.cam || state.sharing : true) && Boolean(remote[seat.id]),
        mic: state ? state.mic : true,
        mine: false,
        screen: Boolean(state?.sharing),
        hand: Boolean(state?.hand),
      };
    }),
  ];
  const pinnedHere = pinned && tiles.some((tile) => tile.id === pinned) ? pinned : undefined;
  const talker = lastSpeaker && others.some((seat) => seat.id === lastSpeaker) ? lastSpeaker : others[0]?.id;
  const focusId =
    layout === "tiled"
      ? pinnedHere
      : layout === "spotlight"
        ? (presenter ?? pinnedHere ?? talker)
        : (presenter ?? pinnedHere);
  const spotlight = focusId ? tiles.find((tile) => tile.id === focusId) : undefined;
  const strip = spotlight ? tiles.filter((tile) => tile.id !== spotlight.id) : tiles;
  // One other person: they fill the stage and I am a small picture in the corner (like Meet).
  const solo = !spotlight && layout !== "tiled" && others.length === 1;
  const mineTile = tiles.find((tile) => tile.mine);
  const gridTiles = solo ? tiles.filter((tile) => !tile.mine) : strip;
  const aloneCard = others.length === 0 && !spotlight;
  const tileSize = fitTiles(gridTiles.length + (aloneCard ? 1 : 0), gridBox, 12);
  const canPin = tiles.length > 1;
  const pin = (id: string) => setPinned((current) => (current === id ? null : id));
  const seats = [...(call?.participants ?? [])].sort(
    (a, b) => Number(Boolean(peerState[b.id]?.hand)) - Number(Boolean(peerState[a.id]?.hand)),
  );
  const startedClock = call ? clock(call.started_at) : "";
  const host = call?.participants.find((seat) => seat.id === call.started_by_id)?.name ?? info?.host_name;

  return (
    <main className={`callroom incall${panel ? " with-panel" : ""}`}>
      {/* Everyone else's voice plays here. */}
      {Object.entries(remote).map(([id, stream]) => (
        <audio
          key={id}
          autoPlay
          ref={(element) => {
            if (element && element.srcObject !== stream) {
              element.srcObject = stream;
              const sink = element as HTMLAudioElement & { setSinkId?: (id: string) => Promise<void> };
              if (speakerRef.current) void sink.setSinkId?.(speakerRef.current).catch(() => undefined);
              void element.play().catch(() => setSoundOff(true));
            }
          }}
        />
      ))}

      <div className="callroom-body">
        <section className={`callroom-stage${spotlight ? " spotlight" : ""}`}>
          {spotlight ? (
            <>
              <div className="callroom-main" ref={mainRef}>
                <Tile
                  {...spotlight}
                  size={fitTiles(1, mainBox, 0)}
                  speaking={speaking.has(spotlight.id)}
                  pinned={pinnedHere === spotlight.id}
                  onPin={canPin ? () => pin(spotlight.id) : undefined}
                />
              </div>
              <div className="callroom-strip">
                {strip.map((tile) => (
                  <Tile
                    key={tile.id}
                    {...tile}
                    className="small"
                    screen={false}
                    speaking={speaking.has(tile.id)}
                    pinned={pinnedHere === tile.id}
                    onPin={canPin ? () => pin(tile.id) : undefined}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="callroom-grid" ref={gridRef}>
              {gridTiles.map((tile) => (
                <Tile
                  key={tile.id}
                  {...tile}
                  size={tileSize}
                  speaking={speaking.has(tile.id)}
                  pinned={pinnedHere === tile.id}
                  onPin={canPin ? () => pin(tile.id) : undefined}
                />
              ))}
              {aloneCard && (
                <div
                  className="callroom-alone"
                  style={tileSize.width > 0 ? { width: tileSize.width, height: tileSize.height } : undefined}
                >
                  <strong>{ringback ? `Calling ${info?.title ?? ""}…` : "You're the only one here"}</strong>
                  {code && (
                    <>
                      <span>Share this link with others you want in the call</span>
                      <button type="button" className="callroom-linkbox" onClick={() => void copyLink()}>
                        <span>{linkText}</span>
                        {copied ? <Check /> : <Copy />}
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
          {solo && mineTile && <Tile {...mineTile} className="pip" speaking={speaking.has(mineTile.id)} />}
          <div className="callroom-floating" aria-hidden="true">
            {floating.map((item) => (
              <span key={item.id} style={{ left: `${item.left}%` }}>
                {(() => {
                  const Icon = REACTION_ICONS[item.emoji as ReactionKey]?.Icon;
                  return Icon ? (
                    <b className={`callroom-reaction ${item.emoji}`}>
                      <Icon />
                    </b>
                  ) : null;
                })()}
                <small>{item.name}</small>
              </span>
            ))}
          </div>
        </section>

        {panel && (
          <aside className="callroom-panel" aria-label="Call details">
            <header>
              <div className="callroom-tabs" role="tablist" aria-label="Call panel">
                {(
                  [
                    ["people", "People", <Users key="i" />],
                    ["chat", "Chat", <MessageSquareText key="i" />],
                    ["info", "Info", <Info key="i" />],
                  ] as const
                ).map(([value, label, icon]) => (
                  <button
                    key={value}
                    type="button"
                    role="tab"
                    aria-selected={panel === value}
                    className={panel === value ? "active" : undefined}
                    onClick={() => {
                      setPanel(value);
                      if (value === "chat") setUnread(0);
                    }}
                  >
                    {icon}
                    {label}
                    {value === "chat" && unread > 0 && <span className="callroom-dot">{unread}</span>}
                  </button>
                ))}
              </div>
              <button type="button" className="callroom-icon" aria-label="Close" onClick={() => setPanel(null)}>
                <X />
              </button>
            </header>

            {panel === "people" && (
              <div className="callroom-panel-body">
                {code && (
                  <button type="button" className="callroom-linkbox" onClick={() => void copyLink()}>
                    <span>{linkText}</span>
                    {copied ? <Check /> : <Copy />}
                  </button>
                )}
                {lobby.length > 0 && (
                  <>
                    <h2>Waiting to join · {lobby.length}</h2>
                    <ul>
                      {lobby.map((person) => (
                        <li key={person.id}>
                          <Avatar name={person.name} image={person.image} />
                          <span>
                            {person.name}
                            <small>{ROLE_LABEL[person.role]}</small>
                          </span>
                          <button type="button" className="callroom-chip" onClick={() => void decide(person, false)}>
                            Deny
                          </button>
                          <button
                            type="button"
                            className="callroom-chip primary"
                            onClick={() => void decide(person, true)}
                          >
                            Admit
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                <div className="callroom-panel-row">
                  <h2>In the call · {call?.participants.length ?? 0}</h2>
                  {canMute && others.some((seat) => peerState[seat.id]?.mic ?? true) && (
                    <button
                      type="button"
                      className="callroom-chip"
                      onClick={() => others.forEach((seat) => (peerState[seat.id]?.mic ?? true) && askToMute(seat.id))}
                    >
                      <MicOff /> Mute everyone
                    </button>
                  )}
                </div>
                <ul>
                  {seats.map((seat) => {
                    const mine = seat.id === me?.id;
                    const mic = mine ? micOn : (peerState[seat.id]?.mic ?? true);
                    const raised = mine ? hand : Boolean(peerState[seat.id]?.hand);
                    return (
                      <li key={seat.id}>
                        <Avatar name={seat.name} image={seat.image} />
                        <span>
                          {seat.name}
                          {mine ? " (you)" : ""}
                          <small>
                            {ROLE_LABEL[seat.role]}
                            {seat.id === call?.started_by_id ? " · Host" : ""}
                            {raised ? " · Hand raised" : ""}
                          </small>
                        </span>
                        {raised && <Hand aria-label="Hand raised" className="hand" />}
                        {canPin && (
                          <button
                            type="button"
                            className="callroom-icon small"
                            aria-label={pinnedHere === seat.id ? `Unpin ${seat.name}` : `Pin ${seat.name}`}
                            title={pinnedHere === seat.id ? "Unpin" : "Pin to the main screen"}
                            onClick={() => pin(seat.id)}
                          >
                            {pinnedHere === seat.id ? <PinOff /> : <Pin />}
                          </button>
                        )}
                        {!mine && canMute && mic ? (
                          <button
                            type="button"
                            className="callroom-icon small"
                            aria-label={`Mute ${seat.name}`}
                            title={`Mute ${seat.name} (only they can turn it back on)`}
                            onClick={() => askToMute(seat.id)}
                          >
                            <Mic />
                          </button>
                        ) : mic ? (
                          <Mic aria-label="Microphone on" />
                        ) : (
                          <MicOff aria-label="Muted" className="off" />
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {panel === "chat" && (
              <div className="callroom-chat">
                <p className="callroom-chat-note">
                  {info?.member
                    ? "Messages here are saved in the chat as well."
                    : "Messages are saved in the chat. You see them while you're in the call."}
                </p>
                <ul className="callroom-lines" aria-live="polite">
                  {lines.length === 0 && <li className="callroom-lines-empty">No messages yet. Say hello.</li>}
                  {lines.map((line, index) => {
                    const previous = lines[index - 1];
                    const grouped =
                      previous !== undefined &&
                      previous.sender.id === line.sender.id &&
                      new Date(line.created_at).getTime() - new Date(previous.created_at).getTime() < 5 * 60_000;
                    const mine = line.sender.id === me?.id;
                    return (
                      <li key={line.id} className={`${mine ? "mine" : ""}${grouped ? " grouped" : ""}`}>
                        {!grouped && (
                          <header>
                            <strong>{mine ? "You" : line.sender.name}</strong>
                            <time dateTime={line.created_at}>{clock(line.created_at)}</time>
                          </header>
                        )}
                        {line.deleted ? (
                          <p className="gone">Message deleted</p>
                        ) : (
                          line.body && (
                            <p>
                              <Linked text={line.body} />
                            </p>
                          )
                        )}
                        {!line.deleted &&
                          line.attachments.map((file) =>
                            info?.member ? (
                              <a
                                key={file.id}
                                className="callroom-file"
                                href={`/api/chat/attachments/${file.id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <Paperclip /> {file.file_name}
                              </a>
                            ) : (
                              <span key={file.id} className="callroom-file">
                                <Paperclip /> {file.file_name}
                              </span>
                            ),
                          )}
                      </li>
                    );
                  })}
                  <li ref={linesEnd} className="callroom-lines-end" aria-hidden="true" />
                </ul>
                <form className="callroom-compose" onSubmit={(event) => void say(event)}>
                  <textarea
                    rows={1}
                    value={draft}
                    maxLength={4000}
                    placeholder="Send a message"
                    aria-label="Message everyone in the call"
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={draftKeys}
                  />
                  <button
                    type="submit"
                    className="callroom-icon send"
                    aria-label="Send message"
                    disabled={!draft.trim() || sending}
                  >
                    <SendHorizontal />
                  </button>
                </form>
              </div>
            )}

            {panel === "info" && (
              <div className="callroom-panel-body">
                <h2>Meeting details</h2>
                <dl className="callroom-facts">
                  <div>
                    <dt>Meeting</dt>
                    <dd>{info?.title}</dd>
                  </div>
                  {host && (
                    <div>
                      <dt>Host</dt>
                      <dd>{host}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Started</dt>
                    <dd>
                      {startedClock} · {clockSince(started, now)} ago
                    </dd>
                  </div>
                  {code && (
                    <div>
                      <dt>Code</dt>
                      <dd>{code}</dd>
                    </div>
                  )}
                </dl>
                {code && (
                  <button type="button" className="callroom-linkbox" onClick={() => void copyLink()}>
                    <span>{linkText}</span>
                    {copied ? <Check /> : <Copy />}
                  </button>
                )}
                <p className="muted small">
                  People in this chat join straight away. Anyone else in the company asks to join and waits until the
                  host or an admin in the call lets them in.
                </p>
                <h2>
                  <Keyboard /> Keyboard shortcuts
                </h2>
                <dl className="callroom-keys">
                  {SHORTCUTS.map(([combo, what]) => (
                    <div key={combo}>
                      <dt>
                        <kbd>{combo}</kbd>
                      </dt>
                      <dd>{what}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </aside>
        )}
      </div>

      {/* Someone is waiting: answer without opening the panel. */}
      {lobby.length > 0 && panel !== "people" && (
        <div className="callroom-knock" role="alertdialog" aria-label="Someone wants to join">
          <Avatar name={lobby[0].name} image={lobby[0].image} />
          <span>
            <strong>{lobby[0].name}</strong> wants to join
            {lobby.length > 1 ? ` (+${lobby.length - 1} more)` : ""}
          </span>
          <button type="button" className="callroom-chip" onClick={() => void decide(lobby[0], false)}>
            Deny
          </button>
          <button type="button" className="callroom-chip primary" onClick={() => void decide(lobby[0], true)}>
            Admit
          </button>
          {lobby.length > 1 && (
            <button type="button" className="callroom-chip" onClick={() => setPanel("people")}>
              View all
            </button>
          )}
        </div>
      )}

      {soundOff && (
        <button type="button" className="callroom-soundoff" onClick={turnSoundOn}>
          <Volume2 /> Sound is off · click to turn it on
        </button>
      )}

      <div className="callroom-notices" aria-live="polite">
        {notices.map((item) => (
          <p key={item.id}>{item.text}</p>
        ))}
      </div>

      {settings && (
        <div className="callroom-dialog-backdrop" onClick={() => setSettings(false)}>
          <section
            className="callroom-dialog wide"
            role="dialog"
            aria-modal="true"
            aria-label="Call settings"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <strong>Settings</strong>
              <button type="button" className="callroom-icon" aria-label="Close" onClick={() => setSettings(false)}>
                <X />
              </button>
            </header>
            <div className="callroom-settings">
              <nav className="callroom-settings-tabs" role="tablist" aria-label="Settings sections">
                {(
                  [
                    ["audio", "Audio", <Volume2 key="i" />],
                    ...(callKind === "VIDEO" ? ([["video", "Video", <Video key="i" />]] as const) : []),
                    ["layout", "Layout", <LayoutGrid key="i" />],
                  ] as const
                ).map(([value, label, icon]) => (
                  <button
                    key={value}
                    type="button"
                    role="tab"
                    aria-selected={settingsTab === value}
                    className={settingsTab === value ? "active" : undefined}
                    onClick={() => setSettingsTab(value)}
                  >
                    {icon}
                    {label}
                  </button>
                ))}
              </nav>
              <div className="callroom-settings-body" role="tabpanel">
                {settingsTab === "audio" && (
                  <>
                    <div className="callroom-setting">
                      <span>Microphone</span>
                      <div className="callroom-setting-row">
                        {mics.length > 0 ? (
                          <LooplessSelect
                            value={micId}
                            options={mics}
                            onValueChange={(value) => void switchDevice("audio", value)}
                            ariaLabel="Microphone"
                          />
                        ) : (
                          <em>No microphone found</em>
                        )}
                        <MicMeter stream={local} />
                      </div>
                      <small>{micOn ? "Speak: the bars should move." : "Your microphone is off in the call."}</small>
                    </div>
                    <div className="callroom-setting">
                      <span>Speaker</span>
                      <div className="callroom-setting-row">
                        {speakers.length > 0 ? (
                          <LooplessSelect
                            value={speakerId || speakers[0].value}
                            options={speakers}
                            onValueChange={pickSpeaker}
                            ariaLabel="Speaker"
                          />
                        ) : (
                          <em>System default (this browser can&apos;t choose)</em>
                        )}
                        <button type="button" className="callroom-button" onClick={() => sounds.join()}>
                          <Volume2 /> Test
                        </button>
                      </div>
                    </div>
                  </>
                )}
                {settingsTab === "video" && (
                  <>
                    <div className="callroom-setting-preview">
                      {hasCamera && camOn ? (
                        <video
                          className="mirror"
                          autoPlay
                          playsInline
                          muted
                          ref={(element) => {
                            if (element && element.srcObject !== local) element.srcObject = local;
                          }}
                        />
                      ) : (
                        <span>{hasCamera ? "Your camera is off" : "No camera found"}</span>
                      )}
                    </div>
                    <div className="callroom-setting">
                      <span>Camera</span>
                      {cams.length > 0 ? (
                        <LooplessSelect
                          value={camId}
                          options={cams}
                          onValueChange={(value) => void switchDevice("video", value)}
                          ariaLabel="Camera"
                        />
                      ) : (
                        <em>No camera found</em>
                      )}
                    </div>
                  </>
                )}
                {settingsTab === "layout" && (
                  <div className="callroom-layouts" role="radiogroup" aria-label="Layout">
                    {LAYOUTS.map((item) => (
                      <button
                        key={item.value}
                        type="button"
                        role="radio"
                        aria-checked={layout === item.value}
                        className={layout === item.value ? "active" : undefined}
                        onClick={() => setLayout(item.value)}
                      >
                        <LayoutPicture kind={item.value} />
                        <strong>{item.label}</strong>
                        <small>{item.hint}</small>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      )}

      <footer className="callroom-bar">
        <div className="callroom-bar-side">
          <strong>{clockSince(started, now)}</strong>
          <span className="callroom-bar-title">{info?.title}</span>
        </div>
        <div className="callroom-bar-main">
          <button
            type="button"
            className={`callroom-round${micOn ? "" : " off"}`}
            aria-label={micOn ? "Turn microphone off" : "Turn microphone on"}
            title={`${micOn ? "Turn microphone off" : "Turn microphone on"} (Ctrl + D)`}
            onClick={toggleMic}
          >
            {micOn ? <Mic /> : <MicOff />}
          </button>
          {callKind === "VIDEO" && (
            <>
              <button
                type="button"
                className={`callroom-round${camOn && hasCamera ? "" : " off"}`}
                aria-label={camOn ? "Turn camera off" : "Turn camera on"}
                title={
                  hasCamera ? `${camOn ? "Turn camera off" : "Turn camera on"} (Ctrl + E)` : "Camera not available"
                }
                disabled={!hasCamera}
                onClick={toggleCamera}
              >
                {camOn && hasCamera ? <Video /> : <VideoOff />}
              </button>
              <button
                type="button"
                className={`callroom-round${sharing ? " on" : ""}`}
                aria-label={sharing ? "Stop presenting" : "Present your screen"}
                title={sharing ? "Stop presenting" : "Present your screen"}
                onClick={() => void toggleShare()}
              >
                <MonitorUp />
              </button>
            </>
          )}
          <div className="callroom-react">
            <button
              type="button"
              className={`callroom-round${tray ? " on" : ""}`}
              aria-label="Send a reaction"
              aria-expanded={tray}
              title="Send a reaction"
              onClick={() => setTray((open) => !open)}
            >
              <Smile />
            </button>
            {tray && (
              <div className="callroom-tray" role="menu" aria-label="Reactions">
                {REACTION_KEYS.map((key) => {
                  const { label, Icon } = REACTION_ICONS[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      role="menuitem"
                      className={`callroom-reaction ${key}`}
                      aria-label={label}
                      title={label}
                      onClick={() => react(key)}
                    >
                      <Icon />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <button
            type="button"
            className={`callroom-round${hand ? " on" : ""}`}
            aria-label={hand ? "Lower hand" : "Raise hand"}
            aria-pressed={hand}
            title={`${hand ? "Lower hand" : "Raise hand"} (Ctrl + Alt + H)`}
            onClick={toggleHand}
          >
            <Hand />
          </button>
          <button
            type="button"
            className={`callroom-round${settings ? " on" : ""}`}
            aria-label="Settings"
            title="Settings: devices and layout"
            onClick={() => {
              void refreshDevices();
              setSettings(true);
            }}
          >
            <Settings />
          </button>
          <button
            type="button"
            className="callroom-round leave"
            aria-label="Leave call"
            title="Leave call"
            onClick={() => void leave("left")}
          >
            <PhoneOff />
          </button>
        </div>
        <div className="callroom-bar-side end">
          <button
            type="button"
            className={`callroom-icon${panel === "info" ? " active" : ""}`}
            aria-label="Meeting details"
            title="Meeting details"
            onClick={() => openPanel("info")}
          >
            <Info />
          </button>
          <button
            type="button"
            className={`callroom-icon${panel === "people" ? " active" : ""}`}
            aria-label="People"
            title="People (Ctrl + Alt + P)"
            onClick={() => openPanel("people")}
          >
            <Users />
            <span className="callroom-count">{call?.participants.length ?? 0}</span>
            {lobby.length > 0 ? (
              <span className="callroom-badge">{lobby.length}</span>
            ) : hands.length > 0 ? (
              <span className="callroom-badge hand" aria-label={`${hands.length} raised`}>
                <Hand />
              </span>
            ) : null}
          </button>
          <button
            type="button"
            className={`callroom-icon${panel === "chat" ? " active" : ""}`}
            aria-label={unread ? `Chat, ${unread} new` : "Chat"}
            title="Chat with everyone (Ctrl + Alt + C)"
            onClick={() => openPanel("chat")}
          >
            <MessageSquareText />
            {unread > 0 && <span className="callroom-badge">{unread}</span>}
          </button>
          <button
            type="button"
            className="callroom-icon"
            aria-label={fullscreen ? "Exit full screen" : "Full screen"}
            title={`${fullscreen ? "Exit full screen" : "Full screen"} (Ctrl + Alt + F)`}
            onClick={() => void toggleFullscreen()}
          >
            {fullscreen ? <Minimize2 /> : <Maximize2 />}
          </button>
        </div>
      </footer>
    </main>
  );
}
