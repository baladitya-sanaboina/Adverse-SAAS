import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

type Context = { params: Promise<{ managerId: string; serviceId: string }> };

export async function PUT(request: NextRequest, context: Context) {
  const { managerId, serviceId } = await context.params;
  const result = await authenticatedBackend(`/company/services/pricing/managers/${managerId}/services/${serviceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json(), { status: result.response.status });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
