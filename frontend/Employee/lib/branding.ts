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
    wordmark: {
      light: "/logos/adverse-logo-transparent-blue.png",
      dark: "/logos/adverse-logo-transparent-white.png",
    },
    orbit: {
      light: "/logos/adverse-orbit-transparent-blue.png",
      dark: "/logos/adverse-orbit-transparent-white.png",
    },
    favicon: "/logos/adverse-orbit-blue-on-white.png",
  },
});

export function getBrandLogo(theme: BrandTheme, variant: BrandLogoVariant): string {
  return adverseBrand.logos[variant][theme === "dark" ? "dark" : "light"];
}
