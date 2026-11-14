import { NextRequest, NextResponse } from "next/server";
import { authenticatedBackend, setSession } from "@/lib/auth/server";
// Copy of frontend/shared/production/backend-proxy.ts (the Client app cannot import shared/). Keep in sync.

const SAFE_SEGMENT = /^[A-Za-z0-9_-]+$/;
const PASSED_HEADERS = ["content-type", "content-disposition", "content-length", "cache-control", "x-accel-buffering"];

/**
 * Forward a request from an Admin API route to one fixed backend prefix.
 *
 * JSON bodies are buffered (so a token refresh can retry them); file uploads are streamed, so
 * large videos are not held in memory. Responses are streamed back unchanged, which also covers
 * file downloads.
 */
export async function proxyToBackend(
  request: NextRequest,
  prefix: string,
  segments: string[] | undefined,
): Promise<NextResponse> {
  const parts = segments ?? [];
  if (!parts.every((part) => SAFE_SEGMENT.test(part))) {
    return NextResponse.json({ detail: "Invalid path." }, { status: 400 });
  }
  const path = [prefix, ...parts].join("/") + request.nextUrl.search;
  const method = request.method;
  const contentType = request.headers.get("content-type") ?? "";
  // The signal closes the backend request when the browser goes away (live event streams).
  const init: RequestInit & { duplex?: "half" } = { method, signal: request.signal };
  if (!["GET", "HEAD", "DELETE"].includes(method)) {
    init.headers = contentType ? { "Content-Type": contentType } : {};
    if (contentType.startsWith("multipart/form-data")) {
      init.body = request.body;
      init.duplex = "half";
    } else {
      init.body = await request.text();
    }
  }
  let result;
  try {
    result = await authenticatedBackend(path, init);
  } catch {
    return NextResponse.json(
      { detail: "The request could not be completed. Please sign in again and retry." },
      { status: 502 },
    );
  }
  const upstream = result.response;
  const headers = new Headers();
  for (const name of PASSED_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = new NextResponse(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers,
  });
  if (result.access && result.refresh) await setSession(response, result.access, result.refresh);
  return response;
}
