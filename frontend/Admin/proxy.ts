import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  if (!request.cookies.get("loopless_admin_access")?.value) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/company/:path*",
    "/employees/:path*",
    "/clients/:path*",
    "/projects/:path*",
    "/tasks/:path*",
    "/crm/:path*",
    "/finance/:path*",
    "/attendance/:path*",
    "/documents/:path*",
    "/reports/:path*",
    "/notifications/:path*",
    "/settings/:path*",
  ],
};
