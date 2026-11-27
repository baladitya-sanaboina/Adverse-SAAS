// Copy of frontend/shared/onboarding/onboarding-page.tsx (the Client app has no shared alias). Keep in sync.
"use client";

/*
 * The private onboarding link. No sign-in: the long random token in the link is the key.
 * Owner requests 2026-11-15 and 2026-11-27: a new client, employee or manager opens it from the
 * onboarding mail, reads the documents and rules, fills in the form (employees and managers:
 * personal details, ID proof, bank details and a photo), sets their password, and accepts.
 * Accepting keeps the typed name, time and IP; the welcome mail then brings their login.
 */
import Link from "next/link";
import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { CheckCircle2, Clock3, Download, FileText, KeyRound, LogIn, ShieldCheck, Upload } from "lucide-react";
import { OrbitLoader } from "@/components/loader/orbit-loader";
import "@/styles/onboarding.css";

type Field = {
  key: string;
  label: string;
  required: boolean;
  multiline: boolean;
  placeholder: string;
  group?: string;
  input?: "text" | "date" | "tel" | "email";
};
type Upload = {
  key: string;
  label: string;
  required: boolean;
  accept: string;
  hint: string;
  uploaded_name: string | null;
};
type Doc = { kind: string; label: string; signable: boolean; title: string; body: string };
type Packet = {
  company_name: string;
  company_email?: string;
  company_phone?: string;
  audience: "CLIENT" | "EMPLOYEE" | "MANAGER";
  username?: string | null;
  needs_password?: boolean;
  uploads?: Upload[];
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
const PARTY = { CLIENT: "Client", EMPLOYEE: "Employee", MANAGER: "Manager" } as const;
const PASSWORD_RULES: [RegExp, string][] = [
  [/.{12,}/, "12 or more characters"],
  [/[a-z]/, "a lowercase letter"],
  [/[A-Z]/, "an uppercase letter"],
  [/\d/, "a number"],
  [/[^A-Za-z0-9]/, "a special character"],
];

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
  const party = PARTY[packet.audience] ?? "Employee";
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

function problemText(body: { detail?: unknown }, fallback: string): string {
  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  return fallback;
}

/** Fields in their groups ("Personal details", "Bank details"), in order. */
function groups(fields: Field[]): [string, Field[]][] {
  const out: [string, Field[]][] = [];
  for (const field of fields) {
    const name = field.group ?? "";
    const last = out[out.length - 1];
    if (last && last[0] === name) last[1].push(field);
    else out.push([name, [field]]);
  }
  return out;
}

export function OnboardingPage({ token }: { token: string }) {
  const [packet, setPacket] = useState<Packet | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [accept, setAccept] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState("");
  const [problem, setProblem] = useState("");
  const [uploadProblem, setUploadProblem] = useState("");
  const base = `/api/public/onboarding/${encodeURIComponent(token)}`;

  const load = useCallback(async () => {
    const response = await fetch(base, { cache: "no-store" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(typeof body.detail === "string" ? body.detail : "This link is not valid.");
      return;
    }
    setPacket(body as Packet);
  }, [base]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function upload(key: string, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploadProblem("");
    if (file.size > 5 * 1024 * 1024) return setUploadProblem(`${file.name} is larger than 5 MB.`);
    setUploading(key);
    const data = new FormData();
    data.append("file", file);
    const response = await fetch(`${base}/files/${key}`, { method: "POST", body: data });
    const body = await response.json().catch(() => ({}));
    setUploading("");
    if (!response.ok) return setUploadProblem(problemText(body, "The file could not be uploaded."));
    setPacket(body as Packet);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem("");
    if (!packet) return;
    const missing = (packet.uploads ?? []).filter((item) => item.required && !item.uploaded_name);
    if (missing.length) return setProblem(`Please upload: ${missing.map((item) => item.label).join(", ")}.`);
    if (packet.needs_password) {
      const unmet = PASSWORD_RULES.filter(([rule]) => !rule.test(password)).map(([, text]) => text);
      if (unmet.length) return setProblem(`Your password needs ${unmet.join(", ")}.`);
      if (password !== confirm) return setProblem("The two passwords do not match.");
    }
    if (!accept) return setProblem("Tick the box to accept the documents.");
    setBusy(true);
    const response = await fetch(base, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        form,
        signed_name: name.trim(),
        accept,
        ...(packet.needs_password ? { password, confirm_password: confirm } : {}),
      }),
    });
    const body = await response.json().catch(() => ({}));
    setBusy(false);
    if (!response.ok) return setProblem(problemText(body, "That did not work. Please try again."));
    setPassword("");
    setConfirm("");
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
  const open = !done && !expired;
  const signable = packet.documents.filter((doc) => doc.signable);
  const isClient = packet.audience === "CLIENT";
  const uploads = packet.uploads ?? [];
  const activates = Boolean(packet.username);
  const pdf = `${base}/pdf`;
  let step = 0;
  const next = () => `Step ${++step}`;

  return (
    <main className="onb-page">
      <header className="onb-head">
        <span className="onb-brand">{packet.company_name}</span>
        <h1>Let&apos;s get you onboarded, {packet.recipient_name.split(" ")[0]}</h1>
        <p>
          {isClient
            ? "Read our service agreement, tell us about your brand and set your password. It takes about five minutes."
            : "Read your documents and our rules, add your details and set your password to finish onboarding."}
        </p>
      </header>

      {done ? (
        <section className="onb-card onb-done">
          <CheckCircle2 aria-hidden="true" />
          <div>
            <h2>Onboarding complete, thank you</h2>
            <p>
              Accepted by <strong>{packet.signed_name}</strong>
              {packet.signed_at ? ` on ${when(packet.signed_at)}` : ""}.{" "}
              {activates
                ? "Your account is ready; your login details and signed documents were sent to your email."
                : "A signed copy was sent to your email."}
            </p>
          </div>
          <div className="onb-done-actions">
            {activates && (
              <Link className="onb-button" href="/login">
                <LogIn aria-hidden="true" /> Sign in
              </Link>
            )}
            <a className="onb-link" href={pdf} target="_blank" rel="noopener noreferrer">
              <Download aria-hidden="true" /> Signed copy (PDF)
            </a>
          </div>
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
          <span className="onb-step">{next()}</span>
          <h2>{isClient ? "Read the agreement" : "Read your documents and our rules"}</h2>
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

        <section className="onb-card">
          <span className="onb-step">{next()}</span>
          <h2>{isClient ? "About your brand" : "Your details"}</h2>
          {packet.intro && <p className="onb-muted">{packet.intro}</p>}
          {groups(packet.form).map(([group, fields]) => (
            <div key={group || "fields"} className="onb-group">
              {group && <h3>{group}</h3>}
              <div className="onb-fields">
                {fields.map((field) => {
                  const value = done ? (packet.form_data[field.key] ?? "") : (form[field.key] ?? "");
                  const change = (text: string) => setForm((current) => ({ ...current, [field.key]: text }));
                  return (
                    <label key={field.key} className={`onb-field${field.multiline ? " wide" : ""}`}>
                      <span>
                        {field.label}
                        {field.required ? <em aria-hidden="true"> *</em> : <small> (optional)</small>}
                      </span>
                      {field.multiline ? (
                        <textarea
                          rows={3}
                          value={value}
                          placeholder={field.placeholder}
                          required={field.required}
                          disabled={!open}
                          onChange={(event) => change(event.target.value)}
                        />
                      ) : (
                        <input
                          type={field.input ?? "text"}
                          value={value}
                          placeholder={field.placeholder}
                          required={field.required}
                          disabled={!open}
                          autoComplete="off"
                          onChange={(event) => change(event.target.value)}
                        />
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
        </section>

        {uploads.length > 0 && (
          <section className="onb-card">
            <span className="onb-step">{next()}</span>
            <h2>ID proof and photo</h2>
            <p className="onb-muted">PDF, JPG or PNG, up to 5 MB each. Only the admin can see these files.</p>
            <div className="onb-uploads">
              {uploads.map((item) => (
                <div key={item.key} className={`onb-upload${item.uploaded_name ? " done" : ""}`}>
                  <span>
                    <strong>
                      {item.label}
                      {item.required && <em aria-hidden="true"> *</em>}
                    </strong>
                    <small>{item.uploaded_name ? `Uploaded: ${item.uploaded_name}` : item.hint}</small>
                  </span>
                  {open && (
                    <label className="onb-upload-button">
                      <input
                        type="file"
                        accept={item.accept}
                        disabled={Boolean(uploading)}
                        onChange={(event) => void upload(item.key, event)}
                      />
                      {item.uploaded_name ? <CheckCircle2 aria-hidden="true" /> : <Upload aria-hidden="true" />}
                      {uploading === item.key ? "Uploading…" : item.uploaded_name ? "Replace" : "Upload"}
                    </label>
                  )}
                </div>
              ))}
            </div>
            {uploadProblem && (
              <p className="onb-problem" role="alert">
                {uploadProblem}
              </p>
            )}
          </section>
        )}

        {open && packet.needs_password && (
          <section className="onb-card">
            <span className="onb-step">{next()}</span>
            <h2>Set your password</h2>
            <p className="onb-muted">You will sign in to Adverse with this username and the password you set here.</p>
            <div className="onb-username">
              <KeyRound aria-hidden="true" />
              <span>
                <small>Your username</small>
                <strong>{packet.username}</strong>
              </span>
            </div>
            <div className="onb-fields">
              <label className="onb-field">
                <span>
                  Password<em aria-hidden="true"> *</em>
                </span>
                <input
                  type="password"
                  value={password}
                  required
                  autoComplete="new-password"
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <label className="onb-field">
                <span>
                  Confirm password<em aria-hidden="true"> *</em>
                </span>
                <input
                  type="password"
                  value={confirm}
                  required
                  autoComplete="new-password"
                  onChange={(event) => setConfirm(event.target.value)}
                />
              </label>
            </div>
            <ul className="onb-rules">
              {PASSWORD_RULES.map(([rule, text]) => (
                <li key={text} className={rule.test(password) ? "met" : ""}>
                  {text}
                </li>
              ))}
            </ul>
          </section>
        )}

        {open && (
          <section className="onb-card">
            <span className="onb-step">{next()}</span>
            <h2>Accept and finish</h2>
            <label className="onb-check">
              <input type="checkbox" checked={accept} onChange={(event) => setAccept(event.target.checked)} />
              <span>
                I have read{" "}
                {signable.length === 1 ? `the ${signable[0].label.toLowerCase()}` : "these documents and rules"} and I
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
            <button type="submit" className="onb-button" disabled={busy || Boolean(uploading)}>
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
