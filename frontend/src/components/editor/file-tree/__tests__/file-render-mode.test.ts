/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getFileRenderMode } from "../file-render-mode";

describe("getFileRenderMode", () => {
  it.each([
    ["text/plain", false, "text"],
    ["text/markdown", false, "markdown"],
    ["text/markdown; charset=utf-8", false, "markdown"],
    ["text/x-rust", false, "text"],
    ["application/json", false, "text"],
    ["application/toml", false, "text"],
    ["application/x-toml", false, "text"],
    ["application/xml", false, "text"],
    ["text/x-toml", false, "text"],
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

  it.each([
    ["README.md", "text/plain", "markdown"],
    ["AGENTS.md", "application/octet-stream", "markdown"],
    ["guide.markdown", "text/plain", "markdown"],
    ["notes.txt", "text/plain", "text"],
  ] as const)(
    "detects Markdown filename %s with MIME %s",
    (filename, mimeType, expected) => {
      expect(getFileRenderMode(mimeType, false, filename)).toBe(expected);
    },
  );

  it("does not treat base64 Markdown as text", () => {
    expect(getFileRenderMode("text/markdown", true, "README.md")).toBe(
      "unsupported",
    );
  });
});
