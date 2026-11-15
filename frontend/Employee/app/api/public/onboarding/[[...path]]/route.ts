import { NextRequest, NextResponse } from "next/server";

// Onboarding documents (2026-11-15): the private link works without signing in. Only
// /public/onboarding/<token>[/pdf] is forwarded; the token is the key the backend checks.
const SAFE = /^[A-Za-z0-9_-]+$/;
const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

type Context = { params: Promise<{ path?: string[] }> };

async function forward(request: NextRequest, context: Context) {
  const parts = (await context.params).path ?? [];
  if (parts.length < 1 || parts.length > 2 || !parts.every((part) => SAFE.test(part))) {
    return NextResponse.json({ detail: "Invalid link." }, { status: 400 });
  }
  const headers: Record<string, string> = {
    "user-agent": request.headers.get("user-agent") ?? "",
    "x-forwarded-for": request.headers.get("x-forwarded-for") ?? "",
  };
  const init: RequestInit = { method: request.method, headers };
  if (request.method === "POST") {
    headers["content-type"] = "application/json";
    init.body = await request.text();
  }
  const upstream = await fetch(`${BACKEND}/public/onboarding/${parts.join("/")}`, init).catch(() => null);
  if (!upstream) return NextResponse.json({ detail: "Please try again in a moment." }, { status: 502 });
  const out = new Headers();
  for (const name of ["content-type", "content-disposition"]) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  return new NextResponse(upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
