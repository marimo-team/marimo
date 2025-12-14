/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseContent } from "../url-parser";

describe("parseContent", () => {
  it("handles data URIs", () => {
    const parts = parseContent("data:image/png;base64,iVBOR");
    expect(parts).toEqual([
      {
        type: "image",
        url: "data:image/png;base64,iVBOR",
      },
    ]);
  });

  it("handles complete URLs", () => {
    const parts = parseContent("https://marimo.io/path?query=value");
    expect(parts).toEqual([
      { type: "url", url: "https://marimo.io/path?query=value" },
    ]);
  });

  it("handles multiple URLs with text", () => {
    const parts = parseContent(
      "Visit https://marimo.io and https://github.com/marimo-team",
    );
    expect(parts).toEqual([
      { type: "text", value: "Visit " },
      { type: "url", url: "https://marimo.io" },
      { type: "text", value: " and " },
      { type: "url", url: "https://github.com/marimo-team" },
    ]);
  });

  it("handles text with data URIs", () => {
    // Currently doesn't detect mixed content
    const parts = parseContent("Image: data:image/png;base64,iVBOR");
    expect(parts).toEqual([
      { type: "text", value: "Image: data:image/png;base64,iVBOR" },
    ]);
  });

  it("handles data URIs, text and images", () => {
    const parts = parseContent(
      "this is a picture: https://avatars.githubusercontent.com/u/123 and data:image/png;base64,iVBOR",
    );
    expect(parts).toEqual([
      { type: "text", value: "this is a picture: " },
      { type: "image", url: "https://avatars.githubusercontent.com/u/123" },
      { type: "text", value: " and data:image/png;base64,iVBOR" },
    ]);
  });

  it("handles plain text without URLs", () => {
    const parts = parseContent("Hello world");
    expect(parts).toEqual([{ type: "text", value: "Hello world" }]);
  });

  it("handles image URLs with various extensions", () => {
    const extensions = ["png", "jpg", "jpeg", "gif", "webp", "svg", "ico"];
    extensions.forEach((ext) => {
      const parts = parseContent(`Image: https://example.com/image.${ext}`);
      expect(parts).toContainEqual({
        type: "image",
        url: `https://example.com/image.${ext}`,
      });
    });
  });

  it("handles known image domains", () => {
    const parts = parseContent(
      "Avatar: https://avatars.githubusercontent.com/u/123",
    );
    expect(parts).toContainEqual({
      type: "image",
      url: "https://avatars.githubusercontent.com/u/123",
    });
  });
});
