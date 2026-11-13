import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

async function forward(request: NextRequest, method: "GET" | "POST") {
  const query = request.nextUrl.searchParams.toString();
  const result = await authenticatedBackend(`/company/roles${query ? `?${query}` : ""}`, {
    method,
    ...(method === "POST" ? { headers: { "Content-Type": "application/json" }, body: await request.text() } : {}),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json(), { status: result.response.status });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function GET(request: NextRequest) {
  return forward(request, "GET");
}

export async function POST(request: NextRequest) {
  return forward(request, "POST");
}
