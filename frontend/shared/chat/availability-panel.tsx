"use client";

/*
 * Availability on every dashboard (owner request 2026-11-15: "available ... anni role frontends lo
 * home page lo ... available ga unnaru ani cheppadaniki"). The same status as in Chat: set your
 * own (Available / Busy / Away) and see who is around, with what each status means.
 * Offline means the person does not have the app open. Who is listed comes from /chat/people,
 * which the server already limits per role (a client sees the admins only).
 */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, MessageCircle, UsersRound } from "lucide-react";
import { STATUS_LABELS, chatApi, initials, jsonBody, type ChatPerson, type ChatStatus } from "./chat-types";
import "../styles/availability.css";

type People = { me: ChatPerson; people: ChatPerson[] };

const MEANING: Record<ChatStatus, string> = {
  AVAILABLE: "Free to talk or take work now",
  BUSY: "Working on something; replies later",
  AWAY: "Not at the desk right now",
  OFFLINE: "Does not have the app open",
};
const ORDER: Record<ChatStatus, number> = { AVAILABLE: 0, BUSY: 1, AWAY: 2, OFFLINE: 3 };
const ROLE: Record<ChatPerson["role"], string> = {
  ADMIN: "Admin",
  MANAGER: "Manager",
  EMPLOYEE: "Employee",
  CLIENT: "Client",
};
const SHOWN = 8;

function Face({ person }: { person: ChatPerson }) {
  return (
    <span className="availability-face">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {person.image ? <img src={person.image} alt="" /> : initials(person.name)}
      <i className={`availability-dot ${person.status.toLowerCase()}`} aria-hidden="true" />
    </span>
  );
}

export function AvailabilityPanel() {
  const router = useRouter();
  const [data, setData] = useState<People | null>(null);
  const [error, setError] = useState("");
  const [all, setAll] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await chatApi<People>("/people"));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load who is available.");
    }
  }, []);

  // Statuses change without events (people open and close the app): refresh now and then.
  useEffect(() => {
    const first = window.setTimeout(() => void load(), 0);
    const poll = window.setInterval(() => void load(), 30_000);
    const focus = () => void load();
    window.addEventListener("focus", focus);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(poll);
      window.removeEventListener("focus", focus);
    };
  }, [load]);

  async function setStatus(status: ChatStatus) {
    if (!data || data.me.status === status) return;
    const before = data;
    setData({ ...data, me: { ...data.me, status } });
    try {
      setData(await chatApi<People>("/status", jsonBody("PUT", { status })));
    } catch (reason) {
      setData(before);
      setError(reason instanceof Error ? reason.message : "Could not change your status.");
    }
  }

  async function message(person: ChatPerson) {
    setBusyId(person.id);
    try {
      const chat = await chatApi<{ id: string }>("/direct", jsonBody("POST", { user_id: person.id }));
      router.push(`/chat?c=${chat.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not open the chat.");
      setBusyId(null);
    }
  }

  const people = [...(data?.people ?? [])].sort(
    (a, b) => ORDER[a.status] - ORDER[b.status] || a.name.localeCompare(b.name),
  );
  const team = people.filter((person) => person.role !== "CLIENT");
  const clients = people.filter((person) => person.role === "CLIENT");
  const free = people.filter((person) => person.status === "AVAILABLE").length;
  const mine: ChatStatus = data && data.me.status !== "OFFLINE" ? data.me.status : "AVAILABLE";
  const onlyAdmins = data !== null && people.length > 0 && people.every((person) => person.role === "ADMIN");

  const list = (rows: ChatPerson[], label?: string) => {
    const visible = all ? rows : rows.slice(0, SHOWN);
    return (
      <>
        {label && rows.length > 0 && <h3 className="availability-group">{label}</h3>}
        <ul className="availability-people">
          {visible.map((person) => (
            <li key={person.id}>
              <Face person={person} />
              <div>
                <strong>{person.name}</strong>
                <small>
                  {ROLE[person.role]} · <em className={person.status.toLowerCase()}>{STATUS_LABELS[person.status]}</em>
                </small>
              </div>
              <button
                type="button"
                className="availability-message"
                aria-label={`Message ${person.name}`}
                title={`Message ${person.name}`}
                disabled={busyId === person.id}
                onClick={() => void message(person)}
              >
                <MessageCircle />
              </button>
            </li>
          ))}
        </ul>
      </>
    );
  };

  return (
    <article className="company-dashboard-panel production-dash-panel availability-panel">
      <header>
        <div>
          <span>AVAILABILITY</span>
          <h2>{!data ? "Who's around" : free === 0 ? "No one is available right now" : `${free} available now`}</h2>
        </div>
      </header>
      <div className="production-dash-panel-body availability-body">
        <section className="availability-me" aria-label="Your status">
          <p className="availability-label">
            Your status
            <small>Shown to everyone you work with, here and in Chat.</small>
          </p>
          <div className="availability-choices" role="radiogroup" aria-label="Your status">
            {(["AVAILABLE", "BUSY", "AWAY"] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mine === value}
                className={mine === value ? "active" : undefined}
                disabled={!data}
                onClick={() => void setStatus(value)}
              >
                <i className={`availability-dot ${value.toLowerCase()}`} aria-hidden="true" />
                <b>{STATUS_LABELS[value]}</b>
                <small>{MEANING[value]}</small>
                {mine === value && <Check className="availability-tick" aria-hidden="true" />}
              </button>
            ))}
          </div>
        </section>

        <section className="availability-list" aria-label={onlyAdmins ? "Your team" : "People"}>
          {error && <p className="availability-error">{error}</p>}
          {!data && !error ? (
            <p className="production-dash-empty">Loading…</p>
          ) : people.length === 0 ? (
            <p className="production-dash-empty">
              <UsersRound aria-hidden="true" />
              No one else here yet.
            </p>
          ) : clients.length > 0 && team.length > 0 ? (
            <>
              {list(team, "Team")}
              {list(clients, "Clients")}
            </>
          ) : (
            list(people, onlyAdmins ? "Your team at the agency" : undefined)
          )}
          {(team.length > SHOWN || clients.length > SHOWN) && (
            <button type="button" className="production-dash-link availability-more" onClick={() => setAll((v) => !v)}>
              {all ? "Show fewer" : `Show all ${people.length}`}
            </button>
          )}
        </section>

        <ul className="availability-legend" aria-label="What the statuses mean">
          {(["AVAILABLE", "BUSY", "AWAY", "OFFLINE"] as const).map((value) => (
            <li key={value}>
              <i className={`availability-dot ${value.toLowerCase()}`} aria-hidden="true" />
              <b>{STATUS_LABELS[value]}</b> {MEANING[value].toLowerCase()}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}
