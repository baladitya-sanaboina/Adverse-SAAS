import type { Metadata } from "next";
import { MailApp } from "@loopless-shared/mail/mail-app";

// Mail in its own tab, without the app's sidebar and topbar (owner request 2026-11-15).
export const metadata: Metadata = { title: "Mail · Adverse" };

export default function MailPage() {
  return <MailApp homeHref="/dashboard" />;
}
