// Copy of frontend/shared/branding/orbit-loader.tsx (the Client app has no shared alias). Keep in sync.
/*
 * The loader everywhere (owner request 2026-11-15): the Adverse orbit mark from
 * Logos/adverse-orbit-animation-*.html, without the word mark and faster. The two rings fill
 * round like progress, the centre pulses and the three planets circle, on a 1.6 s loop.
 */
import type { CSSProperties } from "react";
import "@/styles/orbit-loader.css";

export function OrbitLoader({
  size = 64,
  label = "Loading",
  className,
}: {
  size?: number;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={`orbit-loader${className ? ` ${className}` : ""}`}
      role="status"
      aria-label={label}
      style={{ "--orbit-size": `${size}px` } as CSSProperties}
    >
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="orbit-loader-track" cx="50" cy="50" r="38" />
        <circle className="orbit-loader-track" cx="50" cy="50" r="25" />
        <circle className="orbit-loader-ring outer" cx="50" cy="50" r="38" pathLength="1" />
        <circle className="orbit-loader-ring inner" cx="50" cy="50" r="25" pathLength="1" />
        <circle className="orbit-loader-sun" cx="50" cy="50" r="11" />
        <g className="orbit-loader-path p1">
          <circle className="orbit-loader-dot" cx="50" cy="25" r="5.5" />
        </g>
        <g className="orbit-loader-path p2">
          <circle className="orbit-loader-dot" cx="28.4" cy="62.5" r="5.5" />
        </g>
        <g className="orbit-loader-path p3">
          <circle className="orbit-loader-dot" cx="79.1" cy="74.4" r="7" />
        </g>
      </svg>
    </span>
  );
}
