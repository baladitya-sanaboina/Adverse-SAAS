import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

async function forward(request: NextRequest, method: "GET" | "PUT") {
  const result = await authenticatedBackend(
    "/profile",
    method === "GET" ? {} : { method, headers: { "Content-Type": "application/json" }, body: await request.text() },
  );
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
export async function GET(request: NextRequest) {
  return forward(request, "GET");
}
export async function PUT(request: NextRequest) {
  return forward(request, "PUT");
}
