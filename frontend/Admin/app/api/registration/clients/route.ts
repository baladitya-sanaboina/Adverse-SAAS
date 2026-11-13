import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

export async function GET() {
  const result = await authenticatedBackend("/registration/clients");
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function POST(request: NextRequest) {
  const result = await authenticatedBackend("/registration/clients", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(await request.json()),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json(), { status: 201 });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
