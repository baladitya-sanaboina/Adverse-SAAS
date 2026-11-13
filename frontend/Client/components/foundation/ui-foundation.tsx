import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { Bell } from "lucide-react";
import Image from "next/image";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";

export function AppFooter({ role }: { role: string }) {
  return (
    <footer className="app-footer">
      <span>© Adverse</span>
      <span>{role} workspace</span>
    </footer>
  );
}
export function ShellActions({
  role,
  userName,
  profileImageUrl,
}: {
  role: string;
  userName: string;
  profileImageUrl?: string | null;
}) {
  const initials = userName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  return (
    <div className="shell-actions">
      <button type="button" aria-label="Notifications" style={{ display: "grid", placeItems: "center", padding: 0 }}>
        <Bell width={18} height={18} strokeWidth={1.8} style={{ display: "block" }} aria-hidden="true" />
        <i />
      </button>
      <div className="shell-profile" aria-label={`${userName} profile`}>
        <b>
          {profileImageUrl ? (
            <Image
              unoptimized
              width={30}
              height={30}
              style={{ objectFit: "cover", borderRadius: "inherit" }}
              src={`/api/profile/image?path=${encodeURIComponent(profileImageUrl)}`}
              alt=""
            />
          ) : (
            initials
          )}
        </b>
        <span>
          {userName}
          <small>{role}</small>
        </span>
      </div>
    </div>
  );
}
export function FoundationPage({ title }: { title: string }) {
  return (
    <>
      <DashboardHero
        title=""
        highlight={title}
        description="This route is prepared for a future roadmap day. No feature logic or API integration is active."
        compact
      />
      <div className="dash-content">
        <EmptyState
          title={`No ${title.toLowerCase()} data`}
          description="Content will appear when this module is implemented."
        />
      </div>
    </>
  );
}
export function ErrorState({ code, title }: { code: string; title: string }) {
  return (
    <section className="foundation-error">
      <div className="dash-grid" aria-hidden="true" />
      <div className="foundation-error-content">
        <strong>{code}</strong>
        <h1>{title}</h1>
        <p>This UI state is ready for future application handling.</p>
      </div>
    </section>
  );
}
export function UiButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className="ui-button" {...props} />;
}
export function UiInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="ui-input" {...props} />;
}
export function UiCard({ children }: { children: ReactNode }) {
  return <article className="ui-card">{children}</article>;
}
export function UiAlert({ children }: { children: ReactNode }) {
  return (
    <div className="ui-alert" role="status">
      {children}
    </div>
  );
}
export function UiModal({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="ui-modal" role="dialog" aria-modal="true" aria-label={title}>
      <div>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}
export function ButtonLoader() {
  return <span className="ui-button-loader" aria-label="Loading" />;
}
export function CardLoader() {
  return <div className="ui-card-loader" aria-label="Loading card" />;
}
export function TableLoader() {
  return (
    <div className="ui-table-loader" aria-label="Loading table">
      {[1, 2, 3, 4].map((row) => (
        <i key={row} />
      ))}
    </div>
  );
}
export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="ui-empty">
      <b>◇</b>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}
