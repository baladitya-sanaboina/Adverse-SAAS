import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/lib/auth/config";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${authConfig.backendUrl}/company/invitations/validate${request.nextUrl.search}`, {
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Invitation service is unavailable." }, { status: 503 });
  }
}
