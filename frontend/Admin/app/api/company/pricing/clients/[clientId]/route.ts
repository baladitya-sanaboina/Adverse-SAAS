import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

type Context = { params: Promise<{ clientId: string }> };

export async function GET(request: NextRequest, context: Context) {
  const { clientId } = await context.params;
  const result = await authenticatedBackend(`/company/services/pricing/clients/${clientId}${request.nextUrl.search}`);
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json(), { status: result.response.status });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
