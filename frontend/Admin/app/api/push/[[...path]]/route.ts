import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

type Context = { params: Promise<{ path?: string[] }> };

// Web Push (2026-11-15): the public key and this browser's subscription.
async function forward(request: NextRequest, context: Context) {
  return proxyToBackend(request, "/push", (await context.params).path);
}

export const GET = forward;
export const POST = forward;
