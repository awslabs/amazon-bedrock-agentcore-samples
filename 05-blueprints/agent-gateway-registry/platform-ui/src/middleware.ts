export { auth as middleware } from "@/lib/auth"

export const config = {
  matcher: [
    // Protect everything except auth routes, public API, and static files
    "/((?!api/auth|api/registry/discover|login|_next/static|_next/image|favicon.ico).*)",
  ],
}
