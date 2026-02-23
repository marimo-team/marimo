/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { EDGE_CASE_FILENAMES } from "../../__tests__/mocks";
import { Filenames, getImageExtension } from "../filenames";

describe("Filenames", () => {
  it("should convert filename to markdown", () => {
    expect(Filenames.toMarkdown("test")).toEqual("test.md");
    expect(Filenames.toMarkdown("test.txt")).toEqual("test.md");
    expect(Filenames.toMarkdown("test.foo.py")).toEqual("test.foo.md");
  });

  it("should convert filename to HTML", () => {
    expect(Filenames.toHTML("test")).toEqual("test.html");
    expect(Filenames.toHTML("test.txt")).toEqual("test.html");
    expect(Filenames.toHTML("test.foo.py")).toEqual("test.foo.html");
  });

  it("should convert filename to PNG", () => {
    expect(Filenames.toPNG("test")).toEqual("test.png");
    expect(Filenames.toPNG("test.txt")).toEqual("test.png");
    expect(Filenames.toPNG("test.foo.py")).toEqual("test.foo.png");
  });

  it("should remove extension from filename", () => {
    expect(Filenames.withoutExtension("test")).toEqual("test");
    expect(Filenames.withoutExtension("test.txt")).toEqual("test");
    expect(Filenames.withoutExtension("test.foo.txt")).toEqual("test.foo");
  });

  it.each(
    EDGE_CASE_FILENAMES,
  )("should handle edge case filenames: %s", (filename) => {
    // Test all filename operations with edge cases
    const withoutExt = Filenames.withoutExtension(filename);

    expect(Filenames.toMarkdown(filename)).toEqual(`${withoutExt}.md`);
    expect(Filenames.toHTML(filename)).toEqual(`${withoutExt}.html`);
    expect(Filenames.toPNG(filename)).toEqual(`${withoutExt}.png`);
    expect(Filenames.toPY(filename)).toEqual(`${withoutExt}.py`);

    // Ensure operations preserve unicode and special characters in base name
    expect(withoutExt).not.toEqual("");
    expect(typeof withoutExt).toBe("string");
  });
});

describe("getImageExtension", () => {
  it("should return correct extensions for common image URLs", () => {
    expect(getImageExtension("https://example.com/image.png")).toBe("png");
    expect(getImageExtension("https://example.com/image.jpeg")).toBe("jpeg");
    expect(getImageExtension("https://example.com/image.JPEG?param=1")).toBe(
      "jpeg",
    );
    expect(getImageExtension("https://example.com/image.gif")).toBe("gif");
    expect(getImageExtension("https://example.com/image.svg")).toBe("svg");
    expect(getImageExtension("https://example.com/image.webp")).toBe("webp");
    expect(getImageExtension("https://example.com/image.avif")).toBe("avif");
    expect(getImageExtension("https://example.com/image.bmp")).toBe("bmp");
    expect(getImageExtension("https://example.com/image.tiff")).toBe("tiff");
  });

  it("should return correct extensions for data URIs", () => {
    expect(getImageExtension("data:image/png;base64,...")).toBe("png");
    expect(getImageExtension("data:image/jpeg;base64,...")).toBe("jpeg");
    expect(getImageExtension("data:image/svg+xml;base64,...")).toBe("svg");
  });

  it("should return correct extensions for relative URLs resolved with window.location.href", () => {
    // Mock window.location
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      value: new URL("https://example.com/some/path/index.html"),
      writable: true,
    });

    expect(getImageExtension("../assets/image.png")).toBe("png");
    expect(getImageExtension("image.jpeg")).toBe("jpeg");
    expect(getImageExtension("/root/image.gif")).toBe("gif");

    // Restore original window.location
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });

  it("should return undefined for URLs without recognized image extensions", () => {
    expect(
      getImageExtension("https://example.com/document.pdf"),
    ).toBeUndefined();
    expect(
      getImageExtension("https://example.com/archive.tar.gz"),
    ).toBeUndefined();
    expect(getImageExtension("https://example.com/image")).toBeUndefined(); // No extension
    expect(getImageExtension("image")).toBeUndefined();
    expect(getImageExtension("")).toBeUndefined();
  });
});
