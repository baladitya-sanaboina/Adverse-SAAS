"use client";
import { Check, ShieldAlert, X } from "lucide-react";
import "@/styles/confirmation-dialog.css";
export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel,
  tone = "primary",
  loading = false,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  tone?: "primary" | "danger";
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div
      className="confirm-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && !loading && onCancel()}
    >
      <section
        className={`confirm-dialog ${tone}`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <button
          className="confirm-dialog-close"
          type="button"
          aria-label="Close confirmation"
          disabled={loading}
          onClick={onCancel}
        >
          <X />
        </button>
        <div className="confirm-dialog-icon">{tone === "danger" ? <ShieldAlert /> : <Check />}</div>
        <span>Confirm action</span>
        <h2 id="confirm-dialog-title">{title}</h2>
        <p>{description}</p>
        <footer>
          <button type="button" disabled={loading} onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="confirm-dialog-submit" disabled={loading} onClick={onConfirm}>
            {loading && <i />}
            {loading ? "Please wait…" : confirmLabel}
          </button>
        </footer>
      </section>
    </div>
  );
}
