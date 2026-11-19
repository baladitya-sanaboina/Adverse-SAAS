"use client";

/*
 * Import a client's spreadsheets (owner request 2026-11-19): the content calendar and the payment
 * dashboard / work log they keep in Excel or Google Sheets. The file is read first and shown as a
 * preview; nothing is saved until the admin presses Import. Sending the same file again only adds
 * what is new.
 */
import { useState, type ChangeEvent } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Upload } from "lucide-react";
import { ManagementModal } from "@/components/foundation/management-modal";
import { formatDate, money } from "@/lib/production/client";
import "@/styles/client-import.css";

type Tab = {
  name: string;
  kind: "CALENDAR" | "WORK" | "BUDGET" | "OTHER";
  rows: number;
  skipped: number;
  first_day: string | null;
  last_day: string | null;
  sample: string[];
};
type MoneyLine = { day: string; label: string; amount: string; count: number };
type Preview = {
  client: { id: string; name: string; code: string };
  file_name: string;
  tabs: Tab[];
  payments: MoneyLine[];
  works: MoneyLine[];
  paid_total: string;
  work_total: string;
  warnings: string[];
};
type Result = { message: string };

async function post<T>(url: string, body: FormData): Promise<T> {
  const response = await fetch(url, { method: "POST", body, cache: "no-store" });
  const data = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "The file could not be read.");
  }
  return data as T;
}

export function ClientImportButton({ clientId, onImported }: { clientId: string; onImported: () => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [tabs, setTabs] = useState<string[]>([]);
  const [withMoney, setWithMoney] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const base = `/api/company/imports/clients/${clientId}`;

  const reset = () => {
    setFile(null);
    setPreview(null);
    setTabs([]);
    setWithMoney(true);
    setError("");
    setResult(null);
  };

  const close = () => {
    if (busy) return;
    if (result) onImported();
    setOpen(false);
    reset();
  };

  async function choose(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0];
    event.target.value = "";
    if (!picked) return;
    reset();
    setFile(picked);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", picked);
      const read = await post<Preview>(`${base}/preview`, form);
      setPreview(read);
      setTabs(read.tabs.filter((tab) => tab.kind === "CALENDAR" && tab.rows > 0).map((tab) => tab.name));
      setWithMoney(read.payments.length + read.works.length > 0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The file could not be read.");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("tabs", tabs.join("\n"));
      form.append("money", String(withMoney));
      setResult(await post<Result>(`${base}/apply`, form));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The import did not finish.");
    } finally {
      setBusy(false);
    }
  }

  const calendarTabs = preview?.tabs.filter((tab) => tab.kind === "CALENDAR") ?? [];
  const hasMoney = Boolean(preview && preview.payments.length + preview.works.length > 0);
  const nothingChosen = !tabs.length && !(hasMoney && withMoney);
  const videos = preview?.works.reduce((sum, line) => sum + line.count, 0) ?? 0;
  const lines = preview
    ? [
        ...preview.payments.map((line) => ({ ...line, paid: true })),
        ...preview.works.map((line) => ({ ...line, paid: false })),
      ]
    : [];

  return (
    <>
      <button type="button" className="management-secondary-action" onClick={() => setOpen(true)}>
        <FileSpreadsheet /> Import Excel / PDF
      </button>
      {open &&
        createPortal(
          <ManagementModal
            open={open}
            eyebrow="Import"
            title="Import spreadsheets"
            subtitle="Content calendar, payments and delivered work from an Excel or PDF file. You see everything before it is saved."
            icon={<FileSpreadsheet />}
            busy={busy}
            onClose={close}
            footer={
              result ? (
                <button type="button" className="management-primary-action" onClick={close}>
                  Done
                </button>
              ) : (
                <>
                  <button type="button" className="management-secondary-action" onClick={close} disabled={busy}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="management-primary-action"
                    disabled={!preview || nothingChosen || busy}
                    onClick={() => void save()}
                  >
                    {busy && preview ? "Importing…" : "Import"}
                  </button>
                </>
              )
            }
          >
            {result ? (
              <div className="client-import-done" role="status">
                <CheckCircle2 aria-hidden="true" />
                <div>
                  <strong>Import finished</strong>
                  <p>{result.message}</p>
                </div>
              </div>
            ) : (
              <>
                <label className={`client-import-drop${busy && !preview ? " busy" : ""}`}>
                  <Upload aria-hidden="true" />
                  <span>
                    <strong>{file ? file.name : "Choose an Excel (.xlsx) or PDF file"}</strong>
                    <small>
                      {busy && !preview
                        ? "Reading the file…"
                        : "From Google Sheets: File → Download → Excel or PDF. Excel keeps every tick and link."}
                    </small>
                  </span>
                  <input type="file" accept=".xlsx,.pdf" onChange={(event) => void choose(event)} disabled={busy} />
                </label>

                {error && (
                  <p className="client-import-error" role="alert">
                    {error}
                  </p>
                )}

                {preview && (
                  <>
                    {calendarTabs.length > 0 && (
                      <section className="client-import-group">
                        <h4>Content calendar</h4>
                        {calendarTabs.map((tab) => (
                          <label key={tab.name} className="client-import-option">
                            <input
                              type="checkbox"
                              checked={tabs.includes(tab.name)}
                              disabled={tab.rows === 0}
                              onChange={(event) =>
                                setTabs((current) =>
                                  event.target.checked
                                    ? [...current, tab.name]
                                    : current.filter((name) => name !== tab.name),
                                )
                              }
                            />
                            <span>
                              <strong>
                                {tab.name} · {tab.rows} {tab.rows === 1 ? "row" : "rows"}
                              </strong>
                              <small>
                                {tab.first_day && tab.last_day
                                  ? `${formatDate(tab.first_day)} – ${formatDate(tab.last_day)}`
                                  : "No dated rows"}
                                {tab.skipped ? ` · ${tab.skipped} without a date left out` : ""}
                              </small>
                              {tab.sample.length > 0 && <em>{tab.sample.join("  ·  ")}</em>}
                            </span>
                          </label>
                        ))}
                      </section>
                    )}

                    {hasMoney && (
                      <section className="client-import-group">
                        <h4>Payments and delivered work</h4>
                        <label className="client-import-option">
                          <input
                            type="checkbox"
                            checked={withMoney}
                            onChange={(event) => setWithMoney(event.target.checked)}
                          />
                          <span>
                            <strong>
                              {preview.payments.length > 0 && `Paid in ${money(preview.paid_total)}`}
                              {preview.payments.length > 0 && preview.works.length > 0 && " · "}
                              {preview.works.length > 0 &&
                                `${videos} ${videos === 1 ? "video" : "videos"} worth ${money(preview.work_total)}`}
                            </strong>
                            <small>
                              Each payment opens a payment sheet; each video is added as delivered work on its date.
                            </small>
                          </span>
                        </label>
                        <div className="client-import-lines">
                          <table>
                            <thead>
                              <tr>
                                <th scope="col">Date</th>
                                <th scope="col">Details</th>
                                <th scope="col">Amount</th>
                              </tr>
                            </thead>
                            <tbody>
                              {lines.slice(0, 12).map((line, index) => (
                                <tr key={index}>
                                  <td>{formatDate(line.day)}</td>
                                  <td>
                                    {line.paid ? "Payment · " : ""}
                                    {line.label}
                                    {line.count > 1 ? ` ×${line.count}` : ""}
                                  </td>
                                  <td className={line.paid ? "plus" : undefined}>{money(line.amount)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {lines.length > 12 && <small>and {lines.length - 12} more</small>}
                        </div>
                      </section>
                    )}

                    {preview.warnings.length > 0 && (
                      <ul className="client-import-warnings">
                        {preview.warnings.map((warning) => (
                          <li key={warning}>
                            <AlertTriangle aria-hidden="true" /> {warning}
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </>
            )}
          </ManagementModal>,
          // At page level, so the panel this button sits in does not style the dialog.
          document.body,
        )}
    </>
  );
}
