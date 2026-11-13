import { EmployeeProfilePage } from "@/components/employees/employee-profile-page";
import { UserRegistrationPage } from "@/components/registration/user-registration-page";

export default async function EmployeePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return id === "new" ? (
    <UserRegistrationPage kind="employee" initialMode="create" returnHref="/employees" />
  ) : (
    <EmployeeProfilePage employeeId={id} />
  );
}
