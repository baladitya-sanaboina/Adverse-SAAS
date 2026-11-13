import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/lib/auth/config";

export async function POST(request: NextRequest) {
  try {
    const response = await fetch(`${authConfig.backendUrl}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(await request.json()),
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { code: "SERVICE_UNAVAILABLE", detail: "Password recovery service is unavailable." },
      { status: 503 },
    );
  }
}
