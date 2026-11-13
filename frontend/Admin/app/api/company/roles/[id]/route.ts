import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

async function forward(request: NextRequest, context: { params: Promise<{ id: string }> }, method: string) {
  const { id } = await context.params;
  const result = await authenticatedBackend(`/company/roles/${encodeURIComponent(id)}`, {
    method,
    ...(method === "PATCH" ? { headers: { "Content-Type": "application/json" }, body: await request.text() } : {}),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  return forward(request, context, "GET");
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  return forward(request, context, "PATCH");
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  return forward(request, context, "DELETE");
}
