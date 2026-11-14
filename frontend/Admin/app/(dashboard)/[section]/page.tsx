import { ErrorState, FoundationPage } from "@/components/foundation/ui-foundation";
import { AnimatedErrorPage } from "@/components/status/AnimatedErrorPage";
import { navigationItems } from "@/lib/navigation";
import { ProfilePage } from "@/components/profile/ProfilePage";
import { InvoicesPage } from "@/components/invoices/invoices-page";
import { NotificationsPage } from "@loopless-shared/notifications/notification-center";
import { CompanySettingsPage } from "@/components/settings/company-settings-page";
import { EmployeeDirectoryPage } from "@/components/employees/employee-directory-page";
import { ClientManagementPage } from "@/components/clients/client-management-page";
import { CrmPipelinePage } from "@/components/crm/crm-pipeline-page";
import { TaskManagementPage } from "@/components/tasks/task-management-page";
import { PaymentsPage } from "@/components/payments/payments-page";
import { ReportsPage } from "@/components/reports/reports-page";

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
  if (errors[section]) return <ErrorState code={section} title={errors[section]} />;
  if (section === "employees") return <EmployeeDirectoryPage />;
  if (section === "clients") return <ClientManagementPage />;
  if (section === "crm") return <CrmPipelinePage />;
  if (section === "tasks") return <TaskManagementPage />;
  if (section === "payments") return <PaymentsPage />;
  if (section === "invoices") return <InvoicesPage />;
  if (section === "reports") return <ReportsPage />;
  if (section === "profile") return <ProfilePage />;
  if (section === "settings") return <CompanySettingsPage />;
  const item = navigationItems.find(({ href }) => href === `/${section}`);
  if (!item) return <AnimatedErrorPage />;
  return <FoundationPage title={item.label} />;
}
