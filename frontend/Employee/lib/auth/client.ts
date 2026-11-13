import type { ApiError, CurrentUser } from "./types";

export class AuthApiError extends Error {
  constructor(
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = "AuthApiError";
  }
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const payload = (await response.json().catch(() => ({}))) as ApiError;
  return new AuthApiError(payload.detail || fallback, payload.code);
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await responseError(response, "Unable to log in.");
  return response.json() as Promise<CurrentUser>;
}

export async function loadCurrentUser(): Promise<CurrentUser> {
  const response = await fetch("/api/auth/me", { cache: "no-store" });
  if (!response.ok) throw await responseError(response, "Your session has expired.");
  return response.json() as Promise<CurrentUser>;
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}
