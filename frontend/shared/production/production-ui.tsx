import type { ReactNode } from "react";
import { OrbitLoader } from "../branding/orbit-loader";

/** Form field using the shared management-field styles (label, control, inline error or hint). */
export function Field({
  label,
  error,
  wide,
  hint,
  children,
}: {
  label: string;
  error?: string;
  wide?: boolean;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className={`management-field${wide ? " wide" : ""}`}>
      <span>{label}</span>
      {children}
      {error ? <small>{error}</small> : hint ? <span className="production-hint">{hint}</span> : null}
    </label>
  );
}

/** Card with the same header as the management editor (icon, eyebrow, title, description). */
export function Panel({
  icon,
  eyebrow,
  title,
  description,
  children,
}: {
  icon: ReactNode;
  eyebrow: string;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="management-editor production-panel">
      <header>
        <i aria-hidden="true">{icon}</i>
        <div>
          <span>{eyebrow}</span>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

export function TableSkeleton() {
  return (
    <div className="orbit-loader-block">
      <OrbitLoader size={56} />
    </div>
  );
}
