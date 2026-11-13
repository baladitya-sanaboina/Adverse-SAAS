import { OrganizationPage } from "@/components/organization/organization-page";
import { InvitationsPage } from "@/components/invitations/invitations-page";
import { AnimatedErrorPage } from "@/components/status/AnimatedErrorPage";
import { CompanyUsersPage } from "@/components/users/company-users-page";
import { RoleManagementPage } from "@/components/roles/role-management-page";

export default async function CompanySectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (section === "departments" || section === "branches") return <OrganizationPage kind={section} />;
  if (section === "invitations") return <InvitationsPage />;
  if (section === "users") return <CompanyUsersPage />;
  if (section === "roles") return <RoleManagementPage />;
  return <AnimatedErrorPage />;
}
