import { OnboardingPage } from "@/components/onboarding/onboarding-page";

// The private link for a new client's onboarding form and agreement (2026-11-15). No sign-in.
export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <OnboardingPage token={token} />;
}
