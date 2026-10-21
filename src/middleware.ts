import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route gate.
 *
 * The session cookie (tk_session) is httpOnly and host-only on the API
 * domain, so this middleware can never see it. It reads the first-party
 * hint cookie instead, which the client sets after a successful sign in.
 * The hint only decides which pages to send to /auth; the API validates
 * every request and returns 401 when the session is missing.
 */
const SESSION_HINT_COOKIE = "tk_hint";

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
  const hasHint = Boolean(request.cookies.get(SESSION_HINT_COOKIE)?.value);

  const isProtected = PROTECTED_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`)
  );

  if (isProtected && !hasHint) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (pathname === "/auth" && hasHint) {
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
