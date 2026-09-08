/* Copyright 2026 Marimo. All rights reserved. */

import type { ExportAsHTMLRequest } from "./types";

/**
 * In dev/test the CDN has no assets for the local build, so exports default
 * to the dev server. Callers publishing to a remote origin pass their own
 * assetUrl, which is left untouched.
 */
export function withDevAssetUrl(
  request: ExportAsHTMLRequest,
): ExportAsHTMLRequest {
  const isDevOrTest =
    process.env.NODE_ENV === "development" || process.env.NODE_ENV === "test";
  if (request.assetUrl == null && isDevOrTest) {
    return { ...request, assetUrl: window.location.origin };
  }
  return request;
}
