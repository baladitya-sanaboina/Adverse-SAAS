export type BrandTheme = "light" | "dark";
export type BrandLogoVariant = "wordmark" | "orbit";

export const adverseBrand = Object.freeze({
  name: "Adverse",
  primary: "#0876ED",
  primaryHover: "#065EC1",
  primarySoft: "#D8ECFF",
  primarySurface: "#EDF6FF",
  white: "#FFFFFF",
  logos: {
    // Trimmed to the logo's edges (the original PNGs carry ~25% empty padding on every side).
    wordmark: {
      light: "/logos/adverse-logo-blue.png",
      dark: "/logos/adverse-logo-white.png",
    },
    // Static SVG of Logos/adverse-orbit-animation-*.html (animation removed, transparent).
    orbit: {
      light: "/logos/adverse-mark-blue.svg",
      dark: "/logos/adverse-mark-white.svg",
    },
    // Transparent favicon: SVG for modern browsers, PNG fallback, 180px for phones.
    favicon: "/logos/adverse-favicon.svg",
    faviconPng: "/logos/adverse-favicon-32.png",
    appleIcon: "/logos/adverse-favicon-180.png",
  },
});

export function getBrandLogo(theme: BrandTheme, variant: BrandLogoVariant): string {
  return adverseBrand.logos[variant][theme === "dark" ? "dark" : "light"];
}
