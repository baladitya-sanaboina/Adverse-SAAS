"use client";

/*
 * Payment sheets (owner decision 2026-11-14). Every payment (a manager top-up or a payment
 * received from a client) opens a new sheet; the previous sheet closes the day before and
 * whatever was left, plus or minus, is carried into the new one. Old sheets stay with their dates.
 * Shown like a statement: sheet tabs, a summary, then Date | Details | Paid in | Used | Balance.
 * Each tab shows carried + paid and what moved on to the next sheet (owner request 2026-11-19).
 * Styled like the rest of the app (owner request 2026-11-15): chip tabs, a summary bar like
 * Payments, and the app's table.
 * Used on Manager earnings and sheets, the Admin's manager view and sheets page, Admin client
 * details and Client billing.
 */
import { Fragment, useMemo, useState, type ReactNode } from "react";
import { ArrowRight, X } from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
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
  // Admin only: the invoice made for this sheet (owner request 2026-11-15).
  invoice_id?: string | null;
  invoice_code?: string | null;
  invoice_status?: string | null;
};

type Money = (value: string | number, currency?: string) => string;

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function monthLabel(key: string): string {
  const [year, month] = key.split("-");
  return `${MONTH_NAMES[Number(month) - 1] ?? month} ${year}`;
}

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
  sheetAction,
}: {
  sheets: Sheet[];
  currency: string;
  money: Money;
  date: (value: string) => string;
  itemWord: "task" | "video";
  empty: string;
  /** Something to show on the sheet's summary bar, e.g. the Admin's invoice button. */
  sheetAction?: (sheet: Sheet) => ReactNode;
}) {
  // Month filter (owner request 2026-11-19): sheets stay one per payment; a month shows the sheets
  // that ran in it and only that month's lines.
  const [month, setMonth] = useState("");
  const months = useMemo(() => {
    const found = new Set<string>();
    for (const item of sheets) for (const line of item.lines) found.add(line.day.slice(0, 7));
    return [...found].sort().reverse();
  }, [sheets]);
  // Sheet filter (owner request 2026-11-19): every sheet, only the open one, or closed ones.
  const [state, setState] = useState("");
  const shown = sheets.filter(
    (item) =>
      (!month || item.lines.some((line) => line.day.startsWith(month))) &&
      (!state || (state === "open" ? item.end === null : item.end !== null)),
  );
  const latest = shown[shown.length - 1]?.index ?? 0;
  const [chosen, setChosen] = useState<number | null>(null);
  const sheet = shown.find((item) => item.index === (chosen ?? latest)) ?? shown[shown.length - 1];

  if (!sheets.length) return <p className="sheets-empty">{empty}</p>;

  return (
    <div className="sheet-book">
      <div className="sheet-month">
        <span>Filter sheets</span>
        <LooplessSelect
          value={month}
          ariaLabel="Show sheets for a month"
          onValueChange={(value) => {
            setMonth(value);
            setChosen(null);
          }}
          options={[
            { value: "", label: "All months" },
            ...months.map((key) => ({ value: key, label: monthLabel(key) })),
          ]}
        />
        <LooplessSelect
          value={state}
          ariaLabel="Open or closed sheets"
          onValueChange={(value) => {
            setState(value);
            setChosen(null);
          }}
          options={[
            { value: "", label: `All sheets (${sheets.length})` },
            { value: "open", label: "Open sheet" },
            { value: "closed", label: "Closed sheets" },
          ]}
        />
        {(month || state) && (
          <small>
            {shown.length} of {sheets.length} {sheets.length === 1 ? "sheet" : "sheets"}
            {month ? ` in ${monthLabel(month)}` : ""}
          </small>
        )}
      </div>
      {!sheet && <p className="sheets-empty">No sheet matches these filters.</p>}
      {sheet && shown.length > 1 && (
        <div className="sheet-tabs" role="tablist" aria-label="Payment sheets">
          {shown.map((item, position) => {
            // Each tab shows how the money moves: what came in and what went on to the next sheet.
            const carried = Number(item.carried_in);
            const left = Number(item.left);
            const signed = (value: number) => `${value < 0 ? "−" : ""}${money(Math.abs(value), currency)}`;
            return (
              <Fragment key={item.index}>
                {position > 0 && <ArrowRight className="sheet-tab-arrow" aria-hidden="true" />}
                <button
                  type="button"
                  role="tab"
                  aria-selected={item.index === sheet.index}
                  className={item.index === sheet.index ? "active" : undefined}
                  onClick={() => setChosen(item.index)}
                >
                  <span className="sheet-tab-title">
                    Sheet {item.index}
                    <small>
                      {date(item.start)} – {item.end ? date(item.end) : "now"}
                    </small>
                  </span>
                  <span className="sheet-tab-flow">
                    {carried > 0 && `${money(carried, currency)} from sheet ${item.index - 1} + `}
                    {money(item.paid, currency)} paid
                    {carried < 0 && ` − ${money(-carried, currency)} extra from sheet ${item.index - 1}`}
                  </span>
                  <span className={`sheet-tab-left${left < 0 ? " minus" : ""}`}>
                    {item.end
                      ? left < 0
                        ? `${money(-left, currency)} extra used → sheet ${item.index + 1}`
                        : `${money(left, currency)} left → sheet ${item.index + 1}`
                      : left < 0
                        ? `${money(-left, currency)} extra used`
                        : `${money(left, currency)} left now`}
                  </span>
                </button>
              </Fragment>
            );
          })}
        </div>
      )}
      {sheet && (
        <SheetPage
          key={`${sheet.index}-${month}`}
          month={month}
          sheet={sheet}
          currency={currency}
          money={money}
          date={date}
          itemWord={itemWord}
          action={sheetAction?.(sheet)}
        />
      )}
    </div>
  );
}

function SheetPage({
  sheet,
  month,
  currency,
  money,
  date,
  itemWord,
  action,
}: {
  sheet: Sheet;
  /** "YYYY-MM": only that month's lines; "" for all. */
  month: string;
  currency: string;
  money: Money;
  date: (value: string) => string;
  itemWord: "task" | "video";
  action?: ReactNode;
}) {
  // A filter for every column (owner request 2026-11-15).
  const [byDay, setByDay] = useState("");
  const [text, setText] = useState("");
  const [paidFilter, setPaidFilter] = useState("");
  const [usedFilter, setUsedFilter] = useState("");
  const [balanceFilter, setBalanceFilter] = useState("");
  const lines = useMemo(
    () => (month ? sheet.lines.filter((line) => line.day.startsWith(month)) : sheet.lines),
    [sheet.lines, month],
  );
  const days = useMemo(() => [...new Set(lines.map((line) => line.day))], [lines]);
  const visible = lines.filter((line) => {
    const amount = Number(line.amount);
    const balance = Number(line.balance);
    if (byDay && line.day !== byDay) return false;
    if (text && !line.label.toLowerCase().includes(text.trim().toLowerCase())) return false;
    if (paidFilter === "yes" && !(amount > 0)) return false;
    if (paidFilter === "no" && amount > 0) return false;
    if (usedFilter === "yes" && !(amount < 0)) return false;
    if (usedFilter === "no" && amount < 0) return false;
    if (balanceFilter === "minus" && !(balance < 0)) return false;
    if (balanceFilter === "plus" && !(balance >= 0)) return false;
    return true;
  });
  const filtered = visible.length !== lines.length;
  const clear = () => {
    setByDay("");
    setText("");
    setPaidFilter("");
    setUsedFilter("");
    setBalanceFilter("");
  };
  const closed = sheet.end !== null;
  const left = Number(sheet.left);
  const carried = Number(sheet.carried_in);
  const pot = carried + Number(sheet.paid);
  const percent = pot > 0 ? Math.round((Number(sheet.used) / pot) * 100) : Number(sheet.used) > 0 ? 100 : 0;
  const state = tone(sheet);
  const paidIn = visible.reduce((sum, line) => sum + Math.max(Number(line.amount), 0), 0);
  const usedOut = visible.reduce((sum, line) => sum + Math.max(-Number(line.amount), 0), 0);
  const noPayment = Number(sheet.paid) === 0 && carried === 0;

  const headline = noPayment
    ? "No payment yet"
    : closed
      ? left < 0
        ? `${money(-left, currency)} extra used · taken from sheet ${sheet.index + 1}`
        : `${money(left, currency)} left · carried to sheet ${sheet.index + 1}`
      : left < 0
        ? `${money(-left, currency)} extra used`
        : `${money(left, currency)} left`;

  return (
    <section className={`sheet-page ${state}`} role="tabpanel" aria-label={`Sheet ${sheet.index}`}>
      <div className="sheet-summary">
        <div className="sheet-summary-main">
          <span>
            Sheet {sheet.index} · {closed ? "Closed" : "Open"} · {date(sheet.start)} –{" "}
            {sheet.end ? date(sheet.end) : "now"}
          </span>
          <strong className={left < 0 && !noPayment ? "minus" : undefined}>{headline}</strong>
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
          {action && <div className="sheet-summary-action">{action}</div>}
        </div>
        <dl className="sheet-figures">
          <div>
            <dt>
              {carried < 0
                ? `Extra from sheet ${sheet.index - 1}`
                : carried > 0
                  ? `From sheet ${sheet.index - 1}`
                  : "Carried in"}
            </dt>
            <dd className={carried < 0 ? "minus" : undefined}>
              {carried === 0 ? "—" : `${carried < 0 ? "−" : "+"}${money(Math.abs(carried), currency)}`}
            </dd>
          </div>
          <div>
            <dt>Paid in</dt>
            <dd>{money(sheet.paid, currency)}</dd>
          </div>
          <div>
            <dt>
              Used · {sheet.items} {sheet.items === 1 ? itemWord : `${itemWord}s`}
            </dt>
            <dd>{money(sheet.used, currency)}</dd>
          </div>
          <div>
            <dt>Balance</dt>
            <dd className={left < 0 ? "minus" : undefined}>
              {left < 0 ? "−" : ""}
              {money(Math.abs(left), currency)}
            </dd>
          </div>
        </dl>
      </div>

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
            <tr className="sheet-filters">
              <th scope="col">
                <LooplessSelect
                  value={byDay}
                  onValueChange={setByDay}
                  ariaLabel="Filter by date"
                  options={[
                    { value: "", label: "All dates" },
                    ...days.map((day) => ({ value: day, label: date(day) })),
                  ]}
                />
              </th>
              <th scope="col">
                <input
                  type="search"
                  value={text}
                  placeholder="Search details"
                  aria-label="Search details"
                  onChange={(event) => setText(event.target.value)}
                />
              </th>
              <th scope="col">
                <LooplessSelect
                  value={paidFilter}
                  onValueChange={setPaidFilter}
                  ariaLabel="Filter by paid in"
                  options={[
                    { value: "", label: "All" },
                    { value: "yes", label: "Money in" },
                    { value: "no", label: "No money in" },
                  ]}
                />
              </th>
              <th scope="col">
                <LooplessSelect
                  value={usedFilter}
                  onValueChange={setUsedFilter}
                  ariaLabel="Filter by used"
                  options={[
                    { value: "", label: "All" },
                    { value: "yes", label: `Used (${itemWord}s)` },
                    { value: "no", label: "Not used" },
                  ]}
                />
              </th>
              <th scope="col">
                <LooplessSelect
                  value={balanceFilter}
                  onValueChange={setBalanceFilter}
                  ariaLabel="Filter by balance"
                  options={[
                    { value: "", label: "All" },
                    { value: "plus", label: "In credit" },
                    { value: "minus", label: "Below zero" },
                  ]}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={5} className="sheet-no-rows">
                  No rows match these filters.
                </td>
              </tr>
            )}
            {visible.map((line, index) => {
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
                {filtered ? (
                  <span className="sheet-filtered">
                    Showing {visible.length} of {lines.length}
                    <button type="button" onClick={clear}>
                      <X aria-hidden="true" /> Clear filters
                    </button>
                  </span>
                ) : month ? (
                  `Total in ${monthLabel(month)}`
                ) : (
                  "Total"
                )}
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
