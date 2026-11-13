import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

type Context = { params: Promise<{ id: string }> };

async function forward(request: NextRequest, id: string, method: "GET" | "PATCH") {
  const result = await authenticatedBackend(
    `/company/employees/${id}`,
    method === "GET" ? {} : { method, headers: { "Content-Type": "application/json" }, body: await request.text() },
  );
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function GET(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "GET");
}

export async function PATCH(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "PATCH");
}
