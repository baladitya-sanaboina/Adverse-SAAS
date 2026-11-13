import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/lib/auth/config";

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token") ?? "";
  try {
    const response = await fetch(`${authConfig.backendUrl}/auth/verify-email?token=${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { code: "SERVICE_UNAVAILABLE", detail: "Email verification service is unavailable." },
      { status: 503 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const response = await fetch(`${authConfig.backendUrl}/auth/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(await request.json()),
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { code: "SERVICE_UNAVAILABLE", detail: "Email verification service is unavailable." },
      { status: 503 },
    );
  }
}
