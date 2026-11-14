"use client";

/*
 * Payment sheets (owner decision 2026-11-14). Every payment (a manager top-up or a payment
 * received from a client) opens a new sheet; the previous sheet closes the day before and
 * whatever was left, plus or minus, is carried into the new one. Old sheets stay with their dates.
 * Shown like a statement: sheet tabs, a summary, then Date | Details | Paid in | Used | Balance.
 * Used on Manager earnings and sheets, the Admin's manager view and sheets page, Admin client
 * details and Client billing.
 */
import { useState } from "react";
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

type Money = (value: string | number, currency?: string) => string;

function tone(sheet: Sheet): "over" | "low" | "ok" {
  const left = Number(sheet.left);
  const pot = Number(sheet.carried_in) + Number(sheet.paid);
  if (left <= 0) return "over";
  if (pot > 0 && Number(sheet.used) / pot >= 0.8) return "low";
  return "ok";
}

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
  money: Money;
  date: (value: string) => string;
  itemWord: "task" | "video";
  empty: string;
}) {
  const latest = sheets[sheets.length - 1]?.index ?? 0;
  const [chosen, setChosen] = useState<number | null>(null);
  const sheet = sheets.find((item) => item.index === (chosen ?? latest)) ?? sheets[sheets.length - 1];

  if (!sheet) return <p className="sheets-empty">{empty}</p>;

  return (
    <div className="sheet-book">
      {sheets.length > 1 && (
        <div className="sheet-tabs" role="tablist" aria-label="Payment sheets">
          {sheets.map((item) => (
            <button
              key={item.index}
              type="button"
              role="tab"
              aria-selected={item.index === sheet.index}
              className={`${item.index === sheet.index ? "active " : ""}${tone(item)}`}
              onClick={() => setChosen(item.index)}
            >
              <strong>
                <i aria-hidden="true" />
                Sheet {item.index}
              </strong>
              <small>
                {date(item.start)} – {item.end ? date(item.end) : "now"}
              </small>
            </button>
          ))}
        </div>
      )}
      <SheetPage sheet={sheet} currency={currency} money={money} date={date} itemWord={itemWord} />
    </div>
  );
}

function SheetPage({
  sheet,
  currency,
  money,
  date,
  itemWord,
}: {
  sheet: Sheet;
  currency: string;
  money: Money;
  date: (value: string) => string;
  itemWord: "task" | "video";
}) {
  const closed = sheet.end !== null;
  const left = Number(sheet.left);
  const carried = Number(sheet.carried_in);
  const pot = carried + Number(sheet.paid);
  const percent = pot > 0 ? Math.round((Number(sheet.used) / pot) * 100) : Number(sheet.used) > 0 ? 100 : 0;
  const state = tone(sheet);
  const paidIn = sheet.lines.reduce((sum, line) => sum + Math.max(Number(line.amount), 0), 0);
  const usedOut = sheet.lines.reduce((sum, line) => sum + Math.max(-Number(line.amount), 0), 0);
  const noPayment = Number(sheet.paid) === 0 && carried === 0;

  return (
    <section className={`sheet-page ${state}`} role="tabpanel" aria-label={`Sheet ${sheet.index}`}>
      <header className="sheet-page-head">
        <div>
          <span className="sheet-page-title">
            <strong>Sheet {sheet.index}</strong>
            <em className={closed ? "closed" : "open"}>{closed ? "Closed" : "Open"}</em>
          </span>
          <small>
            {date(sheet.start)} – {sheet.end ? date(sheet.end) : "now"}
          </small>
        </div>
        <div className="sheet-page-left">
          <span>
            {noPayment
              ? "No payment yet"
              : closed
                ? `Carried to sheet ${sheet.index + 1}`
                : left < 0
                  ? "Over by"
                  : "Left"}
          </span>
          <strong>{money(Math.abs(left), currency)}</strong>
        </div>
      </header>

      <div className="sheet-meter">
        <span aria-hidden="true">
          <i style={{ width: `${Math.min(percent, 100)}%` }} />
        </span>
        <small>
          {noPayment
            ? `${sheet.items} ${sheet.items === 1 ? itemWord : `${itemWord}s`} done, nothing paid yet`
            : `${percent}% used`}
          {sheet.ran_out_on && !noPayment ? ` · money ran out on ${date(sheet.ran_out_on)}` : ""}
        </small>
      </div>

      <dl className="sheet-figures">
        <div>
          <dt>Carried in</dt>
          <dd className={carried < 0 ? "minus" : undefined}>
            {carried === 0 ? "—" : `${carried < 0 ? "−" : "+"}${money(Math.abs(carried), currency)}`}
          </dd>
        </div>
        <div>
          <dt>Paid in</dt>
          <dd className="plus">{money(sheet.paid, currency)}</dd>
        </div>
        <div>
          <dt>Used</dt>
          <dd>{money(sheet.used, currency)}</dd>
          <small>
            {sheet.items} {sheet.items === 1 ? itemWord : `${itemWord}s`}
          </small>
        </div>
        <div>
          <dt>Balance</dt>
          <dd className={left < 0 ? "minus" : "plus"}>
            {left < 0 ? "−" : ""}
            {money(Math.abs(left), currency)}
          </dd>
        </div>
      </dl>

      <div className="sheet-table-wrap">
        <table className="sheet-table">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Details</th>
              <th scope="col">Paid in</th>
              <th scope="col">Used</th>
              <th scope="col">Balance</th>
            </tr>
          </thead>
          <tbody>
            {sheet.lines.map((line, index) => {
              const amount = Number(line.amount);
              const balance = Number(line.balance);
              return (
                <tr key={`${line.day}-${index}`} className={line.kind === "WORK" ? undefined : "money"}>
                  <td>{date(line.day)}</td>
                  <td className="details">{line.label}</td>
                  <td className="plus">{amount > 0 ? money(amount, currency) : ""}</td>
                  <td>{amount < 0 ? money(-amount, currency) : ""}</td>
                  <td className={balance < 0 ? "minus" : undefined}>
                    {balance < 0 ? "−" : ""}
                    {money(Math.abs(balance), currency)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={2}>
                Total
              </th>
              <td className="plus">{money(paidIn, currency)}</td>
              <td>{money(usedOut, currency)}</td>
              <td className={left < 0 ? "minus" : undefined}>
                {left < 0 ? "−" : ""}
                {money(Math.abs(left), currency)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
