import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

async function forward(request: NextRequest, params: Promise<{ id: string }>, method: "GET" | "PATCH") {
  const { id } = await params;
  const result = await authenticatedBackend(`/opportunities/${id}`, {
    ...(method === "PATCH"
      ? { method, headers: { "Content-Type": "application/json" }, body: await request.text() }
      : {}),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return forward(request, params, "GET");
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return forward(request, params, "PATCH");
}
