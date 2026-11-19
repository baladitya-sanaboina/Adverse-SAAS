"use client";

/*
 * The app's own date picker (owner request 2026-11-19: no browser calendar, and the calendar icon
 * must show in dark mode). Same look as LooplessSelect. Values are "YYYY-MM-DD" (or "YYYY-MM" with
 * mode="month"), exactly like the native inputs it replaces. Keep the four app copies identical.
 */
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

const MONTHS = [
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
const DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

const pad = (value: number) => String(value).padStart(2, "0");
const iso = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

function parse(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(value || "");
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3] ?? "1"));
}

function label(value: string, mode: "date" | "month"): string {
  const date = parse(value);
  if (!date) return "";
  const month = MONTHS[date.getMonth()];
  return mode === "month"
    ? `${month} ${date.getFullYear()}`
    : `${pad(date.getDate())} ${month.slice(0, 3)} ${date.getFullYear()}`;
}

export function LooplessDate({
  value,
  onValueChange,
  ariaLabel,
  min,
  max,
  mode = "date",
  placeholder,
  disabled = false,
  clearable = true,
  id,
  defaultOpen = false,
  onClose,
}: {
  value: string;
  onValueChange: (value: string) => void;
  ariaLabel: string;
  min?: string;
  max?: string;
  mode?: "date" | "month";
  placeholder?: string;
  disabled?: boolean;
  clearable?: boolean;
  id?: string;
  /** Open straight away, e.g. when a sheet cell starts editing. */
  defaultOpen?: boolean;
  /** Called when the picker closes without a choice (click outside or Esc). */
  onClose?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [above, setAbove] = useState(false);
  const [view, setView] = useState(() => parse(value) ?? new Date());
  const [focus, setFocus] = useState<Date | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const popupId = useId();
  const selected = parse(value);
  const today = new Date();
  const lower = min ? (mode === "month" ? min.slice(0, 7) : min) : "";
  const upper = max ? (mode === "month" ? max.slice(0, 7) : max) : "";
  const allowed = (key: string) => (!lower || key >= lower) && (!upper || key <= upper);
  const todayKey = mode === "month" ? iso(today).slice(0, 7) : iso(today);

  const closed = useRef(onClose);
  useEffect(() => {
    closed.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (root.current?.contains(event.target as Node)) return;
      setOpen((wasOpen) => {
        if (wasOpen) closed.current?.();
        return false;
      });
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  const show = () => {
    if (disabled) return;
    const start = parse(value) ?? new Date();
    setView(new Date(start.getFullYear(), start.getMonth(), 1));
    setFocus(start);
    const box = root.current?.getBoundingClientRect();
    setAbove(Boolean(box && box.bottom + 360 > window.innerHeight && box.top > 360));
    setOpen(true);
  };

  const autoOpened = useRef(false);
  useEffect(() => {
    if (!defaultOpen || autoOpened.current) return;
    autoOpened.current = true;
    const timer = window.setTimeout(show, 0);
    return () => window.clearTimeout(timer);
  });

  const choose = (next: string) => {
    if (!allowed(next)) return;
    onValueChange(next);
    setOpen(false);
  };

  const cells = useMemo(() => {
    const first = new Date(view.getFullYear(), view.getMonth(), 1);
    const offset = (first.getDay() + 6) % 7; // weeks start on Monday
    return Array.from({ length: 42 }, (_, index) => new Date(view.getFullYear(), view.getMonth(), index - offset + 1));
  }, [view]);

  const move = (days: number) => {
    const base = focus ?? selected ?? new Date();
    const next = new Date(base.getFullYear(), base.getMonth(), base.getDate() + days);
    setFocus(next);
    setView(new Date(next.getFullYear(), next.getMonth(), 1));
  };

  const shift = (step: number) =>
    setView((current) =>
      mode === "month"
        ? new Date(current.getFullYear() + step, current.getMonth(), 1)
        : new Date(current.getFullYear(), current.getMonth() + step, 1),
    );

  return (
    <div className={`loopless-date ${open ? "open" : ""}`} ref={root}>
      <button
        type="button"
        id={id}
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={popupId}
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setOpen(false);
            onClose?.();
          }
          if (!open && (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            show();
            return;
          }
          if (!open || mode === "month") return;
          const steps: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
          if (event.key in steps) {
            event.preventDefault();
            move(steps[event.key]);
          }
          if ((event.key === "Enter" || event.key === " ") && focus) {
            event.preventDefault();
            choose(iso(focus));
          }
        }}
      >
        <span className={value ? undefined : "placeholder"}>
          {label(value, mode) || placeholder || (mode === "month" ? "Pick a month" : "Pick a date")}
        </span>
        <CalendarDays aria-hidden="true" />
      </button>
      {open && (
        <div id={popupId} role="dialog" aria-label={ariaLabel} className={above ? "above" : undefined}>
          <header>
            <button
              type="button"
              aria-label={mode === "month" ? "Previous year" : "Previous month"}
              onClick={() => shift(-1)}
            >
              <ChevronLeft />
            </button>
            <strong>
              {mode === "month" ? view.getFullYear() : `${MONTHS[view.getMonth()]} ${view.getFullYear()}`}
            </strong>
            <button type="button" aria-label={mode === "month" ? "Next year" : "Next month"} onClick={() => shift(1)}>
              <ChevronRight />
            </button>
          </header>
          {mode === "month" ? (
            <div className="months">
              {MONTHS.map((name, index) => {
                const key = `${view.getFullYear()}-${pad(index + 1)}`;
                const classes = [value === key ? "chosen" : "", key === todayKey ? "today" : ""].filter(Boolean);
                return (
                  <button
                    type="button"
                    key={key}
                    disabled={!allowed(key)}
                    className={classes.join(" ") || undefined}
                    onClick={() => choose(key)}
                  >
                    {name.slice(0, 3)}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="days" role="grid">
              {DAYS.map((day) => (
                <span key={day} className="weekday" aria-hidden="true">
                  {day}
                </span>
              ))}
              {cells.map((day) => {
                const key = iso(day);
                const classes = [
                  day.getMonth() !== view.getMonth() ? "outside" : "",
                  key === todayKey ? "today" : "",
                  selected && key === iso(selected) ? "chosen" : "",
                  focus && key === iso(focus) ? "focus" : "",
                ].filter(Boolean);
                return (
                  <button
                    type="button"
                    role="gridcell"
                    key={key}
                    disabled={!allowed(key)}
                    aria-selected={Boolean(selected && key === iso(selected))}
                    aria-label={label(key, "date")}
                    className={classes.join(" ") || undefined}
                    onClick={() => choose(key)}
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>
          )}
          <footer>
            <button type="button" onClick={() => choose(todayKey)} disabled={!allowed(todayKey)}>
              {mode === "month" ? "This month" : "Today"}
            </button>
            {clearable && value && (
              <button
                type="button"
                onClick={() => {
                  onValueChange("");
                  setOpen(false);
                }}
              >
                Clear
              </button>
            )}
          </footer>
        </div>
      )}
      <style jsx>{`
        .loopless-date {
          position: relative;
          min-width: 150px;
          color: var(--foreground);
          font-family: var(--font-poppins), Arial, sans-serif;
        }
        .loopless-date > button {
          width: 100%;
          min-height: 42px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 0 13px;
          border: 1px solid var(--border);
          border-radius: 10px;
          color: var(--foreground);
          background: var(--surface);
          font:
            600 0.74rem/1.2 var(--font-poppins),
            Arial,
            sans-serif;
          text-align: left;
          cursor: pointer;
        }
        .loopless-date > button .placeholder {
          color: var(--muted);
          font-weight: 500;
        }
        .loopless-date.open > button,
        .loopless-date > button:hover,
        .loopless-date > button:focus-visible {
          border-color: #0876ed;
          box-shadow: 0 0 0 3px #0876ed16;
          outline: 0;
        }
        .loopless-date > button:disabled {
          opacity: 0.55;
          cursor: not-allowed;
        }
        .loopless-date > button :global(svg) {
          width: 17px;
          height: 17px;
          flex: 0 0 auto;
          color: #0876ed;
        }
        .loopless-date > div {
          position: absolute;
          z-index: 130;
          top: calc(100% + 7px);
          left: 0;
          width: 280px;
          padding: 10px;
          border: 1px solid var(--border);
          border-radius: 12px;
          background: var(--surface);
          box-shadow: 0 18px 42px #25172f24;
        }
        .loopless-date > div.above {
          top: auto;
          bottom: calc(100% + 7px);
        }
        header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 8px;
        }
        header strong {
          font-size: 0.74rem;
          font-weight: 700;
        }
        header button {
          width: 30px;
          height: 30px;
          display: grid;
          place-items: center;
          border: 1px solid var(--border);
          border-radius: 8px;
          color: var(--foreground);
          background: var(--surface);
          cursor: pointer;
        }
        header button:hover {
          border-color: #0876ed;
          color: #0876ed;
        }
        header button :global(svg) {
          width: 15px;
          height: 15px;
        }
        .days {
          display: grid;
          grid-template-columns: repeat(7, 1fr);
          gap: 2px;
        }
        .weekday {
          padding: 4px 0;
          color: var(--muted);
          font-size: 0.6rem;
          font-weight: 700;
          text-align: center;
        }
        .days button,
        .months button {
          height: 34px;
          border: 1px solid transparent;
          border-radius: 8px;
          color: var(--foreground);
          background: transparent;
          font:
            600 0.68rem var(--font-poppins),
            Arial,
            sans-serif;
          cursor: pointer;
        }
        .days button.outside {
          color: var(--muted);
          opacity: 0.6;
        }
        .days button.today,
        .months button.today {
          border-color: #0876ed66;
        }
        .days button.focus {
          background: var(--surface-muted);
        }
        .days button:hover:not(:disabled),
        .months button:hover:not(:disabled) {
          color: #065ec1;
          background: var(--surface-muted);
        }
        .days button.chosen,
        .months button.chosen {
          color: #fff;
          background: #0876ed;
        }
        .days button:disabled,
        .months button:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }
        .months {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 6px;
        }
        footer {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid var(--border);
        }
        footer button {
          min-height: 30px;
          padding: 0 10px;
          border: 0;
          border-radius: 8px;
          color: #0876ed;
          background: transparent;
          font:
            700 0.66rem var(--font-poppins),
            Arial,
            sans-serif;
          cursor: pointer;
        }
        footer button:hover:not(:disabled) {
          background: var(--surface-muted);
        }
        footer button:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
        :global(.dark) .days button:hover:not(:disabled),
        :global(.dark) .months button:hover:not(:disabled) {
          color: #8cc8ff;
        }
        @media (max-width: 700px) {
          .loopless-date {
            width: 100%;
          }
          .loopless-date > div {
            width: min(280px, calc(100vw - 32px));
          }
        }
      `}</style>
    </div>
  );
}
