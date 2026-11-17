import { InvitationAcceptancePage } from "@/components/invitations/invitation-acceptance-page";

export default async function AcceptInvitationPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token = "" } = await searchParams;
  return <InvitationAcceptancePage token={token} />;
}
