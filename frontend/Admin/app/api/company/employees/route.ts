import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

export async function GET(request: NextRequest) {
  const result = await authenticatedBackend(`/company/employees${request.nextUrl.search}`);
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
