import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

type Context = { params: Promise<{ id: string }> };

async function forward(request: NextRequest, id: string, method: "GET" | "POST") {
  const result = await authenticatedBackend(`/clients/${id}/feedback`, {
    ...(method === "POST"
      ? { method, headers: { "Content-Type": "application/json" }, body: await request.text() }
      : {}),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json(), { status: result.response.status });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function GET(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "GET");
}

export async function POST(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "POST");
}
