import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route gate. The session cookie is set by the backend on sign in; its
 * presence is checked here, the backend validates it on every request.
 */
const SESSION_COOKIE = "tk_session";

const PROTECTED_PATHS = [
  "/setup",
  "/jobs",
  "/trends",
  "/qa",
  "/digest",
  "/profile",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  const isProtected = PROTECTED_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`)
  );

  if (isProtected && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (pathname === "/auth" && hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/setup/1";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/setup/:path*", "/jobs/:path*", "/trends/:path*", "/qa/:path*", "/digest/:path*", "/profile/:path*", "/auth"],
};
