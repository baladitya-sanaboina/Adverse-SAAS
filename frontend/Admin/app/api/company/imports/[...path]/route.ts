import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

type Context = { params: Promise<{ path: string[] }> };

// Spreadsheet import (owner request 2026-11-19): the .xlsx upload is streamed to the backend.
async function forward(request: NextRequest, context: Context) {
  return proxyToBackend(request, "/company/imports", (await context.params).path);
}

export const POST = forward;
