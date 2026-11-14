"use client";

/*
 * Payment sheets (owner decision 2026-11-14). Every payment (a manager top-up or a client budget
 * top-up) opens a new sheet; the previous sheet closes the day before and whatever was left, plus
 * or minus, is carried into the new one. Old sheets stay with their dates and their own lines.
 * Used on Manager earnings, the Admin's manager view, Client billing and Admin client details.
 */
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import "../styles/payment-sheets.css";

export type SheetLine = {
  day: string;
  kind: "CARRIED" | "PAYMENT" | "ADJUSTMENT" | "WORK";
  label: string;
  amount: string;
  balance: string;
};

export type Sheet = {
  index: number;
  start: string;
  end: string | null;
  paid: string;
  carried_in: string;
  used: string;
  left: string;
  items: number;
  ran_out_on: string | null;
  lines: SheetLine[];
};

const LINE_LABELS: Record<SheetLine["kind"], string> = {
  CARRIED: "Carried in",
  PAYMENT: "Payment",
  ADJUSTMENT: "Adjustment",
  WORK: "",
};

export function PaymentSheets({
  sheets,
  currency,
  money,
  date,
  itemWord,
  empty,
}: {
  sheets: Sheet[];
  currency: string;
  money: (value: string | number, currency?: string) => string;
  date: (value: string) => string;
  itemWord: "task" | "video";
  empty: string;
}) {
  const latest = sheets[sheets.length - 1]?.index ?? 0;
  const [open, setOpen] = useState<number | null>(null);
  const shown = open ?? latest;

  if (sheets.length === 0) return <p className="sheets-empty">{empty}</p>;

  const signed = (value: string | number) => {
    const amount = Number(value);
    return `${amount < 0 ? "−" : "+"}${money(Math.abs(amount), currency)}`;
  };

  return (
    <ol className="sheets" aria-label="Payment sheets">
      {[...sheets].reverse().map((sheet) => {
        const closed = sheet.end !== null;
        const left = Number(sheet.left);
        const pot = Math.max(Number(sheet.carried_in) + Number(sheet.paid), 0);
        const share = pot > 0 ? Math.min(100, (Number(sheet.used) / pot) * 100) : Number(sheet.used) > 0 ? 100 : 0;
        const expanded = shown === sheet.index;
        const leftLabel = closed ? `Carried to sheet ${sheet.index + 1}` : left < 0 ? "Over by" : "Left";
        return (
          <li key={sheet.index} className={`sheet${closed ? " closed" : ""}`}>
            <button
              type="button"
              className="sheet-head"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? -1 : sheet.index)}
            >
              <span className="sheet-title">
                <strong>Sheet {sheet.index}</strong>
                <em>{closed ? "Closed" : "Open"}</em>
              </span>
              <small>
                {date(sheet.start)} – {sheet.end ? date(sheet.end) : "now"}
              </small>
              <ChevronDown aria-hidden="true" />
            </button>
            <span className="sheet-bar" aria-hidden="true">
              <i style={{ width: `${share}%` }} className={share >= 100 ? "full" : share >= 80 ? "near" : undefined} />
            </span>
            <dl className="sheet-sum">
              {Number(sheet.carried_in) !== 0 && (
                <div>
                  <dt>Carried in</dt>
                  <dd className={Number(sheet.carried_in) < 0 ? "minus" : undefined}>{signed(sheet.carried_in)}</dd>
                </div>
              )}
              <div>
                <dt>Paid</dt>
                <dd className="plus">{signed(sheet.paid)}</dd>
              </div>
              <div>
                <dt>Used</dt>
                <dd>{money(sheet.used, currency)}</dd>
                <small>
                  {sheet.items} {sheet.items === 1 ? itemWord : `${itemWord}s`}
                </small>
              </div>
              <div>
                <dt>{leftLabel}</dt>
                <dd className={left < 0 ? "minus" : "plus"}>
                  {closed ? signed(left) : money(Math.abs(left), currency)}
                </dd>
              </div>
            </dl>
            {sheet.ran_out_on && <p className="sheet-note">Money ran out on {date(sheet.ran_out_on)}</p>}
            {expanded && (
              <ul className="sheet-lines" aria-label={`Sheet ${sheet.index} lines`}>
                {sheet.lines.map((line, index) => (
                  <li key={`${line.day}-${index}`} className={line.kind === "WORK" ? undefined : "money-in"}>
                    <span>
                      <strong>{line.kind === "WORK" ? line.label : line.label || LINE_LABELS[line.kind]}</strong>
                      <small>{date(line.day)}</small>
                    </span>
                    <span className="meta">
                      <em className={Number(line.amount) < 0 ? undefined : "plus"}>{signed(line.amount)}</em>
                      <small className={Number(line.balance) < 0 ? "minus" : undefined}>
                        Balance {money(line.balance, currency)}
                      </small>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}
