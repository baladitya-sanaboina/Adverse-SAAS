"use client";

/*
 * Client details → Billing (owner requests 2026-11-15): GST for this client and a monthly package.
 * GST: off by default; when on, every new invoice adds GST at this rate and shows the client's
 * GSTIN. Package: a fixed monthly price that covers a number of videos; videos over that are
 * billed at the client's per-item rate. Packages are never edited: end one and start another,
 * so months already charged keep their price.
 */
import { useCallback, useEffect, useState } from "react";
import { CalendarCheck2, Package, Percent, Plus, Trash2 } from "lucide-react";
import { api, errorText, formatDate, money } from "@/lib/production/client";
import { useLiveRefresh } from "@loopless-shared/realtime/realtime";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";
import "@/styles/client-work.css";

type PackageItem = {
  id: string;
  name: string;
  monthly_price: string;
  videos_included: number;
  starts_on: string;
  ends_on: string | null;
  status: "UPCOMING" | "ACTIVE" | "ENDED";
  used_this_month: number;
  created_by_name: string;
};
type Settings = {
  client_id: string;
  currency: string;
  gst_enabled: boolean;
  gst_rate: string;
  gstin: string;
  company_gstin: string;
  packages: PackageItem[];
};

function isoDay(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function ClientBillingSettings({ clientId }: { clientId: string }) {
  const [data, setData] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [gstOn, setGstOn] = useState(false);
  const [rate, setRate] = useState("18");
  const [gstin, setGstin] = useState("");
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("Monthly package");
  const [price, setPrice] = useState("");
  const [videos, setVideos] = useState("");
  const [startsOn, setStartsOn] = useState(() => isoDay(new Date()));
  const [endOn, setEndOn] = useState("");

  const show = useCallback((next: Settings) => {
    setData(next);
    setGstOn(next.gst_enabled);
    setRate(String(Number(next.gst_rate)));
    setGstin(next.gstin);
  }, []);

  const load = useCallback(async () => {
    try {
      show(await api<Settings>(`/api/company/invoices/billing-settings/${clientId}`));
      setError("");
    } catch (reason) {
      setError(errorText(reason, "Unable to load billing settings."));
    }
  }, [clientId, show]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useLiveRefresh(["task.", "invoice."], () => void load());

  async function run(label: string, action: () => Promise<Settings>, done: string) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      show(await action());
      setNotice(done);
      return true;
    } catch (reason) {
      setError(errorText(reason, "That did not work."));
      return false;
    } finally {
      setBusy("");
    }
  }

  const currency = data?.currency ?? "INR";
  const current = data?.packages.find((item) => item.status === "ACTIVE") ?? null;
  const upcoming = data?.packages.filter((item) => item.status === "UPCOMING") ?? [];
  const ended = data?.packages.filter((item) => item.status === "ENDED") ?? [];
  const gstChanged =
    data !== null && (gstOn !== data.gst_enabled || Number(rate) !== Number(data.gst_rate) || gstin !== data.gstin);

  return (
    <section className="client-pricing client-work client-billing" aria-label="Billing settings">
      <header>
        <div>
          <span>Billing</span>
          <h3>GST and monthly package</h3>
        </div>
      </header>

      {!data && !error ? (
        <div className="client-work-state">
          <OrbitLoader size={48} label="Loading billing settings" />
        </div>
      ) : (
        <div className="client-billing-grid">
          {(error || notice) && (
            <p className={`client-billing-message${error ? " error" : ""}`} role={error ? "alert" : "status"}>
              {error || notice}
            </p>
          )}

          <article>
            <h4>
              <Percent aria-hidden="true" /> GST
            </h4>
            <label className="client-billing-switch">
              <input type="checkbox" checked={gstOn} onChange={(event) => setGstOn(event.target.checked)} />
              <span aria-hidden="true" />
              <strong>{gstOn ? "GST on new invoices" : "No GST"}</strong>
            </label>
            <div className="client-billing-fields">
              <label className="management-field">
                <span>Rate (%)</span>
                <input
                  className="management-input"
                  type="number"
                  min={0}
                  max={100}
                  step={0.01}
                  value={rate}
                  disabled={!gstOn}
                  onChange={(event) => setRate(event.target.value)}
                />
              </label>
              <label className="management-field">
                <span>Client GSTIN</span>
                <input
                  className="management-input"
                  value={gstin}
                  maxLength={20}
                  placeholder="e.g. 36ABCDE1234F1Z5"
                  onChange={(event) => setGstin(event.target.value.replace(/[^0-9a-z]/gi, "").toUpperCase())}
                />
              </label>
            </div>
            <p className="client-billing-note">
              {data?.company_gstin
                ? `Your GSTIN ${data.company_gstin} prints on invoices.`
                : "Add your own GSTIN in Settings → Company so it prints on invoices."}{" "}
              Invoices already made keep the GST they were made with.
            </p>
            <button
              type="button"
              className="management-primary-action"
              disabled={!gstChanged || busy !== ""}
              onClick={() =>
                void run(
                  "gst",
                  () =>
                    api<Settings>(`/api/company/invoices/billing-settings/${clientId}/gst`, {
                      method: "PUT",
                      json: { gst_enabled: gstOn, gst_rate: Number(rate || 0).toFixed(2), gstin },
                    }),
                  gstOn ? `GST at ${Number(rate)}% is on for new invoices.` : "GST is off for new invoices.",
                )
              }
            >
              {busy === "gst" ? "Saving…" : "Save GST"}
            </button>
          </article>

          <article>
            <h4>
              <Package aria-hidden="true" /> Monthly package
            </h4>
            {current ? (
              <div className="client-billing-package">
                <div>
                  <strong>{current.name}</strong>
                  <small>
                    {money(current.monthly_price, currency)} a month · {current.videos_included}{" "}
                    {current.videos_included === 1 ? "video" : "videos"} · since {formatDate(current.starts_on)}
                    {current.ends_on ? ` · ends ${formatDate(current.ends_on)}` : ""}
                  </small>
                </div>
                <span className="client-billing-meter" aria-label="Videos used this month">
                  <i
                    style={{
                      width: `${Math.min(100, (current.used_this_month / Math.max(current.videos_included, 1)) * 100)}%`,
                    }}
                  />
                </span>
                <small>
                  This month: {current.used_this_month} of {current.videos_included} used
                  {current.used_this_month >= current.videos_included
                    ? " · more videos are billed at the per-item rate"
                    : ""}
                </small>
                {!current.ends_on && (
                  <div className="client-billing-end">
                    <label className="management-field">
                      <span>End on</span>
                      <input
                        className="management-input"
                        type="date"
                        min={current.starts_on}
                        value={endOn}
                        onChange={(event) => setEndOn(event.target.value)}
                      />
                    </label>
                    <button
                      type="button"
                      className="management-secondary-action"
                      disabled={!endOn || busy !== ""}
                      onClick={() =>
                        void run(
                          "end",
                          () =>
                            api<Settings>(
                              `/api/company/invoices/billing-settings/${clientId}/packages/${current.id}/end`,
                              { method: "POST", json: { ends_on: endOn } },
                            ),
                          `${current.name} ends on ${formatDate(endOn)}.`,
                        )
                      }
                    >
                      <CalendarCheck2 /> End package
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <p className="client-billing-note">
                No package now: every video is billed at the client&apos;s per-item rate.
              </p>
            )}

            {upcoming.map((item) => (
              <div key={item.id} className="client-billing-row">
                <span>
                  <strong>{item.name}</strong>
                  <small>
                    Starts {formatDate(item.starts_on)} · {money(item.monthly_price, currency)} a month ·{" "}
                    {item.videos_included} videos
                  </small>
                </span>
                <button
                  type="button"
                  className="management-secondary-action"
                  aria-label={`Remove ${item.name}`}
                  disabled={busy !== ""}
                  onClick={() =>
                    void run(
                      "remove",
                      () =>
                        api<Settings>(`/api/company/invoices/billing-settings/${clientId}/packages/${item.id}`, {
                          method: "DELETE",
                        }),
                      `${item.name} removed.`,
                    )
                  }
                >
                  <Trash2 />
                </button>
              </div>
            ))}

            {adding ? (
              <form
                className="client-billing-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void run(
                    "add",
                    () =>
                      api<Settings>(`/api/company/invoices/billing-settings/${clientId}/packages`, {
                        method: "POST",
                        json: {
                          name: name.trim(),
                          monthly_price: Number(price || 0).toFixed(2),
                          videos_included: Number(videos || 0),
                          starts_on: startsOn,
                        },
                      }),
                    `${name.trim()} starts on ${formatDate(startsOn)}.`,
                  ).then((ok) => ok && setAdding(false));
                }}
              >
                <label className="management-field">
                  <span>Name</span>
                  <input
                    className="management-input"
                    value={name}
                    maxLength={120}
                    required
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>
                <label className="management-field">
                  <span>Price a month ({currency})</span>
                  <input
                    className="management-input"
                    type="number"
                    min={0}
                    step={0.01}
                    required
                    value={price}
                    onChange={(event) => setPrice(event.target.value)}
                  />
                </label>
                <label className="management-field">
                  <span>Videos included a month</span>
                  <input
                    className="management-input"
                    type="number"
                    min={0}
                    step={1}
                    required
                    value={videos}
                    onChange={(event) => setVideos(event.target.value)}
                  />
                </label>
                <label className="management-field">
                  <span>Starts on</span>
                  <input
                    className="management-input"
                    type="date"
                    required
                    value={startsOn}
                    onChange={(event) => setStartsOn(event.target.value)}
                  />
                </label>
                <p className="client-billing-note">
                  The price is charged on the start date and then on the 1st of every month. Videos over the number
                  included are billed at the per-item rate.
                </p>
                <div className="client-billing-actions">
                  <button type="button" className="management-secondary-action" onClick={() => setAdding(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="management-primary-action" disabled={busy !== ""}>
                    {busy === "add" ? "Starting…" : "Start package"}
                  </button>
                </div>
              </form>
            ) : (
              <button type="button" className="management-secondary-action" onClick={() => setAdding(true)}>
                <Plus /> {current || upcoming.length ? "Plan the next package" : "Start a package"}
              </button>
            )}

            {ended.length > 0 && (
              <details className="client-billing-history">
                <summary>Past packages · {ended.length}</summary>
                {ended.map((item) => (
                  <div key={item.id} className="client-billing-row">
                    <span>
                      <strong>{item.name}</strong>
                      <small>
                        {formatDate(item.starts_on)} – {item.ends_on ? formatDate(item.ends_on) : ""} ·{" "}
                        {money(item.monthly_price, currency)} a month · {item.videos_included} videos
                      </small>
                    </span>
                  </div>
                ))}
              </details>
            )}
          </article>
        </div>
      )}
    </section>
  );
}
