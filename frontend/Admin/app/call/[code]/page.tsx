import type { Metadata } from "next";
import { cookies } from "next/headers";
import { authConfig } from "@/lib/auth/config";
import { CallRoom } from "@loopless-shared/chat/call-room";
import { CallSignIn } from "@loopless-shared/chat/call-sign-in";

export const metadata: Metadata = { title: "Call" };

// The call tab (owner request 2026-11-14): full screen, outside the dashboard shell.
export default async function CallPage({
  params,
  searchParams,
}: {
  params: Promise<{ code: string }>;
  searchParams: Promise<{ c?: string; kind?: string }>;
}) {
  const [{ code }, query, store] = await Promise.all([params, searchParams, cookies()]);
  const kind = query.kind === "AUDIO" || query.kind === "VIDEO" ? query.kind : undefined;
  const signedIn = Boolean(store.get(authConfig.accessCookie)?.value || store.get(authConfig.refreshCookie)?.value);
  if (!signedIn) return <CallSignIn code={code} app="admin" kind={kind} />;
  return <CallRoom key={code} code={code} conversationId={query.c} kindHint={kind} />;
}
