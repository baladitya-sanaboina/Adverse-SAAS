import { NextRequest } from "next/server";
import { proxyToBackend } from "@loopless-shared/production/backend-proxy";

type Context = { params: Promise<{ path?: string[] }> };

// Internal mailbox (2026-11-15): every mail call, including file uploads and downloads.
async function forward(request: NextRequest, context: Context) {
  return proxyToBackend(request, "/mail", (await context.params).path);
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
