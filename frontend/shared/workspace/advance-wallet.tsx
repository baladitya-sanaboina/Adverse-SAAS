"use client";

/*
 * Manager advance (Phase 12, owner decision 2026-11-14): the Admin sends a manager money in
 * advance (a top-up); commission on approved work is taken from it. A negative balance means the
 * manager has earned more than was advanced, and the next top-up covers that first.
 * Each top-up opens a payment sheet; the previous sheet's balance carries over (2026-11-14).
 * Used on the Manager's My Earnings page and in the Admin's manager view.
 */
import { FileDown } from "lucide-react";
import { formatDate } from "../production/client";
import { PaymentSheets } from "../production/payment-sheets";
import type { ManagerWallet } from "../production/types";
import "../styles/advance.css";

export function AdvanceWallet({
  wallet,
  currency,
  money,
  viewer,
  statementUrl,
}: {
  wallet: ManagerWallet;
  currency: string;
  money: (value: string | number, currency?: string) => string;
  viewer: "ADMIN" | "MANAGER";
  /** Where a sheet's statement PDF downloads from (owner request 2026-11-19). */
  statementUrl?: (index: number) => string;
}) {
  const balance = Number(wallet.balance);
  const owed = balance < 0;
  const balanceLabel = owed ? (viewer === "ADMIN" ? "You owe" : "Due to you") : "Advance left";

  return (
    <section className="advance-wallet" aria-label="Advance balance">
      <div className="advance-head">
        <div>
          <span>ADVANCE</span>
          <strong className={owed ? "owed" : undefined}>{money(Math.abs(balance), currency)}</strong>
          <small>
            {balanceLabel}
            {owed ? " · the next top-up covers this first" : ""}
          </small>
        </div>
        <dl>
          <div>
            <dt>Topped up</dt>
            <dd>{money(wallet.topped_up, currency)}</dd>
          </div>
          <div>
            <dt>Commission earned</dt>
            <dd>{money(wallet.earned, currency)}</dd>
          </div>
        </dl>
      </div>
      <div className="advance-sheets">
        <h3>Payment sheets</h3>
        <PaymentSheets
          sheets={wallet.periods.map((period) => ({
            index: period.index,
            start: period.start,
            end: period.end,
            paid: period.topped_up,
            carried_in: period.carried_in,
            used: period.earned,
            left: period.balance,
            items: period.items,
            ran_out_on: period.ran_out_on,
            lines: period.lines,
          }))}
          currency={currency}
          money={money}
          date={formatDate}
          itemWord="task"
          sheetAction={
            statementUrl
              ? (sheet) => (
                  <a className="secondary" href={statementUrl(sheet.index)} download>
                    <FileDown aria-hidden="true" /> Download statement PDF
                  </a>
                )
              : undefined
          }
          empty={
            viewer === "ADMIN"
              ? "No top-ups yet. Each top-up you send opens a new sheet."
              : "No top-ups yet. Each top-up from the Admin opens a new sheet."
          }
        />
      </div>
    </section>
  );
}
