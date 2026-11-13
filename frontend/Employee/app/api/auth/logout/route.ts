import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { authConfig } from "@/lib/auth/config";
import { clearSession } from "@/lib/auth/server";

export async function POST() {
  const store = await cookies();
  const access = store.get(authConfig.accessCookie)?.value;
  if (access)
    await fetch(`${authConfig.backendUrl}/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${access}` },
      cache: "no-store",
    });
  const response = NextResponse.json({ message: "Logged out." });
  clearSession(response);
  return response;
}
