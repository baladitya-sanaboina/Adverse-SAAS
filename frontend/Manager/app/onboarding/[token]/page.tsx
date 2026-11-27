import { OnboardingPage } from "@loopless-shared/onboarding/onboarding-page";

// The private onboarding link for a new manager (2026-11-27). No sign-in needed.
export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <OnboardingPage token={token} />;
}
