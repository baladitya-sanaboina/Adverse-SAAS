// Copy of frontend/shared/onboarding/onboarding-page.tsx (the Client app has no shared alias). Keep in sync.
"use client";

/*
 * The private onboarding link. No sign-in: the long random token in the link is the key.
 * Owner requests 2026-11-15 and 2026-11-27: a new client, employee or manager opens it from the
 * onboarding mail and goes through it one step at a time (the owner's design in
 * "Onboarding UI/manager-onboarding.html"): read the documents, add their details (employees and
 * managers also a photo and, if they like, ID proof and bank details), set their password, and
 * accept. Accepting keeps the typed name, time and IP; the welcome mail then brings their login.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  AtSign,
  Check,
  Clock3,
  Download,
  Eye,
  EyeOff,
  FileText,
  IdCard,
  KeyRound,
  Lock,
  PenLine,
  Upload,
  UserRound,
} from "lucide-react";
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
type UploadSlot = {
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
  uploads?: UploadSlot[];
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
type StepId = "docs" | "details" | "uploads" | "password" | "accept";
type Block = { kind: "heading" | "paragraph" | "list" | "lines"; parts: string[] };

const LIST_ITEM = /^(\d+[.)]|[-•*])\s+(.*)$/;
const SECTION = /^\d+[.)]\s+\S.{0,58}$/;
const PARTY = { CLIENT: "Client", EMPLOYEE: "Employee", MANAGER: "Manager" } as const;
const RULES: [RegExp, string][] = [
  [/.{12,}/, "12+ characters"],
  [/[a-z]/, "lowercase"],
  [/[A-Z]/, "uppercase"],
  [/\d/, "number"],
  [/[^A-Za-z0-9]/, "special character"],
];
const METER = ["var(--bad)", "var(--bad)", "#f59e0b", "#84cc16", "var(--ok)"];
const FONTS =
  "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Poppins:wght@700&display=swap";

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
    <article className="ow-paper">
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

/** The Adverse orbit mark and wordmark from the owner's design. */
function Brand() {
  return (
    <div className="ow-brand" role="img" aria-label="Adverse">
      <svg className="ow-mark" viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r="38" fill="none" stroke="#0876ed" strokeWidth="3.5" />
        <circle cx="50" cy="50" r="25" fill="none" stroke="#0876ed" strokeWidth="3.5" />
        <circle cx="50" cy="50" r="11" fill="#0876ed" />
        <circle cx="50" cy="25" r="5.5" fill="#0876ed" stroke="#fff" strokeWidth="4" paintOrder="stroke" />
        <circle cx="28.4" cy="62.5" r="5.5" fill="#0876ed" stroke="#fff" strokeWidth="4" paintOrder="stroke" />
        <circle cx="79.1" cy="74.4" r="7" fill="#0876ed" stroke="#fff" strokeWidth="4" paintOrder="stroke" />
      </svg>
      <span className="ow-wm">adverse</span>
    </div>
  );
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="ow">
      {/* React hoists this into the head; the owner's design uses these two fonts. */}
      <link rel="stylesheet" href={FONTS} precedence="default" />
      {children}
    </div>
  );
}

function Header({ icon, step, title, sub }: { icon: ReactNode; step?: string; title: string; sub?: ReactNode }) {
  return (
    <div className="ow-card-h">
      <span className="ow-ico">{icon}</span>
      <div>
        {step && <div className="ow-eyebrow">{step}</div>}
        <h2>{title}</h2>
        {sub && <p className="ow-sub">{sub}</p>}
      </div>
    </div>
  );
}

export function OnboardingPage({ token }: { token: string }) {
  const [packet, setPacket] = useState<Packet | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [seen, setSeen] = useState<Set<number>>(() => new Set([0]));
  const [tab, setTab] = useState(0);
  const [current, setCurrent] = useState(0);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState([false, false]);
  const [accept, setAccept] = useState(false);
  const [signature, setSignature] = useState("");
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

  const steps = useMemo(() => {
    if (!packet) return [] as { id: StepId; label: string }[];
    const list: { id: StepId; label: string }[] = [
      { id: "docs", label: "Read documents" },
      { id: "details", label: "Your details" },
    ];
    if (packet.uploads?.length) list.push({ id: "uploads", label: "ID proof & photo" });
    if (packet.needs_password) list.push({ id: "password", label: "Set password" });
    list.push({ id: "accept", label: "Accept & finish" });
    return list;
  }, [packet]);

  if (error) {
    return (
      <Shell>
        <div className="ow-shell single">
          <main className="ow-main">
            <Brand />
            <section className="ow-card ow-done">
              <div className="ow-big warn">
                <FileText />
              </div>
              <h2>This link can&apos;t be opened</h2>
              <p>{error} If you need the documents again, please contact the person who sent them.</p>
            </section>
          </main>
        </div>
      </Shell>
    );
  }

  if (!packet) {
    return (
      <Shell>
        <div className="ow-shell single">
          <main className="ow-main">
            <section className="ow-card ow-done">
              <OrbitLoader size={72} label="Opening your documents" />
            </section>
          </main>
        </div>
      </Shell>
    );
  }

  const first = packet.recipient_name.split(" ")[0];
  const documents = packet.documents;
  const uploads = packet.uploads ?? [];
  const pdf = `${base}/pdf`;
  const met = RULES.map(([rule]) => rule.test(password));
  const strength = met.filter(Boolean).length;
  const level = strength === 5 ? 4 : strength >= 4 ? 3 : strength >= 2 ? 2 : strength >= 1 ? 1 : 0;
  const ok: Record<StepId, boolean> = {
    docs: documents.every((_, index) => seen.has(index)),
    details: packet.form.every((field) => !field.required || (form[field.key] ?? "").trim()),
    uploads: uploads.every((item) => !item.required || item.uploaded_name),
    password: strength === 5 && password === confirm,
    accept: accept && signature.trim().length >= 2,
  };
  const waiting: Record<StepId, string> = {
    docs: `Open and read all ${documents.length} documents to continue.`,
    details: "Fill in all required fields to continue.",
    uploads: "Upload the required files to continue.",
    password: "Set a strong password and confirm it to continue.",
    accept: "",
  };
  const todo: Record<StepId, string> = {
    docs: `read all ${documents.length} documents`,
    details: "fill your details",
    uploads: "upload your photo",
    password: "set a strong password",
    accept: "accept and sign",
  };
  const doneCount = steps.filter((step) => ok[step.id]).length;
  const percent = steps.length ? Math.round((doneCount / steps.length) * 100) : 0;
  const allOk = steps.every((step) => ok[step.id]);
  const step = steps[Math.min(current, steps.length - 1)];
  const finished = packet.status === "COMPLETED";
  const expired = packet.status === "EXPIRED";

  function show(index: number) {
    setCurrent(index);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function jump(index: number) {
    if (steps.slice(0, index).every((item) => ok[item.id])) show(index);
  }

  function openTab(index: number) {
    setTab(index);
    setSeen((previous) => new Set(previous).add(index));
  }

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
    if (!packet || !allOk || busy) return;
    setProblem("");
    setBusy(true);
    const response = await fetch(base, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        form,
        signed_name: signature.trim(),
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

  const nav = (index: number) => (
    <>
      <div className="ow-nav">
        {index > 0 && (
          <button type="button" className="ow-nb back" onClick={() => show(index - 1)}>
            <ArrowLeft /> Back
          </button>
        )}
        {index < steps.length - 1 && (
          <button type="button" className="ow-nb next" disabled={!ok[steps[index].id]} onClick={() => show(index + 1)}>
            Continue <ArrowRight />
          </button>
        )}
      </div>
      {index < steps.length - 1 && <p className="ow-nhint">{ok[steps[index].id] ? "" : waiting[steps[index].id]}</p>}
    </>
  );

  const label = (index: number) => `Step ${index + 1}`;

  return (
    <Shell>
      <div className="ow-shell">
        <aside className="ow-rail">
          <Brand />
          <div className="ow-hello">
            <h1>Welcome aboard, {first} 👋</h1>
            <p>One step at a time. It only takes a few minutes.</p>
          </div>
          {!finished && !expired && (
            <>
              <div className="ow-sticky">
                <div className="ow-prog">
                  <div className="ow-prog-top">
                    <span>
                      Step {Math.min(current, steps.length - 1) + 1} of {steps.length}
                    </span>
                    <span>{percent}%</span>
                  </div>
                  <div className="ow-bar">
                    <i style={{ width: `${percent}%` }} />
                  </div>
                </div>
              </div>
              <ol className="ow-steps">
                {steps.map((item, index) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`${ok[item.id] ? "done" : ""} ${index === current ? "active" : ""}`}
                      onClick={() => jump(index)}
                    >
                      <span className="ow-n">{ok[item.id] ? <Check /> : <b>{index + 1}</b>}</span>
                      {item.label}
                    </button>
                  </li>
                ))}
              </ol>
              <div className="ow-expiry">
                <Clock3 />
                <span>
                  This private link works until <b>{when(packet.expires_at)}</b>.
                </span>
              </div>
            </>
          )}
        </aside>

        <main className="ow-main">
          {finished ? (
            <section className="ow-card ow-done">
              <div className="ow-big">
                <Check />
              </div>
              <h2>You&apos;re all set, {first}!</h2>
              <p>
                {packet.username
                  ? "Your onboarding is complete. Sign in with your username and the password you just created."
                  : "Your onboarding is complete. A signed copy was sent to your email."}
              </p>
              {packet.username && (
                <Link className="ow-btn" href="/login">
                  Sign in <ArrowRight />
                </Link>
              )}
              <a className="ow-dl" href={pdf} target="_blank" rel="noopener noreferrer">
                <Download /> Signed documents (PDF)
              </a>
            </section>
          ) : expired ? (
            <section className="ow-card ow-done">
              <div className="ow-big warn">
                <Clock3 />
              </div>
              <h2>This link has expired</h2>
              <p>Please ask {packet.company_name} to send your onboarding again.</p>
            </section>
          ) : (
            <form className="ow-main" onSubmit={(event) => void submit(event)} noValidate>
              {step.id === "docs" && (
                <section className="ow-card">
                  <Header
                    icon={<FileText />}
                    step={label(current)}
                    title="Read your documents"
                    sub="Open each tab and read it through. A tick appears once you've viewed it."
                  />
                  <div className="ow-tabs" role="tablist">
                    {documents.map((doc, index) => (
                      <button
                        key={doc.kind}
                        type="button"
                        role="tab"
                        aria-selected={tab === index}
                        className={`ow-tab${tab === index ? " on" : ""}`}
                        onClick={() => openTab(index)}
                      >
                        {seen.has(index) && <Check className="ow-tick" />}
                        {doc.label}
                      </button>
                    ))}
                  </div>
                  {documents[tab] && <DocumentPaper doc={documents[tab]} packet={packet} />}
                  <a className="ow-dl" href={pdf} target="_blank" rel="noopener noreferrer">
                    <Download /> Download all as PDF
                  </a>
                  {nav(current)}
                </section>
              )}

              {step.id === "details" && (
                <section className="ow-card">
                  <Header
                    icon={<UserRound />}
                    step={label(current)}
                    title={packet.audience === "CLIENT" ? "About your brand" : "Your details"}
                    sub={
                      <>
                        Fields marked <em>*</em> are required.
                      </>
                    }
                  />
                  {packet.intro && (
                    <p className="ow-sub" style={{ marginBottom: 16 }}>
                      {packet.intro}
                    </p>
                  )}
                  {groups(packet.form).map(([group, fields]) => (
                    <div key={group || "fields"} className="ow-group">
                      {group && <h3>{group}</h3>}
                      <div className="ow-grid">
                        {fields.map((field) => {
                          const value = form[field.key] ?? "";
                          const change = (text: string) => setForm((previous) => ({ ...previous, [field.key]: text }));
                          return (
                            <label key={field.key} className={`ow-fld${field.multiline ? " ow-wide" : ""}`}>
                              <span>
                                {field.label} {field.required ? <em className="req">*</em> : <small>(optional)</small>}
                              </span>
                              {field.multiline ? (
                                <textarea
                                  rows={3}
                                  value={value}
                                  placeholder={field.placeholder}
                                  onChange={(event) => change(event.target.value)}
                                />
                              ) : (
                                <input
                                  type={field.input ?? "text"}
                                  value={value}
                                  placeholder={field.placeholder}
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
                  {nav(current)}
                </section>
              )}

              {step.id === "uploads" && (
                <section className="ow-card">
                  <Header
                    icon={<IdCard />}
                    step={label(current)}
                    title="ID proof and photo"
                    sub="PDF, JPG or PNG, up to 5 MB each."
                  />
                  <p className="ow-note">
                    <Lock /> Only the admin can see these files.
                  </p>
                  <div className="ow-ups">
                    {uploads.map((item) => (
                      <label key={item.key} className={`ow-up${item.uploaded_name ? " has" : ""}`}>
                        <span className="ow-ui">{item.uploaded_name ? <Check /> : <Upload />}</span>
                        <span className="ow-tx">
                          <strong>
                            {item.label} {item.required ? <em className="req">*</em> : <small>(optional)</small>}
                          </strong>
                          <small>{uploading === item.key ? "Uploading…" : (item.uploaded_name ?? item.hint)}</small>
                        </span>
                        <span className="ow-btn-s">{item.uploaded_name ? "Change" : "Upload"}</span>
                        <input
                          type="file"
                          accept={item.accept}
                          disabled={Boolean(uploading)}
                          onChange={(event) => void upload(item.key, event)}
                        />
                      </label>
                    ))}
                  </div>
                  {uploadProblem && <p className="ow-mm">{uploadProblem}</p>}
                  {nav(current)}
                </section>
              )}

              {step.id === "password" && (
                <section className="ow-card">
                  <Header
                    icon={<KeyRound />}
                    step={label(current)}
                    title="Set your password"
                    sub="You'll sign in to Adverse with this username and password."
                  />
                  <div className="ow-user">
                    <AtSign />
                    <span>
                      <small>Your username</small>
                      <strong>{packet.username}</strong>
                    </span>
                  </div>
                  <div className="ow-grid">
                    {[
                      ["Password", password, setPassword],
                      ["Confirm password", confirm, setConfirm],
                    ].map(([name, value, set], index) => (
                      <label key={name as string} className="ow-fld">
                        <span>
                          {name as string} <em className="req">*</em>
                        </span>
                        <div className="ow-pw">
                          <input
                            type={showPassword[index] ? "text" : "password"}
                            value={value as string}
                            autoComplete="new-password"
                            onChange={(event) => (set as (text: string) => void)(event.target.value)}
                          />
                          <button
                            type="button"
                            className="ow-eye"
                            aria-label={showPassword[index] ? "Hide password" : "Show password"}
                            onClick={() =>
                              setShowPassword((previous) =>
                                previous.map((shown, at) => (at === index ? !shown : shown)),
                              )
                            }
                          >
                            {showPassword[index] ? <EyeOff /> : <Eye />}
                          </button>
                        </div>
                      </label>
                    ))}
                  </div>
                  <div className="ow-meter">
                    {[0, 1, 2, 3].map((index) => (
                      <i key={index} style={index < level ? { background: METER[level] } : undefined} />
                    ))}
                  </div>
                  <ul className="ow-rules">
                    {RULES.map(([, text], index) => (
                      <li key={text} className={met[index] ? "met" : ""}>
                        {text}
                      </li>
                    ))}
                  </ul>
                  <p className="ow-mm">{confirm && password !== confirm ? "Passwords don’t match yet." : ""}</p>
                  {nav(current)}
                </section>
              )}

              {step.id === "accept" && (
                <section className="ow-card">
                  <Header
                    icon={<PenLine />}
                    step={label(current)}
                    title="Accept and finish"
                    sub="Your typed name acts as your signature."
                  />
                  <label className="ow-chk">
                    <input type="checkbox" checked={accept} onChange={(event) => setAccept(event.target.checked)} />
                    <span>I have read these documents and rules and I accept them.</span>
                  </label>
                  <label className="ow-fld">
                    <span>
                      Type your full name as your signature <em className="req">*</em>
                    </span>
                    <input
                      type="text"
                      className="ow-sig"
                      value={signature}
                      placeholder={packet.recipient_name}
                      minLength={2}
                      maxLength={160}
                      autoComplete="off"
                      onChange={(event) => setSignature(event.target.value)}
                    />
                  </label>
                  <button type="submit" className="ow-btn" disabled={!allOk || busy}>
                    <Check /> {busy ? "Saving…" : "Accept and finish"}
                  </button>
                  {problem ? (
                    <p className="ow-mm" role="alert" style={{ textAlign: "center" }}>
                      {problem}
                    </p>
                  ) : (
                    !allOk && (
                      <p className="ow-hint">
                        Still to do:{" "}
                        {steps
                          .filter((item) => !ok[item.id])
                          .map((item) => todo[item.id])
                          .join(", ")}
                        .
                      </p>
                    )
                  )}
                  <p className="ow-fine">
                    We keep your typed name, the time and your IP address as the record of your acceptance.
                  </p>
                  {nav(current)}
                </section>
              )}
            </form>
          )}
        </main>
      </div>
    </Shell>
  );
}
