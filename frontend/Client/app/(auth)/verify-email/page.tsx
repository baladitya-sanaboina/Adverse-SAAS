import EmailVerificationPage from "@/components/auth/EmailVerificationPage";
import "@/styles/auth/base.css";
import "@/styles/auth/user-login.css";
import "@/styles/auth/auth-theme.css";
import "@/styles/auth/loopless-purple-theme.css";

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string; email?: string }>;
}) {
  const { token, email } = await searchParams;
  return <EmailVerificationPage token={token} email={email} />;
}
