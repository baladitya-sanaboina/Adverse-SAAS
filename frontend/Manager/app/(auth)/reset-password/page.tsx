import PasswordRecoveryPage from "@/components/auth/PasswordRecoveryPage";

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string; email?: string }>;
}) {
  const { token = "", email = "" } = await searchParams;
  return <PasswordRecoveryPage mode="reset" token={token} email={email} />;
}
