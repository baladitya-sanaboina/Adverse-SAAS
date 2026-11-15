"use client";

/*
 * Payment sheets (owner request 2026-11-14): every manager top-up and client budget top-up opens a
 * sheet; the previous sheet's balance carries over. The Admin tracks all of them here and sees
 * who is running low or needs a top-up. Admin only (the endpoint refuses other roles).
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Contact, Plus, UsersRound, Wallet } from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { api, errorText, formatDate, money } from "@/lib/production/client";
import { PaymentSheets } from "@loopless-shared/production/payment-sheets";
import { useLiveRefresh } from "@loopless-shared/realtime/realtime";
import { SheetInvoiceButton } from "./sheet-invoice-button";
import { STATUS_TEXT, ownerLine, type SheetOwner, type SheetsOverview } from "./sheet-types";
import "@/styles/organization.css";
import "@/styles/production.css";
import "@/styles/payment-sheets-page.css";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";

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
        description="Every payment opens a new sheet: a top-up you send a manager, or a payment a client sends you. See who has money left and who needs a top-up."
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
              <OrbitLoader size={56} label="Loading payment sheets" />
            </div>
          ) : owners.length === 0 ? (
            <div className="sheets-page-state">
              <Wallet />
              {tab === "MANAGER"
                ? "No manager top-ups yet. Send one in Payments → Manager top-ups; it opens the first sheet."
                : "No client payments or delivered work yet. Each payment you record in Payments → Client payments opens a sheet."}
            </div>
          ) : (
            <>
              <div
                className="organization-table sheets-owner-table"
                role="table"
                aria-label={tab === "MANAGER" ? "Managers" : "Clients"}
              >
                <div className="organization-table-head" role="row">
                  <span>{tab === "MANAGER" ? "Manager" : "Client"}</span>
                  <span>Current sheet</span>
                  <span className="production-money">Paid in + carried</span>
                  <span className="production-money">Left</span>
                  <span>Used</span>
                  <span>Status</span>
                </div>
                {owners.map((owner) => {
                  const latest = owner.sheets[owner.sheets.length - 1];
                  const left = Number(owner.left);
                  return (
                    <button
                      type="button"
                      role="row"
                      key={owner.id}
                      className={current?.id === owner.id ? "active" : undefined}
                      aria-selected={current?.id === owner.id}
                      onClick={() => setSelected(owner.id)}
                    >
                      <div className="production-cell">
                        <strong>{owner.name}</strong>
                        <small>{owner.code}</small>
                      </div>
                      <div className="production-cell">
                        <strong>Sheet {latest?.index ?? 1}</strong>
                        <small>{latest ? `Since ${formatDate(latest.start)}` : "No sheet yet"}</small>
                      </div>
                      <span className="production-money">{money(owner.pot, currency)}</span>
                      <span className={`production-money${left < 0 ? " sheets-minus" : ""}`}>
                        {left < 0 ? "−" : ""}
                        {money(Math.abs(left), currency)}
                      </span>
                      <span className="sheets-used">
                        <i aria-hidden="true">
                          <b
                            className={owner.status.toLowerCase()}
                            style={{ width: `${Math.min(owner.percent_used, 100)}%` }}
                          />
                        </i>
                        {Math.round(owner.percent_used)}%
                      </span>
                      <span>
                        <em className={`sheets-status ${owner.status.toLowerCase()}`}>{STATUS_TEXT[owner.status]}</em>
                      </span>
                    </button>
                  );
                })}
              </div>

              {current && (
                <section className="sheets-owner-detail" aria-label={`${current.name} sheets`}>
                  <header className="management-toolbar">
                    <div>
                      <span>
                        {current.kind === "MANAGER" ? "Manager" : "Client"} · {current.name}
                      </span>
                      <strong>
                        {ownerLine(current, money, currency)}
                        {current.ran_out_on ? ` · ran out ${formatDate(current.ran_out_on)}` : ""}
                      </strong>
                    </div>
                    <Link
                      href={current.kind === "CLIENT" ? `/clients/${current.id}` : "/payments"}
                      className="management-primary-action"
                    >
                      {current.kind === "CLIENT" ? (
                        "Open client"
                      ) : (
                        <>
                          <Plus /> Send a top-up
                        </>
                      )}
                    </Link>
                  </header>
                  <PaymentSheets
                    key={current.id}
                    sheets={current.sheets}
                    currency={currency}
                    money={money}
                    date={formatDate}
                    itemWord={current.kind === "MANAGER" ? "task" : "video"}
                    empty="No sheets yet."
                    sheetAction={
                      current.kind === "CLIENT"
                        ? (sheet) => <SheetInvoiceButton sheet={sheet} clientId={current.id} onError={setError} />
                        : undefined
                    }
                  />
                </section>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
