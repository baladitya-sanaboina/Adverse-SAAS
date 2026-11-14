"use client";

/*
 * Manager advance (Phase 12, owner decision 2026-11-14): the Admin sends a manager money in
 * advance (a top-up); commission on approved work is taken from it. A negative balance means the
 * manager has earned more than was advanced, and the next top-up covers that first.
 * Used on the Manager's My Earnings page and in the Admin's manager view.
 */
import { formatDate } from "../production/client";
import type { ManagerWallet } from "../production/types";
import "../styles/advance.css";

export function AdvanceWallet({
  wallet,
  currency,
  money,
  viewer,
}: {
  wallet: ManagerWallet;
  currency: string;
  money: (value: string | number, currency?: string) => string;
  viewer: "ADMIN" | "MANAGER";
}) {
  const balance = Number(wallet.balance);
  const owed = balance < 0;
  const latest = wallet.periods[wallet.periods.length - 1];
  const used =
    latest && Number(latest.topped_up) > 0
      ? Math.min(100, Math.round((Number(latest.earned) / Number(latest.topped_up)) * 100))
      : 0;
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
      {latest && (
        <div className="advance-meter" aria-label={`${used}% of the latest top-up used`}>
          <span className="advance-bar" aria-hidden="true">
            <i style={{ width: `${used}%` }} className={used >= 100 ? "full" : used >= 80 ? "near" : undefined} />
          </span>
          <small>
            Latest top-up: {money(latest.earned, currency)} of {money(latest.topped_up, currency)} used ({used}%)
          </small>
        </div>
      )}

      <div className="advance-grid">
        <div>
          <h3>Periods</h3>
          {wallet.periods.length === 0 ? (
            <p className="advance-empty">No top-ups yet.</p>
          ) : (
            <ul className="advance-periods">
              {[...wallet.periods].reverse().map((period) => {
                const share =
                  Number(period.topped_up) > 0
                    ? Math.min(100, (Number(period.earned) / Number(period.topped_up)) * 100)
                    : 0;
                const negative = Number(period.balance) < 0;
                return (
                  <li key={period.index}>
                    <span className="advance-period-top">
                      <strong>Top-up {period.index}</strong>
                      <small>
                        {formatDate(period.start)} – {period.end ? formatDate(period.end) : "now"}
                      </small>
                    </span>
                    <span className="advance-bar" aria-hidden="true">
                      <i style={{ width: `${share}%` }} className={share >= 100 ? "full" : undefined} />
                    </span>
                    <span className="advance-period-meta">
                      {money(period.earned, currency)} of {money(period.topped_up, currency)} · {period.items}{" "}
                      {period.items === 1 ? "task" : "tasks"}
                      <b className={negative ? "owed" : undefined}>
                        {negative
                          ? `${money(-Number(period.balance), currency)} over`
                          : `${money(period.balance, currency)} left`}
                      </b>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div>
          <h3>Timeline</h3>
          {wallet.lines.length === 0 ? (
            <p className="advance-empty">Top-ups and approved commission show up here.</p>
          ) : (
            <ul className="advance-lines">
              {wallet.lines.slice(0, 12).map((line, index) => (
                <li key={`${line.day}-${index}`}>
                  <span>
                    <strong>{line.kind === "TOP_UP" ? "Top-up" : line.title}</strong>
                    <small>{formatDate(line.day)}</small>
                  </span>
                  <span className="meta">
                    <em className={line.kind === "TOP_UP" ? "credit" : undefined}>
                      {line.kind === "TOP_UP" ? "+" : "−"}
                      {money(line.amount, currency)}
                    </em>
                    <small className={Number(line.balance) < 0 ? "owed" : undefined}>
                      Balance {money(line.balance, currency)}
                    </small>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
