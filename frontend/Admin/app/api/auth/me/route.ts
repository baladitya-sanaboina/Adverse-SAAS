import { NextResponse } from "next/server";
import { authConfig } from "@/lib/auth/config";
import { backendError, clearSession, currentUserWithRefresh, setSession } from "@/lib/auth/server";
import type { CurrentUser } from "@/lib/auth/types";

export async function GET() {
  const result = await currentUserWithRefresh();
  if (!result.response.ok) {
    const error = await backendError(result.response);
    clearSession(error);
    return error;
  }
  const user = (await result.response.json()) as CurrentUser;
  if (user.role.code !== authConfig.allowedRole) {
    const error = NextResponse.json({ detail: "This account cannot access this workspace." }, { status: 403 });
    clearSession(error);
    return error;
  }
  const response = NextResponse.json(user);
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
