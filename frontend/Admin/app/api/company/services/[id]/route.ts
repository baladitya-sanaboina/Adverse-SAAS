import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

type Context = { params: Promise<{ id: string }> };

async function forward(request: NextRequest, id: string, method: "GET" | "PATCH" | "DELETE") {
  const result = await authenticatedBackend(`/company/services/${id}`, {
    ...(method === "PATCH"
      ? { method, headers: { "Content-Type": "application/json" }, body: await request.text() }
      : method === "DELETE"
        ? { method }
        : {}),
  });
  if (!result.response.ok) return backendError(result.response);
  const response =
    method === "DELETE"
      ? new NextResponse(null, { status: result.response.status })
      : NextResponse.json(await result.response.json(), { status: result.response.status });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function GET(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "GET");
}

export async function PATCH(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "PATCH");
}

export async function DELETE(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "DELETE");
}
