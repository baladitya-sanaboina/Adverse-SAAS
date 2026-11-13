import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, setSession } from "@/lib/auth/server";

export async function GET(request: NextRequest) {
  const path = request.nextUrl.searchParams.get("path");
  if (!path?.startsWith("/storage/company-branding/") || path.includes("..")) {
    return NextResponse.json({ detail: "Invalid branding path." }, { status: 400 });
  }
  const result = await authenticatedBackend(path);
  if (!result.response.ok) {
    return NextResponse.json({ detail: "Branding asset not found." }, { status: result.response.status });
  }
  const response = new NextResponse(result.response.body, {
    headers: { "Content-Type": result.response.headers.get("content-type") ?? "application/octet-stream" },
  });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
