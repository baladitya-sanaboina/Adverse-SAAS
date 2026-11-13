import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

export async function GET(request: NextRequest) {
  const path = request.nextUrl.searchParams.get("path");
  if (!path?.startsWith("/storage/profile-images/") || path.includes(".."))
    return NextResponse.json({ detail: "Invalid profile image path." }, { status: 400 });
  const result = await authenticatedBackend(path);
  if (!result.response.ok)
    return NextResponse.json({ detail: "Profile image not found." }, { status: result.response.status });
  const response = new NextResponse(result.response.body, {
    headers: { "Content-Type": result.response.headers.get("content-type") ?? "application/octet-stream" },
  });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function POST(request: NextRequest) {
  const result = await authenticatedBackend("/profile/image", { method: "POST", body: await request.formData() });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
