type MetricIcon = "globe" | "eye" | "money" | "bolt";

export function StatCard({
  label,
  value,
  change,
  icon,
  tone,
}: {
  label: string;
  value: string;
  change: string;
  icon: MetricIcon;
  /** Optional: "warning" shows the note in red (e.g. over budget). Default look is unchanged. */
  tone?: "warning";
}) {
  const paths = {
    globe: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
      </>
    ),
    eye: (
      <>
        <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
        <circle cx="12" cy="12" r="2.5" />
      </>
    ),
    money: <path d="M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />,
    bolt: <path d="m13 2-9 12h8l-1 8 9-12h-8l1-8Z" />,
  };
  return (
    <article className={`dash-stat-card${tone ? ` ${tone}` : ""}`}>
      <div className="dash-stat-head">
        <span>{label}</span>
        <i>
          <svg viewBox="0 0 24 24">{paths[icon]}</svg>
        </i>
      </div>
      <strong>{value}</strong>
      <small>{change}</small>
    </article>
  );
}
