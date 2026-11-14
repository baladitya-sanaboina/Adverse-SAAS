import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

type Context = { params: Promise<{ path?: string[] }> };

// Chat (Phase 14): every chat call, including file uploads and downloads, goes through here.
async function forward(request: NextRequest, context: Context) {
  return proxyToBackend(request, "/chat", (await context.params).path);
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
