/* Copyright 2026 Marimo. All rights reserved. */

import { isMediaMime, MIME_TO_LANGUAGE } from "./renderers";

export type FileRenderMode = "text" | "csv" | "media" | "unsupported";

export function getFileRenderMode(
  mimeType: string | null | undefined,
  isBase64: boolean,
): FileRenderMode {
  const mime = mimeType || "text/plain";

  if (isMediaMime(mime)) {
    return "media";
  }
  if (isBase64) {
    return "unsupported";
  }
  if (mime === "text/csv") {
    return "csv";
  }
  if (
    mime.startsWith("text/") ||
    (mime !== "default" && mime in MIME_TO_LANGUAGE)
  ) {
    return "text";
  }
  if (mimeType == null) {
    return "text";
  }
  return "unsupported";
}
