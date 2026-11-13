import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import type { ReactNode } from "react";
import { adverseBrand } from "@/lib/branding";
import { ThemeScript } from "@/components/theme/theme-script";
import { CompanyBrandingProvider } from "@/components/branding/company-branding-provider";
import { appConfig } from "@/lib/config";
import "../styles/globals.css";

const poppins = Poppins({
  variable: "--font-poppins",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: appConfig.appName,
  description: `${appConfig.appName} application · ${appConfig.environment}`,
  icons: {
    icon: adverseBrand.logos.favicon,
    shortcut: adverseBrand.logos.favicon,
    apple: adverseBrand.logos.favicon,
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={poppins.variable} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body suppressHydrationWarning>
        <CompanyBrandingProvider>{children}</CompanyBrandingProvider>
      </body>
    </html>
  );
}
