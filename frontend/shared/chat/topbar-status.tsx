"use client";

/*
 * My status in the top bar of every app (owner request 2026-11-15: "availability status
 * petukovadaniki top bar lo unte best"). The same status as Chat and the dashboard's
 * Availability panel; a change here tells them at once (window event "adverse-status").
 */
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Check, ChevronDown } from "lucide-react";
import { STATUS_LABELS, chatApi, jsonBody, type ChatPerson, type ChatStatus } from "./chat-types";
import "../styles/availability.css";

export const STATUS_EVENT = "adverse-status";

export const STATUS_MEANING: Record<ChatStatus, string> = {
  AVAILABLE: "Free to talk or take work now",
  BUSY: "Working on something; replies later",
  AWAY: "Not at the desk right now",
  OFFLINE: "Does not have the app open",
};

/** Tell the other status pickers on this page that mine changed. */
export function announceStatus(status: ChatStatus): void {
  window.dispatchEvent(new CustomEvent<ChatStatus>(STATUS_EVENT, { detail: status }));
}

export function TopbarStatus() {
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const root = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    const people = await chatApi<{ me: ChatPerson }>("/people").catch(() => null);
    if (people) setStatus(people.me.status === "OFFLINE" ? "AVAILABLE" : people.me.status);
  }, []);

  useEffect(() => {
    const first = window.setTimeout(() => void load(), 0);
    const changed = (event: Event) => setStatus((event as CustomEvent<ChatStatus>).detail);
    window.addEventListener(STATUS_EVENT, changed);
    window.addEventListener("focus", load);
    return () => {
      window.clearTimeout(first);
      window.removeEventListener(STATUS_EVENT, changed);
      window.removeEventListener("focus", load);
    };
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => !root.current?.contains(event.target as Node) && setOpen(false);
    const key = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", key);
    };
  }, [open]);

  async function choose(next: ChatStatus) {
    setOpen(false);
    if (next === status) return;
    const before = status;
    setStatus(next);
    setError("");
    try {
      await chatApi("/status", jsonBody("PUT", { status: next }));
      announceStatus(next);
    } catch (reason) {
      setStatus(before);
      setError(reason instanceof Error ? reason.message : "Could not change your status.");
    }
  }

  const current = status ?? "AVAILABLE";
  return (
    <div className="topbar-status" ref={root}>
      <button
        type="button"
        className="topbar-status-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Your status: ${STATUS_LABELS[current]}. Change status`}
        title={error || `Your status: ${STATUS_LABELS[current]} · ${STATUS_MEANING[current].toLowerCase()}`}
        disabled={status === null}
        onClick={() => setOpen((value) => !value)}
      >
        <i className={`availability-dot ${current.toLowerCase()}`} aria-hidden="true" />
        <span>{STATUS_LABELS[current]}</span>
        <ChevronDown aria-hidden="true" />
      </button>
      {open && (
        <div className="topbar-status-menu" role="menu" aria-label="Set your status">
          <p>
            Your status
            <small>Everyone you work with sees it, here and in Chat.</small>
          </p>
          {(["AVAILABLE", "BUSY", "AWAY"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="menuitemradio"
              aria-checked={current === value}
              className={current === value ? "active" : undefined}
              onClick={() => void choose(value)}
            >
              <i className={`availability-dot ${value.toLowerCase()}`} aria-hidden="true" />
              <span>
                <b>{STATUS_LABELS[value]}</b>
                <small>{STATUS_MEANING[value]}</small>
              </span>
              {current === value && <Check aria-hidden="true" />}
            </button>
          ))}
          <Link href="/dashboard" className="topbar-status-link" onClick={() => setOpen(false)}>
            See who&apos;s available
          </Link>
        </div>
      )}
    </div>
  );
}
