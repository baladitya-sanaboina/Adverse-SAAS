"use client";

import Image from "next/image";
import Link from "next/link";
import { BriefcaseBusiness, CircleDollarSign, Contact, RefreshCw, UsersRound, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { DashboardHero } from "./dashboard-hero";
import { loadCompanyDashboard } from "@/lib/company-dashboard/client";
import type { CompanyDashboard } from "@/lib/company-dashboard/types";

const quickActionPrefixes = ["/employees", "/clients", "/crm", "/settings", "/tasks"];

function isVisibleQuickAction(href: string) {
  return quickActionPrefixes.some((prefix) => href === prefix || href.startsWith(`${prefix}/`) || href.startsWith(`${prefix}?`));
}

function DashboardSkeleton() {
  return (
    <div className="company-dashboard-loading" aria-label="Loading company dashboard" aria-busy="true">
      <div className="company-dashboard-loading__hero" />
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

function relativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
  return new Intl.DateTimeFormat("en", { day: "numeric", month: "short" }).format(new Date(value));
}

function KpiCard({
  title,
  value,
  description,
  emptyDescription,
  href,
  icon: Icon,
}: {
  title: string;
  value: number | string | null;
  description: string;
  emptyDescription: string;
  href?: string;
  icon: LucideIcon;
}) {
  const isEmpty = value === 0;
  const isUnavailable = value == null;
  return (
    <article className={`company-dashboard-kpi${isUnavailable ? " is-unavailable" : ""}`}>
      <div>
        <span>{title}</span>
        <i>
          <Icon aria-hidden="true" />
        </i>
      </div>
      <strong>{isUnavailable ? "—" : value}</strong>
      {isEmpty && href ? (
        <Link href={href}>{emptyDescription}</Link>
      ) : (
        <small>{isEmpty || isUnavailable ? emptyDescription : description}</small>
      )}
    </article>
  );
}

export function DashboardPage() {
  const [dashboard, setDashboard] = useState<CompanyDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await loadCompanyDashboard());
    } catch {
      setError("Something went wrong while loading your company data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void loadCompanyDashboard()
      .then((data) => {
        if (active) setDashboard(data);
      })
      .catch(() => {
        if (active) setError("Something went wrong while loading your company data.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  if (loading) return <DashboardSkeleton />;
  if (error || !dashboard) {
    return (
      <div className="company-dashboard-error" role="alert">
        <RefreshCw aria-hidden="true" />
        <h1>Unable to load dashboard</h1>
        <p>{error}</p>
        <button type="button" onClick={() => void load()}>
          Retry
        </button>
      </div>
    );
  }

  const metrics = [
    {
      title: "Employees",
      value: dashboard.statistics.employees,
      icon: UsersRound,
      description: "Total employees in this company",
      emptyDescription: "No employees yet",
      href: "/employees?mode=create",
    },
    {
      title: "Projects",
      value: dashboard.statistics.projects,
      icon: BriefcaseBusiness,
      description: "Projects recorded for this company",
      emptyDescription: "No projects recorded yet",
    },
    {
      title: "Clients",
      value: dashboard.statistics.clients,
      icon: Contact,
      description: "Total clients in this company",
      emptyDescription: "No clients yet",
      href: "/clients?mode=create",
    },
    {
      title: "Finance",
      value: dashboard.statistics.finance_total,
      icon: CircleDollarSign,
      description: "Current supported financial summary",
      emptyDescription: "Available when Finance launches",
    },
  ];
  const quickActions = dashboard.quick_actions.filter((action) => isVisibleQuickAction(action.href));

  return (
    <>
      <DashboardHero
        title={`Good morning, ${dashboard.current_user.name.split(" ")[0]} · `}
        highlight={dashboard.company.name}
        description="Your tenant-scoped company overview, recent activity, and permitted actions in one place."
        action={
          dashboard.company.logo_url ? (
            <span className="company-dashboard-logo">
              <Image
                unoptimized
                src={`/api/company/dashboard/logo?path=${encodeURIComponent(dashboard.company.logo_url)}`}
                alt={`${dashboard.company.name} logo`}
                width={54}
                height={54}
              />
            </span>
          ) : undefined
        }
      />
      <div className="dash-content company-dashboard-content">
        <section className="company-dashboard-kpis" aria-label="Company summary">
          {metrics.map((metric) => (
            <KpiCard key={metric.title} {...metric} />
          ))}
        </section>
        <section className="company-dashboard-grid">
          <article className="company-dashboard-panel company-dashboard-activity">
            <header>
              <div>
                <span>COMPANY ACTIVITY</span>
                <h2>Recent activity</h2>
              </div>
              <p>Latest events from {dashboard.company.name}</p>
            </header>
            {dashboard.recent_activity.length ? (
              <ol>
                {dashboard.recent_activity.map((activity, index) => (
                  <li key={`${activity.occurred_at}-${index}`}>
                    <i aria-hidden="true" />
                    <div>
                      <strong>{activity.subject}</strong>
                      <p>{activity.description}</p>
                    </div>
                    <time dateTime={activity.occurred_at}>{relativeTime(activity.occurred_at)}</time>
                  </li>
                ))}
              </ol>
            ) : (
              <div className="company-dashboard-empty">
                <h3>No activity yet</h3>
                <p>Company activity will appear here as your team gets started.</p>
              </div>
            )}
          </article>
          <article className="company-dashboard-panel company-dashboard-actions">
            <header>
              <div>
                <span>PERMITTED ACTIONS</span>
                <h2>Quick actions</h2>
              </div>
              <p>Shortcuts based on your access.</p>
            </header>
            {quickActions.length ? (
              <div>
                {quickActions.map((action) => (
                  <Link href={action.href} key={action.href}>
                    <span>+</span>
                    {action.label}
                  </Link>
                ))}
              </div>
            ) : (
              <div className="company-dashboard-empty">
                <h3>No quick actions</h3>
                <p>Your current permissions do not include create actions.</p>
              </div>
            )}
          </article>
        </section>
      </div>
    </>
  );
}
