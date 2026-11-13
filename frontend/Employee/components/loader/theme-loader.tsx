import { adverseBrand } from "@/lib/branding";
import "@/styles/theme-loader.css";

export function ThemeLoader() {
  return (
    <main className="theme-loader" aria-live="polite" aria-busy="true">
      <div className="theme-loader__content">
        <span className="theme-loader__spinner" aria-hidden="true" />
        <span className="theme-loader__label">Loading {adverseBrand.name}</span>
      </div>
    </main>
  );
}
