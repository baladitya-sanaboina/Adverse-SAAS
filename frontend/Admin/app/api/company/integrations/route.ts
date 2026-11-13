import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

export async function GET() {
  const result = await authenticatedBackend("/company/integrations");
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function PUT(request: NextRequest) {
  const provider = request.nextUrl.searchParams.get("provider");
  if (!provider) return NextResponse.json({ detail: "Provider is required." }, { status: 422 });
  const result = await authenticatedBackend(`/company/integrations/${encodeURIComponent(provider)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function DELETE(request: NextRequest) {
  const provider = request.nextUrl.searchParams.get("provider");
  if (!provider) return NextResponse.json({ detail: "Provider is required." }, { status: 422 });
  const result = await authenticatedBackend(`/company/integrations/${encodeURIComponent(provider)}`, {
    method: "DELETE",
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
