/**
 * Vercel Edge Middleware for serving markdown versions of docs pages.
 *
 * Handles two cases:
 * 1. Accept: text/markdown header -> rewrite to serve .md file
 * 2. URL ending in .md -> serve the corresponding .md file
 *
 * Testing (deployed):
 *
 *   # Via Accept header (content negotiation)
 *   curl -H "Accept: text/markdown" https://docs.marimo.io/guides/reactivity/
 *
 *   # Via .md URL extension
 *   curl https://docs.marimo.io/guides/reactivity.md
 *
 * Testing (local build):
 *
 *   # 1. Build docs and generate markdown
 *   make docs
 *   python docs/scripts/html_to_markdown.py --input-dir site --base-url https://docs.marimo.io
 *
 *   # 2. Verify .md files were created
 *   cat site/guides/reactivity/index.md
 *
 *   Note: The middleware only runs on Vercel (edge runtime), so Accept header
 *   negotiation can't be tested locally. The .md files can be served directly
 *   by any static file server, e.g.:
 *     cd site && python -m http.server 8000
 *     curl http://localhost:8000/guides/reactivity/index.md
 */
export default async function middleware(request) {
  const url = new URL(request.url);
  const pathname = url.pathname;

  // Already a direct .md static file request (e.g. /guides/reactivity/index.md)
  // — let Vercel serve it as-is to avoid a rewrite loop.
  if (pathname.endsWith("/index.md")) {
    return;
  }

  const acceptHeader = request.headers.get("accept") || "";
  const wantsMarkdown = acceptHeader.includes("text/markdown");
  const isMdUrl = pathname.endsWith(".md");

  if (!wantsMarkdown && !isMdUrl) {
    return;
  }

  // Determine the .md file path
  let mdPath;
  if (isMdUrl) {
    // /guides/reactivity.md -> /guides/reactivity/index.md
    mdPath = pathname.replace(/\.md$/, "/index.md");
  } else {
    // /guides/reactivity/ -> /guides/reactivity/index.md
    mdPath = pathname.endsWith("/")
      ? pathname + "index.md"
      : pathname + "/index.md";
  }

  // Rewrite to the static .md file. In Vercel's edge runtime, fetch() to the
  // same origin goes directly to the static file server without re-triggering
  // middleware. The /index.md early-return above is an extra safety guard.
  const rewriteUrl = new URL(mdPath, request.url);
  const response = await fetch(rewriteUrl);

  if (!response.ok) {
    // .md file doesn't exist — fall through to normal static serving
    return;
  }

  return new Response(response.body, {
    status: 200,
    headers: {
      "content-type": "text/markdown; charset=utf-8",
      "cache-control":
        response.headers.get("cache-control") || "public, max-age=3600",
      "access-control-allow-origin": "*",
    },
  });
}

export const config = {
  matcher: [
    // Match all paths except static assets and direct .md file requests
    "/((?!_static|assets|stylesheets|search/search_index\\.json|sitemap|robots\\.txt|favicon|llms\\.txt|CLAUDE\\.md).*)",
  ],
};
