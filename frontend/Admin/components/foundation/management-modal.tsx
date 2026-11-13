import type { ReactNode } from "react";
import { X } from "lucide-react";
import "@/styles/management-surfaces.css";

export function ManagementModal({
  open,
  eyebrow,
  title,
  subtitle,
  icon,
  children,
  footer,
  busy = false,
  onClose,
}: {
  open: boolean;
  eyebrow: string;
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  children: ReactNode;
  footer: ReactNode;
  busy?: boolean;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div
      className="management-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <section className="management-modal" role="dialog" aria-modal="true" aria-labelledby="management-modal-title">
        <header>
          {icon && <i aria-hidden="true">{icon}</i>}
          <div>
            <span>{eyebrow}</span>
            <h2 id="management-modal-title">{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close dialog">
            <X />
          </button>
        </header>
        <div className="management-modal-body">{children}</div>
        <footer>{footer}</footer>
      </section>
    </div>
  );
}
