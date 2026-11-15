import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

type Context = { params: Promise<{ path?: string[] }> };

// Calendar with events and todos (2026-11-15): every calendar call goes to the backend.
async function forward(request: NextRequest, context: Context) {
  return proxyToBackend(request, "/agenda", (await context.params).path);
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
