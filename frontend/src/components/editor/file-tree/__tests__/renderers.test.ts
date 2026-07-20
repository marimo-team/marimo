/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { buildMediaSource } from "../renderers";

describe("buildMediaSource", () => {
  it("returns base64 source for binary media", () => {
    expect(
      buildMediaSource({
        contents: "aGVsbG8=",
        mimeType: "image/png",
        isBase64: true,
      }),
    ).toEqual({
      base64: "aGVsbG8=",
      mime: "image/png",
    });
  });

  it("returns UTF-8 data URL for text-based media", () => {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>';
    expect(
      buildMediaSource({
        contents: svg,
        mimeType: "image/svg+xml",
        isBase64: false,
      }),
    ).toEqual({
      url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
    });
  });
});
