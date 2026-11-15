import "@/styles/dashboard-content-loader.css";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";

export function DashboardContentLoader() {
  return (
    <div className="dashboard-content-loader" aria-live="polite" aria-busy="true">
      <div className="dashboard-content-loader__body">
        <OrbitLoader size={76} label="Loading workspace" />
      </div>
    </div>
  );
}
