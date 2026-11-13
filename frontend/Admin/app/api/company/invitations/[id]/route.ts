import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";
type Context = { params: Promise<{ id: string }> };
export async function GET(_: NextRequest, context: Context) {
  const result = await authenticatedBackend(`/company/invitations/${(await context.params).id}`);
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
