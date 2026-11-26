"use client";

/*
 * Client access (owner request 2026-11-26): the admin decides, per manager or employee, which
 * clients' work they may see (Read), work on (Write) or add videos for (Create). The server
 * enforces every level; no money is ever shown through this access.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { KeyRound, Search, UsersRound } from "lucide-react";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { api, errorText } from "@/lib/production/client";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";
import "@/styles/organization.css";
import "@/styles/production.css";
import "@/styles/payment-sheets-page.css";
import "@/styles/client-access.css";

type Level = "READ" | "WRITE" | "CREATE";
type Person = { id: string; name: string; role: "MANAGER" | "EMPLOYEE"; code: string };
type Overview = {
  people: Person[];
  clients: { id: string; name: string; code: string }[];
  grants: { user_id: string; client_id: string; level: Level }[];
};

const LEVELS: { value: "" | Level; label: string; detail: string }[] = [
  { value: "", label: "No access", detail: "Sees only tasks assigned to them." },
  { value: "READ", label: "Read", detail: "Sees this client's tickets and content calendar." },
  { value: "WRITE", label: "Write", detail: "Also changes status (up to Review), comments and uploads files." },
  { value: "CREATE", label: "Create", detail: "Also adds videos to the client's calendar; the ticket is theirs." },
];

export function ClientAccessPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [person, setPerson] = useState("");
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const overview = await api<Overview>("/api/company/client-access");
      setData(overview);
      setPerson((current) => current || overview.people[0]?.id || "");
    } catch (requestError) {
      setError(errorText(requestError, "Unable to load client access."));
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const levels = useMemo(() => {
    const map = new Map<string, Level>();
    data?.grants.filter((grant) => grant.user_id === person).forEach((grant) => map.set(grant.client_id, grant.level));
    return map;
  }, [data, person]);

  const counts = useMemo(() => {
    const map = new Map<string, number>();
    data?.grants.forEach((grant) => map.set(grant.user_id, (map.get(grant.user_id) ?? 0) + 1));
    return map;
  }, [data]);

  const clients = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (data?.clients ?? []).filter(
      (client) => !term || `${client.name} ${client.code}`.toLowerCase().includes(term),
    );
  }, [data, search]);

  const chosen = data?.people.find((item) => item.id === person) ?? null;

  async function change(clientId: string, clientName: string, level: string) {
    if (!chosen) return;
    setSaving(clientId);
    setNotice("");
    try {
      setData(
        await api<Overview>("/api/company/client-access", {
          method: "PUT",
          json: { user_id: chosen.id, client_id: clientId, level: level || null },
        }),
      );
      const label = LEVELS.find((item) => item.value === level)?.label ?? "No access";
      setNotice(
        level
          ? `${chosen.name} now has ${label} access to ${clientName} and is in ${clientName}'s team chat.`
          : `${chosen.name} no longer has access to ${clientName}.`,
      );
    } catch (requestError) {
      setNotice(errorText(requestError, "Could not change the access."));
    } finally {
      setSaving(null);
    }
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight="Client Access"
        description="Choose which clients each manager or employee can see, work on or add videos for. Prices and pay are never shown through this access."
        compact
      />
      <div className="dash-content">
        <section className="organization-workspace production-workspace" aria-live="polite">
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
              <OrbitLoader size={56} label="Loading client access" />
            </div>
          ) : data.people.length === 0 || data.clients.length === 0 ? (
            <div className="sheets-page-state">
              <UsersRound />
              {data.people.length === 0
                ? "No managers or employees yet. Invite them from Employees first."
                : "No active clients yet."}
            </div>
          ) : (
            <>
              <div className="organization-tools client-access-tools">
                <LooplessSelect
                  value={person}
                  onValueChange={setPerson}
                  ariaLabel="Manager or employee"
                  options={data.people.map((item) => ({
                    value: item.id,
                    label: `${item.name} · ${item.role === "MANAGER" ? "Manager" : "Employee"} · ${
                      counts.get(item.id) ?? 0
                    } ${(counts.get(item.id) ?? 0) === 1 ? "client" : "clients"}`,
                  }))}
                />
                <label>
                  <Search />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search clients by name or code"
                    aria-label="Search clients"
                  />
                </label>
              </div>

              <ul className="client-access-legend" aria-label="What each level allows">
                {LEVELS.slice(1).map((item) => (
                  <li key={item.value}>
                    <em className={`client-access-level ${item.value.toLowerCase()}`}>{item.label}</em>
                    {item.detail}
                  </li>
                ))}
              </ul>

              {chosen && (
                <p className="client-access-summary">
                  <KeyRound aria-hidden="true" />
                  <strong>{chosen.name}</strong>
                  {levels.size === 0
                    ? " has no client access yet: only the tasks assigned to them."
                    : ` has access to ${levels.size} of ${data.clients.length} clients.`}
                </p>
              )}

              <div className="organization-table client-access-table" role="table" aria-label="Client access">
                <div className="organization-table-head" role="row">
                  <span>Client</span>
                  <span>Access</span>
                  <span>What they can do</span>
                </div>
                {clients.length === 0 && <p className="sheets-no-match">No clients match this search.</p>}
                {clients.map((client) => {
                  const level = levels.get(client.id) ?? "";
                  const info = LEVELS.find((item) => item.value === level) ?? LEVELS[0];
                  return (
                    <article role="row" key={client.id} className={level ? "has-access" : undefined}>
                      <div className="production-cell">
                        <strong>{client.name}</strong>
                        <small>{client.code}</small>
                      </div>
                      <div className="client-access-select">
                        <LooplessSelect
                          value={level}
                          disabled={saving === client.id}
                          onValueChange={(value) => void change(client.id, client.name, value)}
                          ariaLabel={`${chosen?.name ?? "Person"}'s access to ${client.name}`}
                          options={LEVELS.map((item) => ({ value: item.value, label: item.label }))}
                        />
                      </div>
                      <span className="client-access-detail">{saving === client.id ? "Saving…" : info.detail}</span>
                    </article>
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
