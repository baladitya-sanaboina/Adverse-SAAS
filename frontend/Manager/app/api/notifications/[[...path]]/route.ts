import { NextRequest } from "next/server";
import { proxyToBackend } from "@loopless-shared/production/backend-proxy";

type Context = { params: Promise<{ path?: string[] }> };

async function forward(request: NextRequest, context: Context) {
  return proxyToBackend(request, "/notifications", (await context.params).path);
}

export const GET = forward;
export const POST = forward;
