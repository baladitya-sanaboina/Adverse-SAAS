import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

async function forward(request?: NextRequest) {
  const result = await authenticatedBackend(
    "/company/workflow-settings",
    request ? { method: "PUT", headers: { "Content-Type": "application/json" }, body: await request.text() } : {},
  );
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function GET() {
  return forward();
}

export async function PUT(request: NextRequest) {
  return forward(request);
}
