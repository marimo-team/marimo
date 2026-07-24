/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getFileRenderMode } from "../file-render-mode";

describe("getFileRenderMode", () => {
  it.each([
    ["text/plain", false, "text"],
    ["text/x-rust", false, "text"],
    ["application/json", false, "text"],
    ["application/xml", false, "text"],
    ["text/csv", false, "csv"],
    ["image/png", true, "media"],
    ["video/mp4", true, "media"],
    ["application/pdf", true, "media"],
    ["application/x-apple-diskimage", true, "unsupported"],
    ["application/zip", true, "unsupported"],
    ["application/octet-stream", false, "unsupported"],
    [null, false, "text"],
    [null, true, "unsupported"],
  ] as const)(
    "maps %s with isBase64=%s to %s",
    (mimeType, isBase64, expected) => {
      expect(getFileRenderMode(mimeType, isBase64)).toBe(expected);
    },
  );
});
