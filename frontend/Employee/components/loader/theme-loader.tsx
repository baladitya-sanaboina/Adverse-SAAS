import { adverseBrand } from "@/lib/branding";
import "@/styles/theme-loader.css";
import { OrbitLoader } from "@loopless-shared/branding/orbit-loader";

export function ThemeLoader() {
  return (
    <main className="theme-loader" aria-live="polite" aria-busy="true">
      <div className="theme-loader__content">
        <OrbitLoader size={88} label={`Loading ${adverseBrand.name}`} />
      </div>
    </main>
  );
}
