"use client";

/*
 * The private onboarding link (owner request 2026-11-15): a new client fills a short form and
 * accepts the service agreement; a new employee reads the offer, joining letter and agreement and
 * accepts them. No sign-in: the long random token in the link is the key. Accepting keeps the
 * typed name, time and IP, and the signed copy can be downloaded as a PDF.
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, Clock3, Download, FileText, ShieldCheck } from "lucide-react";
import { OrbitLoader } from "../branding/orbit-loader";
import "../styles/onboarding.css";

type Field = { key: string; label: string; required: boolean; multiline: boolean; placeholder: string };
type Doc = { kind: string; label: string; signable: boolean; title: string; body: string };
type Packet = {
  company_name: string;
  company_email?: string;
  company_phone?: string;
  audience: "CLIENT" | "EMPLOYEE";
  recipient_name: string;
  status: "SENT" | "OPENED" | "COMPLETED" | "CANCELLED" | "EXPIRED";
  expires_at: string;
  intro: string;
  documents: Doc[];
  form: Field[];
  form_data: Record<string, string>;
  signed_name: string | null;
  signed_at: string | null;
};

type Block = { kind: "heading" | "paragraph" | "list" | "lines"; parts: string[] };

const LIST_ITEM = /^(\d+[.)]|[-•*])\s+(.*)$/;
const SECTION = /^\d+[.)]\s+\S.{0,58}$/;

/**
 * A document body as layout blocks (owner request 2026-11-19: documents must read like proper
 * letters). Same rules as document_templates.blocks in the backend, which lays out the PDF.
 */
function documentBlocks(body: string): Block[] {
  const out: Block[] = [];
  const chunks = body
    .trim()
    .split(/\n\s*\n/)
    .filter((chunk) => chunk.trim());
  chunks.forEach((chunk, position) => {
    let lines = chunk
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (position === 0 && lines.length === 1 && lines[0] === lines[0].toUpperCase() && lines[0].length <= 60) return;
    if (lines.length > 1 && SECTION.test(lines[0]) && !LIST_ITEM.test(lines[1])) {
      out.push({ kind: "heading", parts: [lines[0]] });
      lines = lines.slice(1);
    }
    if (lines.length >= 2 && lines.every((line) => line.length <= 45) && !lines.some((line) => LIST_ITEM.test(line))) {
      out.push({ kind: "lines", parts: lines });
      return;
    }
    let paragraph: string[] = [];
    let items: string[] = [];
    const flushParagraph = () => {
      if (paragraph.length) out.push({ kind: "paragraph", parts: [paragraph.join(" ")] });
      paragraph = [];
    };
    const flushItems = () => {
      if (items.length) out.push({ kind: "list", parts: items });
      items = [];
    };
    for (const line of lines) {
      const match = LIST_ITEM.exec(line);
      if (match) {
        flushParagraph();
        items.push(match[2]);
      } else if (items.length) {
        items[items.length - 1] = `${items[items.length - 1]} ${line}`;
      } else {
        paragraph.push(line);
      }
    }
    flushParagraph();
    flushItems();
  });
  return out;
}

/** One document drawn like paper: letterhead, title, sections, and a signature block. */
function DocumentPaper({ doc, packet }: { doc: Doc; packet: Packet }) {
  const party = packet.audience === "CLIENT" ? "Client" : "Employee";
  return (
    <article className="onb-paper">
      <header className="onb-letterhead">
        {/* A plain image: this public page is also printed, and the logo is a small static file. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logos/adverse-logo-blue.png" alt="Adverse" width={132} height={35} />
        <div>
          <strong>{packet.company_name}</strong>
          {packet.company_email && <span>{packet.company_email}</span>}
          {packet.company_phone && <span>{packet.company_phone}</span>}
        </div>
      </header>
      <h3>{doc.title}</h3>
      <p className="onb-paper-meta">
        {doc.label} · Prepared for {packet.recipient_name}
      </p>
      {documentBlocks(doc.body).map((block, index) =>
        block.kind === "heading" ? (
          <h4 key={index}>{block.parts[0]}</h4>
        ) : block.kind === "list" ? (
          <ol key={index}>
            {block.parts.map((item, itemIndex) => (
              <li key={itemIndex}>{item}</li>
            ))}
          </ol>
        ) : block.kind === "lines" ? (
          <p key={index} className="onb-paper-lines">
            {block.parts.join("\n")}
          </p>
        ) : (
          <p key={index}>{block.parts[0]}</p>
        ),
      )}
      {doc.signable && (
        <div className="onb-sign">
          <div>
            <small>For {packet.company_name}</small>
            <strong>{packet.company_name}</strong>
            <span>Authorised signatory</span>
          </div>
          <div>
            <small>{party}</small>
            <strong>{packet.signed_name || packet.recipient_name}</strong>
            <span>
              {packet.signed_at ? `Accepted online on ${when(packet.signed_at)}` : "Accept below to sign online"}
            </span>
          </div>
        </div>
      )}
    </article>
  );
}

function when(value: string): string {
  const date = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function OnboardingPage({ token }: { token: string }) {
  const [packet, setPacket] = useState<Packet | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [accept, setAccept] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const load = useCallback(async () => {
    const response = await fetch(`/api/public/onboarding/${encodeURIComponent(token)}`, { cache: "no-store" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(typeof body.detail === "string" ? body.detail : "This link is not valid.");
      return;
    }
    setPacket(body as Packet);
  }, [token]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem("");
    if (!accept) return setProblem("Tick the box to accept the documents.");
    setBusy(true);
    const response = await fetch(`/api/public/onboarding/${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ form, signed_name: name.trim(), accept }),
    });
    const body = await response.json().catch(() => ({}));
    setBusy(false);
    if (!response.ok) {
      const detail = body.detail;
      setProblem(
        typeof detail === "string"
          ? detail
          : Array.isArray(detail) && detail[0]?.msg
            ? String(detail[0].msg)
            : "That did not work. Please try again.",
      );
      return;
    }
    setPacket(body as Packet);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (error) {
    return (
      <main className="onb-page">
        <section className="onb-card onb-center">
          <FileText aria-hidden="true" />
          <h1>This link can&apos;t be opened</h1>
          <p>{error} If you need the documents again, please contact the person who sent them.</p>
        </section>
      </main>
    );
  }

  if (!packet) {
    return (
      <main className="onb-page">
        <section className="onb-card onb-center">
          <OrbitLoader size={72} label="Opening your documents" />
        </section>
      </main>
    );
  }

  const done = packet.status === "COMPLETED";
  const expired = packet.status === "EXPIRED";
  const signable = packet.documents.filter((doc) => doc.signable);
  const isClient = packet.audience === "CLIENT";
  const pdf = `/api/public/onboarding/${encodeURIComponent(token)}/pdf`;

  return (
    <main className="onb-page">
      <header className="onb-head">
        <span className="onb-brand">{packet.company_name}</span>
        <h1>
          {isClient ? "Welcome aboard" : "Welcome to the team"}, {packet.recipient_name.split(" ")[0]}
        </h1>
        <p>
          {isClient
            ? "A short form and our service agreement. It takes about five minutes."
            : "Your documents are below. Read them, add a few details and accept."}
        </p>
      </header>

      {done ? (
        <section className="onb-card onb-done">
          <CheckCircle2 aria-hidden="true" />
          <div>
            <h2>All done, thank you</h2>
            <p>
              Accepted by <strong>{packet.signed_name}</strong>
              {packet.signed_at ? ` on ${when(packet.signed_at)}` : ""}. A signed copy was sent to your email.
            </p>
          </div>
          <a className="onb-button" href={pdf} target="_blank" rel="noopener noreferrer">
            <Download aria-hidden="true" /> Signed copy (PDF)
          </a>
        </section>
      ) : expired ? (
        <section className="onb-card onb-warn">
          <Clock3 aria-hidden="true" />
          <div>
            <h2>This link has expired</h2>
            <p>Please ask {packet.company_name} to send it again.</p>
          </div>
        </section>
      ) : (
        <p className="onb-expiry">
          <Clock3 aria-hidden="true" /> This private link works until {when(packet.expires_at)}.
        </p>
      )}

      <form className="onb-steps" onSubmit={(event) => void submit(event)}>
        <section className="onb-card">
          <span className="onb-step">Step 1</span>
          <h2>{isClient ? "About your brand" : "Your details"}</h2>
          {packet.intro && <p className="onb-muted">{packet.intro}</p>}
          <div className="onb-fields">
            {packet.form.map((field) => {
              const value = done ? (packet.form_data[field.key] ?? "") : (form[field.key] ?? "");
              return (
                <label key={field.key} className={`onb-field${field.multiline ? " wide" : ""}`}>
                  <span>
                    {field.label}
                    {field.required && <em aria-hidden="true"> *</em>}
                  </span>
                  {field.multiline ? (
                    <textarea
                      rows={3}
                      value={value}
                      placeholder={field.placeholder}
                      required={field.required}
                      disabled={done || expired}
                      onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
                    />
                  ) : (
                    <input
                      value={value}
                      placeholder={field.placeholder}
                      required={field.required}
                      disabled={done || expired}
                      onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
                    />
                  )}
                </label>
              );
            })}
          </div>
        </section>

        <section className="onb-card">
          <span className="onb-step">Step 2</span>
          <h2>Read the documents</h2>
          <div className="onb-docs">
            {packet.documents.map((doc) => (
              <details key={doc.kind} className="onb-doc" open={doc.signable && signable.length === 1}>
                <summary>
                  <FileText aria-hidden="true" />
                  <span>
                    <strong>{doc.label}</strong>
                    <small>{doc.signable ? "To accept" : "For your information"}</small>
                  </span>
                </summary>
                <DocumentPaper doc={doc} packet={packet} />
              </details>
            ))}
          </div>
          <a className="onb-link" href={pdf} target="_blank" rel="noopener noreferrer">
            <Download aria-hidden="true" /> Download as PDF
          </a>
        </section>

        {!done && !expired && (
          <section className="onb-card">
            <span className="onb-step">Step 3</span>
            <h2>Accept</h2>
            <label className="onb-check">
              <input type="checkbox" checked={accept} onChange={(event) => setAccept(event.target.checked)} />
              <span>
                I have read {signable.length === 1 ? `the ${signable[0].label.toLowerCase()}` : "these documents"} and I
                accept {signable.length === 1 ? "it" : "them"}.
              </span>
            </label>
            <label className="onb-field">
              <span>
                Type your full name as your signature<em aria-hidden="true"> *</em>
              </span>
              <input
                className="onb-signature"
                value={name}
                required
                minLength={2}
                maxLength={160}
                placeholder={packet.recipient_name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            {problem && (
              <p className="onb-problem" role="alert">
                {problem}
              </p>
            )}
            <button type="submit" className="onb-button" disabled={busy}>
              <ShieldCheck aria-hidden="true" /> {busy ? "Saving…" : "Accept and finish"}
            </button>
            <p className="onb-muted small">
              We keep your typed name, the time and your IP address as the record of your acceptance.
            </p>
          </section>
        )}
      </form>
    </main>
  );
}
