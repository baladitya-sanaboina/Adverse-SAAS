import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  if (!request.cookies.get("loopless_employee_access")?.value) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  // Every signed-in page (security checklist, 2026-11-15). Left open: the sign-in pages,
  // invitations, meet links (/call shows its own sign-in), the API, Next's files and static files.
  matcher: [
    "/((?!$|login|register|forgot-password|reset-password|verify-email|invitations|call|api|_next|.*\\.[A-Za-z0-9]+$).*)",
  ],
};
