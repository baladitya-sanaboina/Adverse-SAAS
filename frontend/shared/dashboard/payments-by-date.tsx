"use client";

/*
 * Payments by date (owner request 2026-11-28): a dashboard section with a month filter, then every
 * payment of that month grouped by day, newest first, with the day's total. The Admin sees money
 * in (client payments) and out (salaries, manager top-ups); a manager sees the top-ups they got.
 * The parent loads the month's rows; this panel only filters by day and lays them out.
 */
import { useMemo, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, CalendarDays } from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { Panel, PanelHead, lastMonths } from "./role-dashboard-ui";
import "../styles/payments-by-date.css";

export type DatedPayment = {
  id: string;
  /** YYYY-MM-DD */
  day: string;
  title: string;
  detail: string;
  amount: number;
  direction: "IN" | "OUT";
};

/** The "Last 30 days" choice in the month list (owner request 2026-11-28). */
export const LAST_30_DAYS = "last30";

const isoDate = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

/** First and last day of a month ("YYYY-MM"), or of the last 30 days (today included). */
export function monthRange(month: string): { start: string; end: string } {
  if (month === LAST_30_DAYS) {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 29);
    return { start: isoDate(start), end: isoDate(now) };
  }
  const [year, number] = month.split("-").map(Number);
  const last = new Date(year, number, 0).getDate();
  return { start: `${month}-01`, end: `${month}-${String(last).padStart(2, "0")}` };
}

function monthLabel(month: string): string {
  if (month === LAST_30_DAYS) return "Last 30 days";
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(new Date(`${month}-01T00:00:00`));
}

function dayLabel(day: string): string {
  return new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" }).format(
    new Date(`${day}T00:00:00`),
  );
}

export function PaymentsByDatePanel({
  rows,
  month,
  onMonth,
  money,
  loading = false,
  error = "",
  eyebrow = "PAYMENTS",
  inLabel = "Received",
  outLabel = "Paid out",
  empty = "No payments in this month.",
}: {
  rows: DatedPayment[];
  month: string;
  onMonth: (month: string) => void;
  money: (amount: number) => string;
  loading?: boolean;
  error?: string;
  eyebrow?: string;
  inLabel?: string;
  outLabel?: string;
  empty?: string;
}) {
  const [day, setDay] = useState("");
  const months = useMemo(() => lastMonths(12).reverse(), []);
  const days = useMemo(() => [...new Set(rows.map((row) => row.day))].sort().reverse(), [rows]);
  const chosenDay = days.includes(day) ? day : "";
  const groups = useMemo(() => {
    const byDay = new Map<string, DatedPayment[]>();
    for (const row of rows) {
      if (chosenDay && row.day !== chosenDay) continue;
      byDay.set(row.day, [...(byDay.get(row.day) ?? []), row]);
    }
    return [...byDay.entries()].sort(([a], [b]) => b.localeCompare(a));
  }, [rows, chosenDay]);
  const shown = groups.flatMap(([, items]) => items);
  const total = (items: DatedPayment[], direction: DatedPayment["direction"]) =>
    items.filter((row) => row.direction === direction).reduce((sum, row) => sum + row.amount, 0);
  const hasOut = rows.some((row) => row.direction === "OUT");
  const hasIn = rows.some((row) => row.direction === "IN");

  return (
    <Panel>
      <PanelHead
        eyebrow={eyebrow}
        title={chosenDay ? dayLabel(chosenDay) : monthLabel(month)}
        aside={
          <div className="pay-date-filters">
            <LooplessSelect
              value={month}
              onValueChange={(value) => {
                setDay("");
                onMonth(value);
              }}
              ariaLabel="Month"
              options={[
                { value: LAST_30_DAYS, label: "Last 30 days" },
                ...months.map((key) => ({ value: key, label: monthLabel(key) })),
              ]}
            />
            <LooplessSelect
              value={chosenDay}
              onValueChange={setDay}
              ariaLabel="Date"
              disabled={days.length === 0}
              options={[
                { value: "", label: "All dates" },
                ...days.map((key) => ({ value: key, label: dayLabel(key) })),
              ]}
            />
          </div>
        }
      />
      <div className="production-dash-panel-body">
        {error ? (
          <p className="production-dash-empty">{error}</p>
        ) : loading && rows.length === 0 ? (
          <p className="production-dash-empty">Loading payments…</p>
        ) : rows.length === 0 ? (
          <p className="production-dash-empty">
            <CalendarDays aria-hidden="true" />
            {empty}
          </p>
        ) : (
          <>
            <div className="pay-date-totals">
              {(hasIn || !hasOut) && (
                <span className="in">
                  <small>{inLabel}</small>
                  <strong>{money(total(shown, "IN"))}</strong>
                </span>
              )}
              {hasOut && (
                <span className="out">
                  <small>{outLabel}</small>
                  <strong>{money(total(shown, "OUT"))}</strong>
                </span>
              )}
              <span>
                <small>Payments</small>
                <strong>{shown.length}</strong>
              </span>
            </div>
            <div className={`pay-date-days${loading ? " refreshing" : ""}`}>
              {groups.map(([key, items]) => {
                const dayIn = total(items, "IN");
                const dayOut = total(items, "OUT");
                return (
                  <section key={key} className="pay-date-day">
                    <header>
                      <strong>{dayLabel(key)}</strong>
                      <span>
                        {dayIn > 0 && <em className="in">+{money(dayIn)}</em>}
                        {dayOut > 0 && <em className="out">−{money(dayOut)}</em>}
                      </span>
                    </header>
                    <ul className="production-dash-rows">
                      {items.map((row) => (
                        <li key={row.id}>
                          <div className="pay-date-row">
                            <span
                              className={`pay-date-icon ${row.direction === "IN" ? "in" : "out"}`}
                              aria-hidden="true"
                            >
                              {row.direction === "IN" ? <ArrowDownLeft /> : <ArrowUpRight />}
                            </span>
                            <span className="pay-date-text">
                              <strong>{row.title}</strong>
                              <small>{row.detail}</small>
                            </span>
                            <em className={row.direction === "IN" ? "in" : "out"}>
                              {row.direction === "IN" ? "+" : "−"}
                              {money(row.amount)}
                            </em>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}
