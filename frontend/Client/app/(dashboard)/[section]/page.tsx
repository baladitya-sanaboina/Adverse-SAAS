import { ErrorState, FoundationPage } from "@/components/foundation/ui-foundation";
import { ChatPage } from "@/components/chat/chat-page";
import { AnimatedErrorPage } from "@/components/status/AnimatedErrorPage";
import { navigationItems } from "@/lib/navigation";
import { ProfilePage } from "@/components/profile/ProfilePage";
import { BillingPage } from "@/components/billing/billing-page";
import { ContentCalendarPage } from "@/components/calendar/content-calendar";
import { NotificationsPage } from "@/components/notifications/notification-center";

const errors: Record<string, string> = {
  "401": "Unauthorized",
  "403": "Forbidden",
  "404": "Page not found",
  "500": "Server error",
};
const companyInternalSections = new Set(["clients", "crm", "roles", "departments", "branches"]);

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (section === "404") return <AnimatedErrorPage />;
  if (section === "notifications") return <NotificationsPage />;
  if (section === "chat") return <ChatPage role="CLIENT" />;
  if (section === "billing") return <BillingPage />;
  if (section === "calendar") return <ContentCalendarPage role="CLIENT" />;
  if (errors[section]) return <ErrorState code={section} title={errors[section]} />;
  if (companyInternalSections.has(section)) {
    return <ErrorState code="403" title="This company workspace area is not available to client accounts" />;
  }
  if (section === "profile") return <ProfilePage />;
  if (section === "settings") return <ProfilePage initialTab="settings" />;
  const item = navigationItems.find(({ href }) => href === `/${section}`);
  if (!item) return <AnimatedErrorPage />;
  return <FoundationPage title={item.label} />;
}
