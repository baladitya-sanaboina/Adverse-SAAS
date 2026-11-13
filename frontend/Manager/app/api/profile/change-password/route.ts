import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, clearSession } from "@/lib/auth/server";

export async function PUT(request: NextRequest) {
  const result = await authenticatedBackend("/profile/change-password", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  clearSession(response);
  return response;
}
