export const dynamic = "force-dynamic";

type HealthPayload = {
  status?: string;
  version?: string;
  environment?: string;
  services?: Record<string, unknown>;
  [key: string]: unknown;
};

async function loadHealth(): Promise<{ payload: HealthPayload | null; error?: string }> {
  const backendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_HEALTH_URL;
  if (!backendUrl) return { payload: null, error: "Backend health URL is not configured." };
  try {
    const response = await fetch(backendUrl.endsWith("/health") ? backendUrl : `${backendUrl}/health`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return { payload: null, error: `Health check returned ${response.status}.` };
    }
    return { payload: (await response.json()) as HealthPayload };
  } catch {
    return { payload: null, error: "Unable to reach the backend health service." };
  }
}

export default async function BackendHealthPage() {
  const { payload, error } = await loadHealth();
  const services = payload?.services && typeof payload.services === "object" ? payload.services : {};

  return (
    <div className="dash-content">
      <section className="dash-workspace-grid">
        <article className="dash-panel">
          <header>
            <h2>Backend health</h2>
            <p>Live health snapshot for API, auth, storage, and dependencies.</p>
          </header>
          {error ? (
            <div className="interactive-error" role="alert">
              {error}
            </div>
          ) : (
            <div className="dash-modules">
              <div>
                <em>● status</em>
                <h3>{String(payload?.status ?? "unknown").toUpperCase()}</h3>
                <p>Current backend service status</p>
                <strong>{String(payload?.environment ?? "development")}</strong>
              </div>
              <div>
                <em>● version</em>
                <h3>{String(payload?.version ?? "n/a")}</h3>
                <p>Running backend build version</p>
                <strong>{Object.keys(services).length} service checks</strong>
              </div>
            </div>
          )}
        </article>

        <article className="dash-panel">
          <header>
            <h2>Service checks</h2>
            <p>Useful for confirming auth, database, mail, and tenant modules are reachable.</p>
          </header>
          {error ? (
            <p>Retry after the backend is running.</p>
          ) : (
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {JSON.stringify(services, null, 2)}
            </pre>
          )}
        </article>
      </section>
    </div>
  );
}
