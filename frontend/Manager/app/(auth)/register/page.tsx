import { redirect } from "next/navigation";
import LoginRegisterPage from "@/components/auth/LoginRegisterPage";
import { authConfig } from "@/lib/auth/config";

export default function RegisterPage() {
  if (!authConfig.signupEnabled) {
    redirect("/login");
  }

  return <LoginRegisterPage initialMode="register" />;
}
