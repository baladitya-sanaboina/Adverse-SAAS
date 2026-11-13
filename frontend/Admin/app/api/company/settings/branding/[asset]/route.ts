import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, backendError, setSession } from "@/lib/auth/server";

export async function GET(request: NextRequest, { params }: { params: Promise<{ asset: string }> }) {
  const { asset } = await params;
  if (asset !== "file") return NextResponse.json({ detail: "Invalid asset." }, { status: 422 });
  const path = request.nextUrl.searchParams.get("path");
  if (!path?.startsWith("/storage/company-branding/") || path.includes(".."))
    return NextResponse.json({ detail: "Invalid asset path." }, { status: 400 });
  const result = await authenticatedBackend(path);
  if (!result.response.ok) return NextResponse.json({ detail: "Asset not found." }, { status: result.response.status });
  const response = new NextResponse(result.response.body, {
    headers: { "Content-Type": result.response.headers.get("content-type") ?? "application/octet-stream" },
  });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ asset: string }> }) {
  const { asset } = await params;
  if (!["logo", "favicon"].includes(asset)) return NextResponse.json({ detail: "Invalid asset." }, { status: 422 });
  const result = await authenticatedBackend(`/company/settings/branding/${asset}`, {
    method: "POST",
    body: await request.formData(),
  });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json(), { status: 201 });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ asset: string }> }) {
  const { asset } = await params;
  if (!["logo", "favicon"].includes(asset)) return NextResponse.json({ detail: "Invalid asset." }, { status: 422 });
  const result = await authenticatedBackend(`/company/settings/branding/${asset}`, { method: "DELETE" });
  if (!result.response.ok) return backendError(result.response);
  const response = NextResponse.json(await result.response.json());
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
