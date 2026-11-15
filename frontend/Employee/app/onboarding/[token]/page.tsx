import { OnboardingPage } from "@loopless-shared/onboarding/onboarding-page";

// The private link for a new team member's documents (2026-11-15). No sign-in needed.
export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <OnboardingPage token={token} />;
}
