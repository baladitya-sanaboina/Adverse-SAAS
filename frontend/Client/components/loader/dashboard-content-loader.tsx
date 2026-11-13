import "@/styles/dashboard-content-loader.css";

export function DashboardContentLoader() {
  return (
    <div className="dashboard-content-loader" aria-live="polite" aria-busy="true">
      <div className="dashboard-content-loader__body">
        <span className="dashboard-content-loader__spinner" aria-hidden="true" />
        <strong>Loading workspace</strong>
        <span>Please wait a moment</span>
      </div>
    </div>
  );
}
