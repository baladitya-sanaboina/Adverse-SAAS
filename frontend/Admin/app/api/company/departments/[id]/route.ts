import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

async function forward(request: NextRequest, id: string, method: "GET" | "PATCH" | "DELETE") {
  const result = await authenticatedBackend(
    `/company/departments/${id}`,
    method === "GET"
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: method === "PATCH" ? await request.text() : undefined,
        },
  );
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
type Context = { params: Promise<{ id: string }> };
export async function GET(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "GET");
}
export async function PATCH(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "PATCH");
}
export async function DELETE(request: NextRequest, context: Context) {
  return forward(request, (await context.params).id, "DELETE");
}
