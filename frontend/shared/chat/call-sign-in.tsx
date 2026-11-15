/*
 * A meet link opened without being signed in to this app (owner decision 2026-11-14: only people
 * with an account in the company can join). Each role has its own app, so the link may have come
 * from another role's app: offer to sign in here, or to open the same link in the right app.
 */
import { ArrowRight, Video } from "lucide-react";
import "../styles/call.css";

type App = "admin" | "manager" | "employee" | "client";

const APPS: { key: App; label: string; url: string }[] = [
  { key: "admin", label: "Admin", url: process.env.NEXT_PUBLIC_ADMIN_APP_URL ?? "http://localhost:3000" },
  { key: "manager", label: "Manager", url: process.env.NEXT_PUBLIC_MANAGER_APP_URL ?? "http://localhost:3001" },
  { key: "employee", label: "Employee", url: process.env.NEXT_PUBLIC_EMPLOYEE_APP_URL ?? "http://localhost:3002" },
  { key: "client", label: "Client", url: process.env.NEXT_PUBLIC_CLIENT_APP_URL ?? "http://localhost:3003" },
];

export function CallSignIn({ code, app, kind }: { code: string; app: App; kind?: string }) {
  const safe = /^[a-z-]{3,16}$/i.test(code) ? code.toLowerCase() : "";
  const path = `/call/${safe}${kind === "AUDIO" || kind === "VIDEO" ? `?kind=${kind}` : ""}`;
  const here = APPS.find((item) => item.key === app);
  return (
    <main className="callroom center">
      <span className="callroom-avatar lg" aria-hidden="true">
        <Video />
      </span>
      <h1>Sign in to join this call</h1>
      <p className="muted">Only people with an account in this company can join.</p>
      <div className="callroom-row">
        <a className="callroom-button primary" href={`/login?next=${encodeURIComponent(path)}`}>
          Sign in as {here?.label ?? "user"} <ArrowRight />
        </a>
      </div>
      <p className="muted small">
        Not a{app === "admin" || app === "employee" ? "n" : ""} {here?.label}? Open the link in your app:
      </p>
      <div className="callroom-row">
        {APPS.filter((item) => item.key !== app).map((item) => (
          <a key={item.key} className="callroom-button" href={`${item.url}${path}`}>
            {item.label}
          </a>
        ))}
      </div>
    </main>
  );
}
