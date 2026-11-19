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
}: {
  sheet: Sheet;
  clientId: string;
  onError?: (message: string) => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  if (sheet.invoice_id && sheet.invoice_code) {
    const status = sheet.invoice_status === "DRAFT" ? "draft" : (sheet.invoice_status ?? "").toLowerCase();
    return (
      <button type="button" className="secondary" onClick={() => router.push(`/invoices?invoice=${sheet.invoice_id}`)}>
        <FileText aria-hidden="true" /> Invoice {sheet.invoice_code}
        {status ? ` · ${status}` : ""}
      </button>
    );
  }

  async function generate() {
    setBusy(true);
    try {
      const invoice = await api<{ id: string }>("/api/company/invoices/sheet", {
        method: "POST",
        json: { client_id: clientId, start: sheet.start },
      });
      router.push(`/invoices?invoice=${invoice.id}`);
    } catch (reason) {
      onError?.(errorText(reason, "Could not make the invoice."));
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      disabled={busy || sheet.items === 0}
      title={sheet.items === 0 ? "No work on this sheet yet" : "Make the invoice for this sheet"}
      onClick={() => void generate()}
    >
      <ReceiptText aria-hidden="true" /> {busy ? "Making invoice…" : "Generate invoice"}
    </button>
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
