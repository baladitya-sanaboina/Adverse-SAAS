import { NextResponse } from "next/server";
import { loginSession, setSession } from "@/lib/auth/server";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { email?: string; password?: string };
  if (!body.email || !body.password)
    return NextResponse.json({ detail: "Email and password are required." }, { status: 422 });
  const result = await loginSession(body.email, body.password);
  if (result.response) return result.response;
  const response = NextResponse.json(result.user);
  await setSession(response, result.access!, result.refresh!);
  return response;
}
