import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/lib/auth/config";

export async function POST(request: NextRequest) {
  if (!authConfig.signupEnabled) {
    return NextResponse.json(
      { code: "PUBLIC_SIGNUP_DISABLED", detail: authConfig.signupDisabledMessage },
      { status: 403 },
    );
  }

  try {
    const response = await fetch(`${authConfig.backendUrl}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(await request.json()),
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { code: "SERVICE_UNAVAILABLE", detail: "Signup service is unavailable." },
      { status: 503 },
    );
  }
}
