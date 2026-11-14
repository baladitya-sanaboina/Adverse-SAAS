import { ErrorState, FoundationPage } from "@/components/foundation/ui-foundation";
import { WorkCalendarPage } from "@loopless-shared/calendar/work-calendar";
import { ChatPage } from "@loopless-shared/chat/chat-page";
import { AnimatedErrorPage } from "@/components/status/AnimatedErrorPage";
import { navigationItems } from "@/lib/navigation";
import { ProfilePage } from "@/components/profile/ProfilePage";
import { NotificationsPage } from "@loopless-shared/notifications/notification-center";
import { ClientManagementPage } from "@/components/clients/client-management-page";
import { CrmPipelinePage } from "@/components/crm/crm-pipeline-page";
import { EmployeeSalaryPage, MyTasksPage } from "@/components/workspace/workspace-pages";

const errors: Record<string, string> = {
  "401": "Unauthorized",
  "403": "Forbidden",
  "404": "Page not found",
  "500": "Server error",
};

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (section === "404") return <AnimatedErrorPage />;
  if (section === "notifications") return <NotificationsPage />;
  if (section === "chat") return <ChatPage role="EMPLOYEE" />;
  if (section === "calendar") return <WorkCalendarPage />;
  if (errors[section]) return <ErrorState code={section} title={errors[section]} />;
  if (section === "profile") return <ProfilePage />;
  if (section === "settings") return <ProfilePage initialTab="settings" />;
  if (section === "clients") return <ClientManagementPage />;
  if (section === "crm") return <CrmPipelinePage />;
  if (section === "tasks") return <MyTasksPage />;
  if (section === "salary") return <EmployeeSalaryPage />;
  const item = navigationItems.find(({ href }) => href === `/${section}`);
  if (!item) return <AnimatedErrorPage />;
  return <FoundationPage title={item.label} />;
}
