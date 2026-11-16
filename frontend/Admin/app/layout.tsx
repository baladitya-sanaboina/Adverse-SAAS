import type { Metadata } from "next";
import type { ReactNode } from "react";
import { adverseBrand } from "@/lib/branding";
import { ThemeScript } from "@/components/theme/theme-script";
import { CompanyBrandingProvider } from "@/components/branding/company-branding-provider";
import { appConfig } from "@/lib/config";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: appConfig.appName,
  description: `${appConfig.appName} application · ${appConfig.environment}`,
  icons: {
    icon: [
      { url: adverseBrand.logos.favicon, type: "image/svg+xml" },
      { url: adverseBrand.logos.faviconPng, sizes: "32x32", type: "image/png" },
    ],
    shortcut: adverseBrand.logos.faviconPng,
    apple: adverseBrand.logos.appleIcon,
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body suppressHydrationWarning>
        <CompanyBrandingProvider>{children}</CompanyBrandingProvider>
      </body>
    </html>
  );
}
