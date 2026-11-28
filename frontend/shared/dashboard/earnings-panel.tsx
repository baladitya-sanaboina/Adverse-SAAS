"use client";

/*
 * Earnings on the Admin and Manager dashboards (owner request 2026-11-28): one section with
 * Date / Week / Month / Year views, a bar graph of the recent periods, the chosen period's total
 * against the one before, and the work behind it. Click a bar or pick a date to look at that
 * period. The Admin's earnings are client prices of delivered work (with the managers'
 * commission); a manager's are their own commission. The parent passes the lines.
 */
import { useMemo, useState } from "react";
import { TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { LooplessDate } from "@/components/foundation/loopless-date";
import { Panel, PanelHead } from "./role-dashboard-ui";
import "../styles/earnings-panel.css";

export type EarningItem = {
  key: string;
  /** YYYY-MM-DD, in the viewer's calendar */
  day: string;
  title: string;
  detail: string;
  amount: number;
  /** Admin: the manager commission on this work. */
  commission?: number;
};

type View = "day" | "week" | "month" | "year";

const VIEWS: { id: View; label: string; bars: number }[] = [
  { id: "day", label: "Date", bars: 14 },
  { id: "week", label: "Week", bars: 12 },
  { id: "month", label: "Month", bars: 12 },
  { id: "year", label: "Year", bars: 5 },
];

const PREVIOUS: Record<View, string> = {
  day: "the day before",
  week: "last week",
  month: "last month",
  year: "last year",
};

const pad = (value: number) => String(value).padStart(2, "0");
export const isoDay = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const parse = (value: string) => {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day);
};
const fmt = (options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("en-IN", options);

/** First day of the period that holds `date`. Weeks start on Monday. */
function periodStart(view: View, date: Date): Date {
  if (view === "day") return new Date(date.getFullYear(), date.getMonth(), date.getDate());
  if (view === "week") {
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    return start;
  }
  if (view === "month") return new Date(date.getFullYear(), date.getMonth(), 1);
  return new Date(date.getFullYear(), 0, 1);
}

function shift(view: View, start: Date, steps: number): Date {
  if (view === "day") return new Date(start.getFullYear(), start.getMonth(), start.getDate() + steps);
  if (view === "week") return new Date(start.getFullYear(), start.getMonth(), start.getDate() + steps * 7);
  if (view === "month") return new Date(start.getFullYear(), start.getMonth() + steps, 1);
  return new Date(start.getFullYear() + steps, 0, 1);
}

function barLabel(view: View, start: Date): string {
  if (view === "month") return fmt({ month: "short", year: "2-digit" }).format(start);
  if (view === "year") return String(start.getFullYear());
  return fmt({ day: "numeric", month: "short" }).format(start);
}

function periodTitle(view: View, start: Date): string {
  if (view === "day") return fmt({ weekday: "short", day: "numeric", month: "long", year: "numeric" }).format(start);
  if (view === "week") {
    const end = shift("day", start, 6);
    return `Week of ${fmt({ day: "numeric", month: "short" }).format(start)} – ${fmt({
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(end)}`;
  }
  if (view === "month") return fmt({ month: "long", year: "numeric" }).format(start);
  return String(start.getFullYear());
}

export function EarningsPanel({
  items,
  money,
  eyebrow = "EARNINGS",
  amountLabel = "Earned",
  countLabel = "Items",
  loading = false,
  error = "",
}: {
  items: EarningItem[];
  money: (amount: number) => string;
  eyebrow?: string;
  amountLabel?: string;
  countLabel?: string;
  loading?: boolean;
  error?: string;
}) {
  const [mode, setMode] = useState<View | "last30" | "custom">("month");
  const [today] = useState(() => isoDay(new Date()));
  const [focus, setFocus] = useState(today);
  const [from, setFrom] = useState(() => `${today.slice(0, 8)}01`);
  const [to, setTo] = useState(today);
  const [showAll, setShowAll] = useState(false);
  const withCommission = items.some((item) => item.commission !== undefined);

  // Custom From–To (owner request 2026-11-28): the graph is by day for up to a month, by week
  // for up to half a year, else by month; the comparison is the same number of days before.
  // "30 days" (owner request 2026-11-28) is a ready-made range: today and the 29 days before.
  const custom = mode === "custom" || mode === "last30";
  const thirtyAgo = isoDay(shift("day", parse(today), -29));
  const first = mode === "last30" ? thirtyAgo : from <= to ? from : to;
  const lastDay = mode === "last30" ? today : from <= to ? to : from;
  const spanDays = Math.round((parse(lastDay).getTime() - parse(first).getTime()) / 86_400_000) + 1;
  const view: View = !custom ? mode : spanDays <= 31 ? "day" : spanDays <= 182 ? "week" : "month";
  const selected = periodStart(view, parse(focus));
  const range = custom
    ? {
        start: first,
        next: isoDay(shift("day", parse(lastDay), 1)),
        title: `${fmt({ day: "numeric", month: "short", year: "numeric" }).format(parse(first))} – ${fmt({
          day: "numeric",
          month: "short",
          year: "numeric",
        }).format(parse(lastDay))}`,
        before: [isoDay(shift("day", parse(first), -spanDays)), first] as const,
        beforeLabel: `the ${spanDays} ${spanDays === 1 ? "day" : "days"} before`,
      }
    : {
        start: isoDay(selected),
        next: isoDay(shift(view, selected, 1)),
        title: periodTitle(view, selected),
        before: [isoDay(shift(view, selected, -1)), isoDay(selected)] as const,
        beforeLabel: PREVIOUS[view],
      };

  // Totals per graph period.
  const totals = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of items) {
      const key = isoDay(periodStart(view, parse(item.day)));
      map.set(key, (map.get(key) ?? 0) + item.amount);
    }
    return map;
  }, [items, view]);

  // Custom: every period in the range. Otherwise the last few, ending at the current period, or
  // at the chosen one when that is further back.
  const columns = useMemo(() => {
    const list: { key: string; start: Date; total: number }[] = [];
    if (custom) {
      let at = periodStart(view, parse(first));
      while (isoDay(at) <= lastDay && list.length < 62) {
        list.push({ key: isoDay(at), start: at, total: totals.get(isoDay(at)) ?? 0 });
        at = shift(view, at, 1);
      }
      return list;
    }
    const bars = VIEWS.find((item) => item.id === view)?.bars ?? 12;
    const current = periodStart(view, parse(today));
    const last = isoDay(shift(view, selected, bars - 1)) >= isoDay(current) ? current : selected;
    for (let index = 0; index < bars; index += 1) {
      const at = shift(view, last, index - (bars - 1));
      list.push({ key: isoDay(at), start: at, total: totals.get(isoDay(at)) ?? 0 });
    }
    return list;
  }, [custom, view, first, lastDay, totals, today, selected]);
  const highest = Math.max(1, ...columns.map((column) => column.total));
  const selectedKey = custom ? "" : isoDay(selected);

  const lines = items
    .filter((item) => item.day >= range.start && item.day < range.next)
    .sort((a, b) => b.day.localeCompare(a.day));
  const now = {
    amount: lines.reduce((sum, item) => sum + item.amount, 0),
    commission: lines.reduce((sum, item) => sum + (item.commission ?? 0), 0),
    count: lines.length,
  };
  const before = items
    .filter((item) => item.day >= range.before[0] && item.day < range.before[1])
    .reduce((sum, item) => sum + item.amount, 0);
  const change = before > 0 ? ((now.amount - before) / before) * 100 : null;
  const shown = showAll ? lines : lines.slice(0, 8);
  // A bar opens that period in its own view (Date, Week or Month).
  const choose = (day: string) => {
    if (custom) setMode(view);
    setFocus(day);
    setShowAll(false);
  };

  return (
    <Panel>
      <PanelHead
        eyebrow={eyebrow}
        title={range.title}
        aside={
          <div className="earn-controls">
            <div className="earn-views" role="tablist" aria-label="Earnings by">
              {[...VIEWS, { id: "last30" as const, label: "30 days" }, { id: "custom" as const, label: "Custom" }].map(
                (item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={mode === item.id}
                    className={mode === item.id ? "active" : undefined}
                    onClick={() => {
                      setMode(item.id);
                      setShowAll(false);
                    }}
                  >
                    {item.label}
                  </button>
                ),
              )}
            </div>
            {mode === "custom" ? (
              <div className="earn-range">
                <LooplessDate
                  value={from}
                  onValueChange={(value) => {
                    setFrom(value || today);
                    setShowAll(false);
                  }}
                  ariaLabel="From date"
                  max={today}
                  clearable={false}
                />
                <span aria-hidden="true">to</span>
                <LooplessDate
                  value={to}
                  onValueChange={(value) => {
                    setTo(value || today);
                    setShowAll(false);
                  }}
                  ariaLabel="To date"
                  max={today}
                  clearable={false}
                />
              </div>
            ) : mode === "last30" ? null : (
              <LooplessDate
                value={focus}
                onValueChange={(value) => choose(value || today)}
                ariaLabel="Pick a date"
                max={today}
                clearable={false}
              />
            )}
          </div>
        }
      />
      <div className="production-dash-panel-body">
        {error ? (
          <p className="production-dash-empty">{error}</p>
        ) : loading && items.length === 0 ? (
          <p className="production-dash-empty">Loading earnings…</p>
        ) : (
          <>
            <div className="earn-tiles">
              <span className="main">
                <small>{amountLabel}</small>
                <strong>{money(now.amount)}</strong>
                <em className={change === null ? undefined : change >= 0 ? "up" : "down"}>
                  {change === null ? (
                    `${money(before)} ${range.beforeLabel}`
                  ) : (
                    <>
                      {change >= 0 ? <TrendingUp aria-hidden="true" /> : <TrendingDown aria-hidden="true" />}
                      {Math.abs(change).toFixed(0)}% vs {range.beforeLabel}
                    </>
                  )}
                </em>
              </span>
              <span>
                <small>{countLabel}</small>
                <strong>{now.count}</strong>
              </span>
              {withCommission && (
                <>
                  <span>
                    <small>Manager commission</small>
                    <strong>{money(now.commission)}</strong>
                  </span>
                  <span>
                    <small>After commission</small>
                    <strong>{money(now.amount - now.commission)}</strong>
                  </span>
                </>
              )}
            </div>

            <div className="earn-chart" role="group" aria-label={`${amountLabel} per period`}>
              {columns.map((column) => (
                <button
                  key={column.key}
                  type="button"
                  className={`earn-bar${column.key === selectedKey ? " selected" : ""}`}
                  onClick={() => choose(column.key)}
                  aria-pressed={column.key === selectedKey}
                  title={`${periodTitle(view, column.start)}: ${money(column.total)}`}
                >
                  <span className="earn-bar-value">{column.total > 0 ? money(column.total) : ""}</span>
                  <span className="earn-bar-track">
                    <i style={{ height: `${column.total > 0 ? Math.max(4, (column.total / highest) * 100) : 0}%` }} />
                  </span>
                  <span className="earn-bar-label">{barLabel(view, column.start)}</span>
                </button>
              ))}
            </div>

            {lines.length === 0 ? (
              <p className="production-dash-empty">
                <Wallet aria-hidden="true" />
                Nothing earned in {custom ? "these dates" : `this ${view === "day" ? "day" : view}`}.
              </p>
            ) : (
              <>
                <ul className="production-dash-rows earn-lines">
                  {shown.map((item) => (
                    <li key={item.key}>
                      <div className="earn-line">
                        <span>
                          <small>{item.detail}</small>
                          <strong>{item.title}</strong>
                        </span>
                        <span className="meta">
                          <em>{money(item.amount)}</em>
                          <small>
                            {fmt({ day: "numeric", month: "short", year: "numeric" }).format(parse(item.day))}
                          </small>
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
                {lines.length > shown.length && (
                  <button type="button" className="earn-more" onClick={() => setShowAll(true)}>
                    Show all {lines.length}
                  </button>
                )}
              </>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}
