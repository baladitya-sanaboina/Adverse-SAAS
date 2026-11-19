"use client";

/*
 * Payment sheets (owner request 2026-11-14): every manager top-up and client budget top-up opens a
 * sheet; the previous sheet's balance carries over. The Admin tracks all of them here and sees
 * who is running low or needs a top-up. Admin only (the endpoint refuses other roles).
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ChevronRight, Contact, FileDown, Plus, Search, UsersRound, Wallet } from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { api, errorText, formatDate, money } from "@/lib/production/client";
import { PaymentSheets } from "@loopless-shared/production/payment-sheets";
import { useLiveRefresh } from "@loopless-shared/realtime/realtime";
import { SheetEmailButton, SheetInvoiceButton } from "./sheet-invoice-button";
import { STATUS_TEXT, ownerLine, type SheetOwner, type SheetsOverview } from "./sheet-types";
import "@/styles/organization.css";
import "@/styles/production.css";
import "@/styles/payment-sheets-page.css";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";

type Tab = "MANAGER" | "CLIENT";

/** Reads ?tab=clients&owner=<id> so a link (or the browser Back button) opens the right view. */
function fromUrl(): { tab: Tab; owner: string | null } {
  const params = new URLSearchParams(window.location.search);
  return { tab: params.get("tab") === "clients" ? "CLIENT" : "MANAGER", owner: params.get("owner") };
}

function toUrl(tab: Tab, owner: string | null) {
  const params = new URLSearchParams();
  if (tab === "CLIENT") params.set("tab", "clients");
  if (owner) params.set("owner", owner);
  const query = params.toString();
  window.history.pushState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

/*
 * Owner request 2026-11-19: first a clean list of people; clicking one opens only that person's
 * sheets. Each later sheet starts with what was left on the one before.
 */
export function PaymentSheetsPage() {
  const [data, setData] = useState<SheetsOverview | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<Tab>("MANAGER");
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [show, setShow] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await api<SheetsOverview>("/api/company/finance/sheets"));
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load payment sheets."));
    }
  }, []);

  useEffect(() => {
    const sync = () => {
      const state = fromUrl();
      setTab(state.tab);
      setSelected(state.owner);
    };
    const timer = window.setTimeout(() => {
      sync();
      void load();
    }, 0);
    window.addEventListener("popstate", sync);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("popstate", sync);
    };
  }, [load]);

  useLiveRefresh(["task.", "payout.", "budget.", "payment."], () => void load());

  const owners = useMemo(() => (data ? (tab === "MANAGER" ? data.managers : data.clients) : []), [data, tab]);
  const current = selected ? (owners.find((owner) => owner.id === selected) ?? null) : null;
  const shown = useMemo(() => {
    const term = search.trim().toLowerCase();
    return owners.filter((owner) => {
      if (show === "attention" && owner.status === "OK") return false;
      if (show === "ok" && owner.status !== "OK") return false;
      return !term || `${owner.name} ${owner.code}`.toLowerCase().includes(term);
    });
  }, [owners, search, show]);
  const alerts = (list: SheetOwner[]) => list.filter((owner) => owner.status !== "OK").length;
  const currency = data?.currency ?? "INR";
  const people = tab === "MANAGER" ? "managers" : "clients";

  const open = (owner: string | null) => {
    setSelected(owner);
    setNotice("");
    toUrl(tab, owner);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <>
      <DashboardHero
        title=""
        highlight="Payment Sheets"
        description="Every payment opens a new sheet. Whatever is left on a sheet moves into the next one, so each sheet starts with the old balance plus the new payment."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace" aria-live="polite">
          {!current && (
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
                    toUrl(item.id, null);
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
          )}

          {notice && (
            <p className="sheets-notice" role="status">
              {notice}
              <button type="button" aria-label="Dismiss" onClick={() => setNotice("")}>
                ×
              </button>
            </p>
          )}
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
          ) : current ? (
            <section className="sheets-owner-detail" aria-label={`${current.name} sheets`}>
              <header className="management-toolbar">
                <button type="button" className="management-back" onClick={() => open(null)}>
                  <ArrowLeft /> Back to {people}
                </button>
                <div className="sheets-detail-title">
                  <span>
                    {current.kind === "MANAGER" ? "Manager" : "Client"} · {current.code} · {current.sheets.length}{" "}
                    {current.sheets.length === 1 ? "sheet" : "sheets"}
                  </span>
                  <strong>{current.name}</strong>
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
              <p className="sheets-detail-line">
                <em className={`sheets-status ${current.status.toLowerCase()}`}>{STATUS_TEXT[current.status]}</em>
                {ownerLine(current, money, currency)}
                {current.ran_out_on ? ` · ran out ${formatDate(current.ran_out_on)}` : ""}
              </p>
              <PaymentSheets
                key={current.id}
                sheets={current.sheets}
                currency={currency}
                money={money}
                date={formatDate}
                itemWord={current.kind === "MANAGER" ? "task" : "video"}
                empty="No sheets yet."
                sheetAction={(sheet) => (
                  <>
                    {current.kind === "CLIENT" && (
                      <SheetInvoiceButton sheet={sheet} clientId={current.id} onError={setNotice} />
                    )}
                    <SheetEmailButton
                      sheet={sheet}
                      kind={current.kind}
                      ownerId={current.id}
                      onDone={(message) => setNotice(message)}
                    />
                    {current.kind === "MANAGER" && (
                      <a
                        className="secondary"
                        href={`/api/company/finance/sheets/managers/${current.id}/${sheet.index}/statement.pdf`}
                        download
                      >
                        <FileDown aria-hidden="true" /> Download PDF
                      </a>
                    )}
                  </>
                )}
              />
            </section>
          ) : owners.length === 0 ? (
            <div className="sheets-page-state">
              <Wallet />
              {tab === "MANAGER"
                ? "No manager top-ups yet. Send one in Payments → Manager top-ups; it opens the first sheet."
                : "No client payments or delivered work yet. Each payment you record in Payments → Client payments opens a sheet."}
            </div>
          ) : (
            <>
              <div className="organization-tools sheets-tools">
                <label>
                  <Search />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder={`Search ${people} by name or code`}
                    aria-label={`Search ${people}`}
                  />
                </label>
                <LooplessSelect
                  value={show}
                  onValueChange={setShow}
                  ariaLabel={`Filter ${people}`}
                  options={[
                    { value: "", label: `All ${people}` },
                    { value: "attention", label: "Needs attention" },
                    { value: "ok", label: "OK" },
                  ]}
                />
              </div>
              <div
                className="organization-table sheets-owner-table"
                role="table"
                aria-label={tab === "MANAGER" ? "Managers" : "Clients"}
              >
                <div className="organization-table-head" role="row">
                  <span>{tab === "MANAGER" ? "Manager" : "Client"}</span>
                  <span>Current sheet</span>
                  <span className="production-money">Money left</span>
                  <span>Used</span>
                  <span>Status</span>
                  <span aria-hidden="true" />
                </div>
                {shown.length === 0 && <p className="sheets-no-match">No {people} match this search.</p>}
                {shown.map((owner) => {
                  const latest = owner.sheets[owner.sheets.length - 1];
                  const left = Number(owner.left);
                  return (
                    <button
                      type="button"
                      role="row"
                      key={owner.id}
                      onClick={() => open(owner.id)}
                      aria-label={`Open ${owner.name} sheets`}
                    >
                      <div className="production-cell">
                        <strong>{owner.name}</strong>
                        <small>{owner.code}</small>
                      </div>
                      <div className="production-cell">
                        <strong>
                          Sheet {latest?.index ?? 1}
                          {owner.sheets.length > 1 ? ` of ${owner.sheets.length}` : ""}
                        </strong>
                        <small>{latest ? `Since ${formatDate(latest.start)}` : "No sheet yet"}</small>
                      </div>
                      <div className="production-cell production-money">
                        <strong className={left < 0 ? "sheets-minus" : undefined}>
                          {left < 0 ? "−" : ""}
                          {money(Math.abs(left), currency)}
                        </strong>
                        <small>of {money(owner.pot, currency)}</small>
                      </div>
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
                      <ChevronRight className="sheets-row-open" aria-hidden="true" />
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
