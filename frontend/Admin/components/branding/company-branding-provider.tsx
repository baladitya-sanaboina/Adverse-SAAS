"use client";

import { usePathname } from "next/navigation";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import { adverseBrand } from "@/lib/branding";

export type CompanyBranding = {
  company_id: string;
  company_name: string;
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  info_color: string;
  success_color: string;
  warning_color: string;
  danger_color: string;
};

const defaults: CompanyBranding = {
  company_id: "",
  company_name: adverseBrand.name,
  logo_url: null,
  favicon_url: null,
  primary_color: adverseBrand.primary,
  secondary_color: adverseBrand.primaryHover,
  accent_color: adverseBrand.primary,
  info_color: "#2563A6",
  success_color: "#16855B",
  warning_color: "#B7791F",
  danger_color: "#C2414F",
};

const CompanyBrandingContext = createContext(defaults);

const legacyAccentColors = new Set(["#8B6AAF", "#715795", "#3D9BF5"]);

function normalizeHexColor(value: string | null | undefined, fallback: string) {
  const normalized = value?.trim().toUpperCase();
  return normalized && /^#[0-9A-F]{6}$/.test(normalized) ? normalized : fallback;
}

function normalizeBranding(value: CompanyBranding): CompanyBranding {
  const primary = normalizeHexColor(value.primary_color, defaults.primary_color);
  const secondary = normalizeHexColor(value.secondary_color, defaults.secondary_color);
  const accentCandidate = normalizeHexColor(value.accent_color, primary);
  return {
    ...value,
    primary_color: primary,
    secondary_color: secondary,
    accent_color: legacyAccentColors.has(accentCandidate) ? primary : accentCandidate,
    info_color: normalizeHexColor(value.info_color, defaults.info_color),
    success_color: normalizeHexColor(value.success_color, defaults.success_color),
    warning_color: normalizeHexColor(value.warning_color, defaults.warning_color),
    danger_color: normalizeHexColor(value.danger_color, defaults.danger_color),
  };
}

function applyBrandingVariables(value: CompanyBranding) {
  const branding = normalizeBranding(value);
  const root = document.documentElement;
  root.style.setProperty("--company-primary", branding.primary_color);
  root.style.setProperty("--company-secondary", branding.secondary_color);
  root.style.setProperty("--company-accent", branding.accent_color);
  root.style.setProperty("--company-on-primary", "#ffffff");
  root.style.setProperty("--company-info", branding.info_color);
  root.style.setProperty("--company-success", branding.success_color);
  root.style.setProperty("--company-warning", branding.warning_color);
  root.style.setProperty("--company-danger", branding.danger_color);
  root.style.setProperty("--primary", branding.primary_color);
  root.style.setProperty("--primary-hover", branding.secondary_color);
  root.style.setProperty("--primary-foreground", "#ffffff");
  root.style.setProperty("--focus", branding.primary_color);
  root.dataset.companyBranding = branding.company_id;
  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]') ?? document.createElement("link");
  favicon.rel = "icon";
  favicon.href = branding.favicon_url
    ? `/api/company/branding/file?path=${encodeURIComponent(branding.favicon_url)}`
    : adverseBrand.logos.favicon;
  if (!favicon.parentNode) document.head.appendChild(favicon);
}

export function CompanyBrandingProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [branding, setBranding] = useState(defaults);

  useEffect(() => {
    if (
      [
        "/login",
        "/forgot-password",
        "/reset-password",
        "/verify-email",
        "/accept-invitation",
        "/invitations/accept",
      ].some((path) => pathname.startsWith(path))
    )
      return;
    let active = true;
    void fetch("/api/company/branding", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return null;
        return (await response.json()) as CompanyBranding;
      })
      .then((value) => {
        if (!active || !value) return;
        const branding = normalizeBranding(value);
        setBranding(branding);
        applyBrandingVariables(branding);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [pathname]);

  useEffect(() => {
    function applyBranding(event: Event) {
      const value = (event as CustomEvent<CompanyBranding>).detail;
      if (!value) return;
      const branding = normalizeBranding(value);
      setBranding(branding);
      applyBrandingVariables(branding);
    }
    window.addEventListener("loopless-company-branding", applyBranding);
    return () => window.removeEventListener("loopless-company-branding", applyBranding);
  }, []);

  return <CompanyBrandingContext.Provider value={branding}>{children}</CompanyBrandingContext.Provider>;
}

export function useCompanyBranding() {
  return useContext(CompanyBrandingContext);
}
