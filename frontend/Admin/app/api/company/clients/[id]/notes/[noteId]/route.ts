import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

type Context = { params: Promise<{ id: string; noteId: string }> };

async function forward(request: NextRequest, context: Context, method: "PATCH" | "DELETE") {
  const { id, noteId } = await context.params;
  const result = await authenticatedBackend(`/clients/${id}/notes/${noteId}`, {
    method,
    ...(method === "PATCH" ? { headers: { "Content-Type": "application/json" }, body: await request.text() } : {}),
  });
  if (!result.response.ok) return backendError(result.response);
  const response =
    result.response.status === 204
      ? new NextResponse(null, { status: 204 })
      : NextResponse.json(await result.response.json(), { status: result.response.status });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function PATCH(request: NextRequest, context: Context) {
  return forward(request, context, "PATCH");
}

export async function DELETE(request: NextRequest, context: Context) {
  return forward(request, context, "DELETE");
}
