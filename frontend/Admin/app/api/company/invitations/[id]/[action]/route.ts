import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";
type Context = { params: Promise<{ id: string; action: string }> };
export async function POST(_: NextRequest, context: Context) {
  const { id, action } = await context.params;
  if (!new Set(["resend", "revoke"]).has(action))
    return NextResponse.json({ detail: "Unknown action." }, { status: 404 });
  const result = await authenticatedBackend(`/company/invitations/${id}/${action}`, { method: "POST" });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
