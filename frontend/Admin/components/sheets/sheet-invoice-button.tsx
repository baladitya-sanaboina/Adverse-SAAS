"use client";

/*
 * Invoices per payment sheet (owner request 2026-11-15): a finished sheet gets a draft by itself;
 * any sheet can also be invoiced by hand here. Once made, the button opens that invoice.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Mail, ReceiptText } from "lucide-react";
import type { Sheet } from "@loopless-shared/production/payment-sheets";
import { api, errorText } from "@/lib/production/client";

export function SheetInvoiceButton({
  sheet,
  clientId,
  onError,
  onDone,
}: {
  sheet: Sheet;
  clientId: string;
  onError?: (message: string) => void;
  onDone?: (message: string) => void;
}) {
  // The old flow, kept on the sheet itself (owner request 2026-11-19): Generate invoice → it
  // becomes a PDF → Send invoice mails the PDF to the client's Gmail and their Adverse mailbox.
  const router = useRouter();
  const [busy, setBusy] = useState<"" | "make" | "send">("");
  const [made, setMade] = useState<{ id: string; code: string; status: string } | null>(null);
  const invoice =
    made ??
    (sheet.invoice_id && sheet.invoice_code
      ? { id: sheet.invoice_id, code: sheet.invoice_code, status: sheet.invoice_status ?? "" }
      : null);

  async function generate() {
    setBusy("make");
    try {
      const created = await api<{ id: string; code: string; status: string }>("/api/company/invoices/sheet", {
        method: "POST",
        json: { client_id: clientId, start: sheet.start, index: sheet.index },
      });
      setMade({ id: created.id, code: created.code, status: created.status });
      onDone?.(`Invoice ${created.code} is ready for sheet ${sheet.index}. View the PDF or send it.`);
    } catch (reason) {
      onError?.(errorText(reason, "Could not make the invoice."));
    } finally {
      setBusy("");
    }
  }

  async function send() {
    if (!invoice) return;
    setBusy("send");
    try {
      const result = await api<{ message: string }>(`/api/company/invoices/${invoice.id}/send`, { method: "POST" });
      setMade({ ...invoice, status: "SENT" });
      onDone?.(`Invoice ${invoice.code}: ${result.message}`);
    } catch (reason) {
      onError?.(errorText(reason, "Could not send the invoice."));
    } finally {
      setBusy("");
    }
  }

  if (!invoice) {
    return (
      <button
        type="button"
        disabled={busy !== "" || sheet.items === 0}
        title={sheet.items === 0 ? "No work on this sheet yet" : "Make the invoice PDF for this sheet"}
        onClick={() => void generate()}
      >
        <ReceiptText aria-hidden="true" /> {busy === "make" ? "Making invoice…" : "Generate invoice"}
      </button>
    );
  }

  const status = invoice.status.toLowerCase();
  const sent = ["sent", "paid", "partially_paid", "overdue"].includes(status);
  return (
    <>
      <button type="button" disabled={busy !== ""} onClick={() => void send()}>
        <Mail aria-hidden="true" /> {busy === "send" ? "Sending…" : sent ? "Send invoice again" : "Send invoice"}
      </button>
      <a className="secondary" href={`/api/company/invoices/${invoice.id}/pdf`} target="_blank" rel="noreferrer">
        <FileText aria-hidden="true" /> {invoice.code} PDF
      </a>
      <button type="button" className="secondary" onClick={() => router.push(`/invoices?invoice=${invoice.id}`)}>
        <ReceiptText aria-hidden="true" /> Open invoice
      </button>
    </>
  );
}

/** "Email statement": the statement goes to their Gmail and their Adverse mailbox (2026-11-19). */
export function SheetEmailButton({
  sheet,
  kind,
  ownerId,
  onDone,
}: {
  sheet: Sheet;
  kind: "MANAGER" | "CLIENT";
  ownerId: string;
  onDone?: (message: string, failed?: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  async function send() {
    setBusy(true);
    try {
      const result = await api<{ message: string }>("/api/company/invoices/sheet-email", {
        method: "POST",
        json: { kind, owner_id: ownerId, index: sheet.index },
      });
      onDone?.(`Sheet ${sheet.index}: ${result.message}`);
    } catch (reason) {
      onDone?.(errorText(reason, "Could not send the statement."), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <button type="button" className="secondary" disabled={busy} onClick={() => void send()}>
      <Mail aria-hidden="true" /> {busy ? "Sending…" : "Email statement"}
    </button>
  );
}
