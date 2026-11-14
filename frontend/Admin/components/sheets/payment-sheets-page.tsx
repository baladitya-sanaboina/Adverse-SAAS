"use client";

/*
 * Payment sheets (owner request 2026-11-14): every manager top-up and client budget top-up opens a
 * sheet; the previous sheet's balance carries over. The Admin tracks all of them here and sees
 * who is running low or needs a top-up. Admin only (the endpoint refuses other roles).
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Contact, RefreshCw, UsersRound, Wallet } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { api, errorText, formatDate, money } from "@/lib/production/client";
import { PaymentSheets } from "@loopless-shared/production/payment-sheets";
import { useLiveRefresh } from "@loopless-shared/realtime/realtime";
import { STATUS_TEXT, ownerLine, type SheetOwner, type SheetsOverview } from "./sheet-types";
import "@/styles/production.css";
import "@/styles/payment-sheets-page.css";

type Tab = "MANAGER" | "CLIENT";

export function PaymentSheetsPage() {
  const [data, setData] = useState<SheetsOverview | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("MANAGER");
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await api<SheetsOverview>("/api/company/finance/sheets"));
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load payment sheets."));
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      if (params.get("tab") === "clients") setTab("CLIENT");
      const owner = params.get("owner");
      if (owner) setSelected(owner);
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useLiveRefresh(["task.", "payout.", "budget.", "payment."], () => void load());

  const owners = useMemo(() => (data ? (tab === "MANAGER" ? data.managers : data.clients) : []), [data, tab]);
  const current = owners.find((owner) => owner.id === selected) ?? owners[0] ?? null;
  const alerts = (list: SheetOwner[]) => list.filter((owner) => owner.status !== "OK").length;
  const currency = data?.currency ?? "INR";

  return (
    <>
      <DashboardHero
        title=""
        highlight="Payment Sheets"
        description="Every top-up opens a new sheet. See what each manager and client has left, and who needs a top-up."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace" aria-live="polite">
          <nav className="production-tabs" aria-label="Payment sheet sections">
            {(
              [
                { id: "MANAGER", label: "Managers", icon: <UsersRound />, list: data?.managers ?? [] },
                { id: "CLIENT", label: "Clients", icon: <Contact />, list: data?.clients ?? [] },
              ] as const
            ).map((item) => (
              <button
                type="button"
                key={item.id}
                className={tab === item.id ? "active" : ""}
                aria-pressed={tab === item.id}
                onClick={() => {
                  setTab(item.id);
                  setSelected(null);
                }}
              >
                {item.icon}
                {item.label}
                {alerts(item.list) > 0 && (
                  <em className="sheets-tab-alert">
                    {alerts(item.list)} {alerts(item.list) === 1 ? "needs" : "need"} attention
                  </em>
                )}
              </button>
            ))}
          </nav>

          {error ? (
            <div className="organization-state">
              <h3>{error}</h3>
              <button type="button" onClick={() => void load()}>
                Retry
              </button>
            </div>
          ) : !data ? (
            <div className="sheets-page-state">
              <RefreshCw className="spin" /> Loading payment sheets…
            </div>
          ) : owners.length === 0 ? (
            <div className="sheets-page-state">
              <Wallet />
              {tab === "MANAGER"
                ? "No manager top-ups yet. Send one in Payments → Manager top-ups; it opens the first sheet."
                : "No client budgets yet. Add one in Payments → Client budgets; it opens the first sheet."}
            </div>
          ) : (
            <div className="sheets-page-grid">
              <ul className="sheets-owner-list" aria-label={tab === "MANAGER" ? "Managers" : "Clients"}>
                {owners.map((owner) => (
                  <li key={owner.id}>
                    <button
                      type="button"
                      className={current?.id === owner.id ? "active" : undefined}
                      aria-pressed={current?.id === owner.id}
                      onClick={() => setSelected(owner.id)}
                    >
                      <span className="sheets-owner-top">
                        <strong>{owner.name}</strong>
                        <em className={`sheets-status ${owner.status.toLowerCase()}`}>{STATUS_TEXT[owner.status]}</em>
                      </span>
                      <span className="sheets-owner-bar" aria-hidden="true">
                        <i
                          style={{ width: `${Math.min(owner.percent_used, 100)}%` }}
                          className={owner.status.toLowerCase()}
                        />
                      </span>
                      <small>
                        Sheet {owner.sheets.length} · {ownerLine(owner, money, currency)}
                      </small>
                    </button>
                  </li>
                ))}
              </ul>
              {current && (
                <article className="sheets-owner-detail">
                  <header>
                    <div>
                      <span>{current.kind === "MANAGER" ? "MANAGER" : "CLIENT"}</span>
                      <h3>{current.name}</h3>
                      <p>
                        {ownerLine(current, money, currency)}
                        {current.ran_out_on ? ` · money ran out on ${formatDate(current.ran_out_on)}` : ""}
                      </p>
                    </div>
                    <Link
                      href={current.kind === "CLIENT" ? `/clients/${current.id}` : "/payments"}
                      className="management-secondary-action"
                    >
                      {current.kind === "CLIENT" ? "Open client" : "Send a top-up"}
                    </Link>
                  </header>
                  <PaymentSheets
                    sheets={current.sheets}
                    currency={currency}
                    money={money}
                    date={formatDate}
                    itemWord={current.kind === "MANAGER" ? "task" : "video"}
                    empty="No sheets yet."
                  />
                </article>
              )}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
