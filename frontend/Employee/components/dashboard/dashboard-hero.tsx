import type { ReactNode } from "react";

interface DashboardHeroProps {
  title: string;
  highlight: string;
  description: string;
  action?: ReactNode;
  compact?: boolean;
}

export function DashboardHero({ title, highlight, description, action, compact = false }: DashboardHeroProps) {
  return (
    <section className={`dash-hero${compact ? " dash-about-hero" : ""}`}>
      <div className="dash-grid" aria-hidden="true" />
      <div className="dash-hero-content">
        <h1>
          {title}
          <span>{highlight}</span>
        </h1>
        <p>{description}</p>
        {action}
      </div>
    </section>
  );
}
