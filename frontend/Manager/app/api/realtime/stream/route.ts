import { NextRequest } from "next/server";
import { proxyToBackend } from "@loopless-shared/production/backend-proxy";

// Live events (Server-Sent Events) for the signed-in user; streamed through unchanged.
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "/realtime/stream", []);
}
