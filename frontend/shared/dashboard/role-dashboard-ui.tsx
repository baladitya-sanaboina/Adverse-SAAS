"use client";

/*
 * Building blocks for the Manager and Employee dashboards, in the style of the Admin dashboard:
 * compact greeting header, KPI tiles, panels, a single-series month chart and status bars.
 */
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import "../styles/production.css";
import "../styles/role-dashboard.css";

export function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export function todayText(): string {
  return new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
}

/** The last `count` months as YYYY-MM keys, oldest first, ending with the current month. */
export function lastMonths(count: number): string[] {
  const now = new Date();
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(now.getFullYear(), now.getMonth() - (count - 1 - index), 1);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  });
}

/** YYYY-MM of a UTC timestamp (stored without a zone marker) in the viewer's time zone. */
export function monthKey(timestamp: string | null): string | null {
  if (!timestamp) return null;
  const date = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(timestamp) ? timestamp : `${timestamp}Z`);
  if (Number.isNaN(date.getTime())) return null;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function monthShort(key: string): string {
  return new Intl.DateTimeFormat("en-IN", { month: "short" }).format(new Date(`${key}-01T00:00:00`));
}

export function DashHeader({ name, subtitle, actions }: { name: string; subtitle: string; actions?: ReactNode }) {
  const first = name.split(/\s+/)[0] ?? "";
  return (
    <header className="production-dash-header">
      <div>
        <h1>
          {greeting()}
          {first ? `, ${first}` : ""}
        </h1>
        <p>{subtitle}</p>
      </div>
      {actions && <div className="production-dash-actions">{actions}</div>}
    </header>
  );
}

export function Tile({
  title,
  value,
  icon,
  children,
  tone,
}: {
  title: string;
  value: string;
  icon: ReactNode;
  children: ReactNode;
  tone?: "negative";
}) {
  return (
    <article className="company-dashboard-kpi production-dash-tile">
      <div>
        <span>{title}</span>
        <i aria-hidden="true">{icon}</i>
      </div>
      <strong className={tone === "negative" ? "negative" : undefined}>{value}</strong>
      <small>{children}</small>
    </article>
  );
}

export function PanelHead({ eyebrow, title, aside }: { eyebrow: string; title: string; aside?: ReactNode }) {
  return (
    <header>
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {aside}
    </header>
  );
}

export function Panel({ children }: { children: ReactNode }) {
  return <article className="company-dashboard-panel production-dash-panel">{children}</article>;
}

/** Single-series bar chart for a few months. `display` is the label printed above each bar. */
export function MonthBars({
  points,
  label,
}: {
  points: { key: string; value: number; display: string }[];
  label: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(560);
  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(260, Math.round(entry.contentRect.width))));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const height = 210;
  const pad = { top: 22, right: 8, bottom: 26, left: 8 };
  const max = Math.max(...points.map((point) => point.value), 0);
  const plotH = height - pad.top - pad.bottom;
  const slot = (width - pad.left - pad.right) / Math.max(points.length, 1);
  const barW = Math.min(44, slot * 0.56);
  const y = (value: number) => pad.top + plotH - (max > 0 ? (value / max) * plotH : 0);
  return (
    <div className="role-chart" ref={box}>
      {max === 0 ? (
        <div className="role-chart-empty">Nothing yet in the last six months.</div>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} height={height} role="img" aria-label={label}>
          {[0.5, 1].map((step) => (
            <line
              key={step}
              className="grid"
              x1={pad.left}
              x2={width - pad.right}
              y1={y(max * step)}
              y2={y(max * step)}
            />
          ))}
          <line className="grid" x1={pad.left} x2={width - pad.right} y1={y(0)} y2={y(0)} />
          {points.map((point, index) => {
            const x = pad.left + slot * index + (slot - barW) / 2;
            const top = y(point.value);
            const last = index === points.length - 1;
            return (
              <g key={point.key}>
                {point.value > 0 && (
                  <rect
                    className={`bar ${last ? "current" : "past"}`}
                    x={x}
                    y={top}
                    width={barW}
                    height={Math.max(2, y(0) - top)}
                    rx={4}
                  >
                    <title>{`${monthShort(point.key)}: ${point.display}`}</title>
                  </rect>
                )}
                {point.value > 0 && (
                  <text className="value" x={x + barW / 2} y={top - 6} textAnchor="middle">
                    {point.display}
                  </text>
                )}
                <text className="axis" x={x + barW / 2} y={height - 8} textAnchor="middle">
                  {monthShort(point.key)}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

/** Horizontal bars per status, each linking to the filtered task page. */
export function StatusBars({
  rows,
  href,
}: {
  rows: { key: string; label: string; count: number }[];
  href: (key: string) => string;
}) {
  const max = Math.max(...rows.map((row) => row.count), 1);
  return (
    <ul className="production-dash-bars" aria-label="Tasks by status">
      {rows.map((row) => (
        <li key={row.key}>
          <Link href={href(row.key)}>
            <span>{row.label}</span>
            <span className="track" aria-hidden="true">
              {row.count > 0 && <i style={{ width: `${(row.count / max) * 100}%` }} />}
            </span>
            <b>{row.count}</b>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function DashLoading() {
  return (
    <div className="company-dashboard-loading" aria-busy="true" aria-label="Loading dashboard">
      <div className="company-dashboard-loading__cards">
        {[1, 2, 3, 4].map((item) => (
          <i key={item} />
        ))}
      </div>
      <div className="company-dashboard-loading__panels">
        <i />
        <i />
      </div>
    </div>
  );
}
