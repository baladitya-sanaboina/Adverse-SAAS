import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { authConfig } from "./config";
import type { ApiError, CurrentUser } from "./types";

const secure = process.env.NODE_ENV === "production";
const cookieOptions = (maxAge: number) => ({ httpOnly: true, secure, sameSite: "lax" as const, path: "/", maxAge });

async function backend(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${authConfig.backendUrl}${path}`, { ...init, cache: "no-store" });
}

// One refresh per refresh token (2026-11-19). When the 30-minute access token has expired, a
// page load fires many requests at once; each used to refresh on its own with the same refresh
// token, only the first won (the backend allows each refresh token once) and the rest failed,
// leaving blank pages and sudden logouts. Requests that arrive together share one refresh, and
// late ones within a minute get the same new tokens, so every response saves the same cookies.
type RefreshedTokens = { access_token: string; refresh_token: string };
type RefreshOutcome = { tokens: RefreshedTokens } | { status: number; body: string; contentType: string };
const REFRESH_REUSE_MS = 60_000;
const refreshes = new Map<string, { at: number; outcome: Promise<RefreshOutcome> }>();

function refreshOnce(refreshToken: string): Promise<RefreshOutcome> {
  const now = Date.now();
  for (const [key, entry] of refreshes) if (now - entry.at > REFRESH_REUSE_MS) refreshes.delete(key);
  const known = refreshes.get(refreshToken);
  if (known) return known.outcome;
  const outcome: Promise<RefreshOutcome> = backend("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).then(async (response) =>
    response.ok
      ? { tokens: (await response.json()) as RefreshedTokens }
      : {
          status: response.status,
          body: await response.text(),
          contentType: response.headers.get("content-type") ?? "application/json",
        },
  );
  refreshes.set(refreshToken, { at: now, outcome });
  // Only successes are shared; a failure is not remembered.
  void outcome
    .then((result) => {
      if (!("tokens" in result)) refreshes.delete(refreshToken);
    })
    .catch(() => refreshes.delete(refreshToken));
  return outcome;
}

function refreshFailure(outcome: Exclude<RefreshOutcome, { tokens: RefreshedTokens }>): Response {
  return new Response(outcome.body, { status: outcome.status, headers: { "Content-Type": outcome.contentType } });
}

function companyIdFromAccessToken(token: string): string | undefined {
  try {
    const payload = token.split(".")[1];
    if (!payload) return undefined;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "="))) as {
      company_id?: unknown;
    };
    return typeof decoded.company_id === "string" && decoded.company_id ? decoded.company_id : undefined;
  } catch {
    return undefined;
  }
}

export async function authenticatedBackend(
  path: string,
  init: RequestInit = {},
): Promise<{ response: Response; access?: string; refresh?: string }> {
  const store = await cookies();
  let access = store.get(authConfig.accessCookie)?.value;
  const refresh = store.get(authConfig.refreshCookie)?.value;
  if (!access) return { response: new Response(null, { status: 401 }) };
  const request = (token: string) => {
    const companyId = companyIdFromAccessToken(token);
    return backend(path, {
      ...init,
      headers: {
        ...Object.fromEntries(new Headers(init.headers).entries()),
        Authorization: `Bearer ${token}`,
        ...(companyId ? { "X-Company-ID": companyId } : {}),
      },
    });
  };
  let response = await request(access);
  if (response.status !== 401 || !refresh) return { response };
  const outcome = await refreshOnce(refresh);
  if (!("tokens" in outcome)) return { response: refreshFailure(outcome) };
  const tokens = outcome.tokens;
  access = tokens.access_token;
  response = await request(access);
  return { response, access, refresh: tokens.refresh_token };
}

export async function backendError(response: Response): Promise<NextResponse> {
  // A server crash has no JSON body; say what happened instead of blaming the sign-in.
  const fallback =
    response.status === 401
      ? "Your session has ended. Please sign in again."
      : response.status === 403
        ? "You do not have permission to do this."
        : response.status >= 500
          ? "Something went wrong on the server. Please try again."
          : "The request could not be completed.";
  const payload = (await response.json().catch(() => ({ detail: fallback }))) as ApiError;
  return NextResponse.json(payload, { status: response.status });
}

export async function setSession(response: NextResponse, accessToken: string, refreshToken: string): Promise<void> {
  // The cookie lives as long as the refresh token (7 days); an expired token inside it is renewed
  // on the next request, so people stay signed in instead of being logged out after 30 minutes.
  response.cookies.set(authConfig.accessCookie, accessToken, cookieOptions(7 * 24 * 60 * 60));
  response.cookies.set(authConfig.refreshCookie, refreshToken, cookieOptions(7 * 24 * 60 * 60));
}

export function clearSession(response: NextResponse): void {
  response.cookies.set(authConfig.accessCookie, "", cookieOptions(0));
  response.cookies.set(authConfig.refreshCookie, "", cookieOptions(0));
}

export async function currentUserWithRefresh(): Promise<{ response: Response; access?: string; refresh?: string }> {
  const store = await cookies();
  let access = store.get(authConfig.accessCookie)?.value;
  const refresh = store.get(authConfig.refreshCookie)?.value;
  if (!access) return { response: new Response(null, { status: 401 }) };
  let response = await backend("/users/me", { headers: { Authorization: `Bearer ${access}` } });
  if (response.status !== 401 || !refresh) return { response };
  const outcome = await refreshOnce(refresh);
  if (!("tokens" in outcome)) return { response: refreshFailure(outcome) };
  const tokens = outcome.tokens;
  access = tokens.access_token;
  response = await backend("/users/me", { headers: { Authorization: `Bearer ${access}` } });
  return { response, access, refresh: tokens.refresh_token };
}

export async function loginSession(
  email: string,
  password: string,
): Promise<{ user?: CurrentUser; response?: NextResponse; access?: string; refresh?: string }> {
  const loginResponse = await backend("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!loginResponse.ok) return { response: await backendError(loginResponse) };
  const tokens = (await loginResponse.json()) as { access_token: string; refresh_token: string };
  const profileResponse = await backend("/users/me", { headers: { Authorization: `Bearer ${tokens.access_token}` } });
  if (!profileResponse.ok) return { response: await backendError(profileResponse) };
  const user = (await profileResponse.json()) as CurrentUser;
  if (user.role.code !== authConfig.allowedRole) {
    await backend("/auth/logout", { method: "POST", headers: { Authorization: `Bearer ${tokens.access_token}` } });
    return {
      response: NextResponse.json(
        { code: "ROLE_NOT_ALLOWED", detail: "This account cannot access this workspace." },
        { status: 403 },
      ),
    };
  }
  return { user, access: tokens.access_token, refresh: tokens.refresh_token };
}
