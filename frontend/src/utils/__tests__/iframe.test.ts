/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { captureExternalIframes } from "../iframe";

describe("captureExternalIframes", () => {
  const originalCreateElement = document.createElement.bind(document);

  beforeEach(() => {
    // Mock devicePixelRatio
    Object.defineProperty(window, "devicePixelRatio", {
      value: 1,
      writable: true,
    });

    // Mock canvas for placeholder generation
    vi.spyOn(document, "createElement").mockImplementation((tagName) => {
      const element = originalCreateElement(tagName);
      if (tagName === "canvas") {
        const mockCtx = {
          scale: vi.fn(),
          fillStyle: "",
          fillRect: vi.fn(),
          strokeStyle: "",
          strokeRect: vi.fn(),
          font: "",
          textAlign: "",
          textBaseline: "",
          fillText: vi.fn(),
          measureText: vi.fn().mockReturnValue({ width: 10 }),
        };
        vi.spyOn(element as HTMLCanvasElement, "getContext").mockReturnValue(
          mockCtx as unknown as CanvasRenderingContext2D,
        );
        vi.spyOn(element as HTMLCanvasElement, "toDataURL").mockReturnValue(
          "data:image/png;base64,placeholder",
        );
      }
      return element;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("should return null when element has no iframe", async () => {
    const element = document.createElement("div");
    element.innerHTML = "<p>No iframe here</p>";

    const result = await captureExternalIframes(element);
    expect(result).toBeNull();
  });

  it("should return placeholder for external iframe", async () => {
    const element = document.createElement("div");
    element.innerHTML = '<iframe src="https://external.com/page"></iframe>';

    const result = await captureExternalIframes(element);

    expect(result).not.toBeNull();
    expect(result).toMatch(/^data:image\/png;base64,/);
  });

  it("should return placeholder for cross-origin iframe", async () => {
    const element = document.createElement("div");
    element.innerHTML =
      '<iframe src="https://www.openstreetmap.org/export/embed.html"></iframe>';

    const result = await captureExternalIframes(element);

    expect(result).not.toBeNull();
    expect(result).toMatch(/^data:image\/png;base64,/);
  });

  it("should return null for about:blank iframe without body", async () => {
    const element = document.createElement("div");
    const iframe = document.createElement("iframe");
    iframe.src = "about:blank";
    element.append(iframe);

    // The iframe has no body accessible in jsdom
    const result = await captureExternalIframes(element);

    // In jsdom, contentDocument may not be accessible
    expect(result).toBeNull();
  });

  it("should handle iframe with relative same-origin src", async () => {
    const element = document.createElement("div");
    element.innerHTML = '<iframe src="./@file/123.html"></iframe>';

    // Same-origin relative URL, but contentDocument not accessible in jsdom
    const result = await captureExternalIframes(element);

    // Returns null because jsdom can't access contentDocument for file URLs
    expect(result).toBeNull();
  });

  it("should detect external URL from various formats", async () => {
    const externalUrls = [
      "https://example.com",
      "http://external.org/path",
      "https://sub.domain.com:8080/page",
    ];

    for (const url of externalUrls) {
      const element = document.createElement("div");
      element.innerHTML = `<iframe src="${url}"></iframe>`;

      const result = await captureExternalIframes(element);

      expect(result).not.toBeNull();
      expect(result).toMatch(/^data:image\/png;base64,/);
    }
  });

  it("should not treat same-origin URLs as external", async () => {
    // Same-origin URLs - these should try to capture, not return placeholder
    const sameOriginUrls = ["/local/path", "./relative/path", "../parent/path"];

    for (const url of sameOriginUrls) {
      const element = document.createElement("div");
      element.innerHTML = `<iframe src="${url}"></iframe>`;

      const result = await captureExternalIframes(element);

      // In jsdom, these return null because contentDocument isn't accessible
      // but they should NOT return a placeholder (which would indicate external detection)
      // The key is they don't trigger the external URL path
      expect(result).toBeNull();
    }
  });
});
