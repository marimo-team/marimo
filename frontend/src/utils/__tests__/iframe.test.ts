/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { replaceIframesForCapture } from "../iframe";

// Mock Logger
vi.mock("@/utils/Logger", () => ({
  Logger: {
    debug: vi.fn(),
    error: vi.fn(),
  },
}));

describe("replaceIframesForCapture", () => {
  let container: HTMLDivElement;
  const mockToPng = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    container = document.createElement("div");
    document.body.append(container);
    mockToPng.mockResolvedValue("data:image/png;base64,mockdata");
  });

  afterEach(() => {
    container.remove();
  });

  /**
   * Helper to create a cross-origin iframe (contentDocument is null in jsdom for cross-origin)
   */
  function createCrossOriginIframe(
    src: string,
    width: number,
    height: number,
  ): HTMLIFrameElement {
    const iframe = document.createElement("iframe");
    iframe.src = src;
    Object.defineProperty(iframe, "offsetWidth", { value: width });
    Object.defineProperty(iframe, "offsetHeight", { value: height });
    return iframe;
  }

  /**
   * Helper to create a same-origin iframe with mocked contentDocument
   */
  function createSameOriginIframe(
    bodyContent: string,
    width: number,
    height: number,
  ): HTMLIFrameElement {
    const iframe = document.createElement("iframe");
    Object.defineProperty(iframe, "offsetWidth", { value: width });
    Object.defineProperty(iframe, "offsetHeight", { value: height });

    // Create a mock document body
    const mockBody = document.createElement("body");
    mockBody.innerHTML = bodyContent;

    // Mock contentDocument
    Object.defineProperty(iframe, "contentDocument", {
      value: { body: mockBody },
      configurable: true,
    });

    return iframe;
  }

  describe("cross-origin iframes", () => {
    it("should replace cross-origin iframe with placeholder", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      const restore = await replaceIframesForCapture(container, mockToPng);

      // During capture, iframe should be replaced
      expect(container.querySelectorAll("iframe").length).toBe(0);
      const placeholder = container.querySelector("div");
      expect(placeholder).toBeTruthy();

      restore();

      // After restore, iframe should be back
      expect(container.querySelectorAll("iframe").length).toBe(1);
      expect(container.querySelector("iframe")).toBe(iframe);
    });

    it("should create placeholder with correct dimensions", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 420, 315);
      container.append(iframe);

      await replaceIframesForCapture(container, mockToPng);

      const placeholder = container.querySelector("div")!;
      expect(placeholder.style.width).toBe("420px");
      expect(placeholder.style.height).toBe("315px");
    });

    it("should create placeholder with hostname label", async () => {
      const iframe = createCrossOriginIframe(
        "https://www.youtube.com/embed/abc123",
        400,
        300,
      );
      container.append(iframe);

      await replaceIframesForCapture(container, mockToPng);

      const placeholder = container.querySelector("div")!;
      expect(placeholder.textContent).toBe("[Embedded: www.youtube.com]");
    });

    it("should extract hostname from various URL formats", async () => {
      const iframe = createCrossOriginIframe(
        "https://player.vimeo.com/video/123",
        400,
        300,
      );
      container.append(iframe);

      await replaceIframesForCapture(container, mockToPng);

      const placeholder = container.querySelector("div")!;
      expect(placeholder.textContent).toBe("[Embedded: player.vimeo.com]");
    });
  });

  describe("placeholder styling", () => {
    it("should apply visual styles for placeholder appearance", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      await replaceIframesForCapture(container, mockToPng);

      const placeholder = container.querySelector("div")!;

      // Check essential styles are applied
      expect(placeholder.style.backgroundColor).toBe("rgb(245, 245, 245)");
      expect(placeholder.style.display).toBe("flex");
      expect(placeholder.style.alignItems).toBe("center");
      expect(placeholder.style.justifyContent).toBe("center");
      expect(placeholder.style.border).toBe("1px dashed rgb(204, 204, 204)");
      expect(placeholder.style.boxSizing).toBe("border-box");
    });
  });

  describe("same-origin iframes", () => {
    it("should capture same-origin iframe and replace with image", async () => {
      const iframe = createSameOriginIframe("<p>Hello</p>", 400, 300);
      container.append(iframe);

      const capturedDataUrl = "data:image/png;base64,captured";
      mockToPng.mockResolvedValue(capturedDataUrl);

      const restore = await replaceIframesForCapture(container, mockToPng);

      // Should have called toPng on iframe body
      expect(mockToPng).toHaveBeenCalled();

      // Should be replaced with an img element
      const img = container.querySelector("img");
      expect(img).toBeTruthy();
      expect(img?.src).toBe(capturedDataUrl);
      expect(img?.style.width).toBe("400px");
      expect(img?.style.height).toBe("300px");
      expect(img?.style.display).toBe("block");

      restore();

      // After restore, iframe should be back
      expect(container.querySelector("iframe")).toBe(iframe);
    });

    it("should fall back to placeholder when capture fails", async () => {
      const iframe = createSameOriginIframe("<p>Hello</p>", 400, 300);
      container.append(iframe);

      mockToPng.mockRejectedValue(new Error("Capture failed"));

      const restore = await replaceIframesForCapture(container, mockToPng);

      // Should fall back to placeholder when capture fails
      const placeholder = container.querySelector("div");
      expect(placeholder).toBeTruthy();
      expect(placeholder?.textContent).toBe("[Embedded content]");

      restore();

      expect(container.querySelector("iframe")).toBe(iframe);
    });
  });

  describe("nested iframes (mo.iframe with embedded content)", () => {
    it("should replace nested cross-origin iframes within same-origin iframe", async () => {
      // Create outer same-origin iframe with a nested cross-origin iframe
      const iframe = document.createElement("iframe");
      Object.defineProperty(iframe, "offsetWidth", { value: 420 });
      Object.defineProperty(iframe, "offsetHeight", { value: 315 });

      // Create mock body with nested iframe
      const mockBody = document.createElement("body");
      const nestedIframe = document.createElement("iframe");
      nestedIframe.src = "https://www.youtube.com/embed/abc123";
      Object.defineProperty(nestedIframe, "offsetWidth", { value: 420 });
      Object.defineProperty(nestedIframe, "offsetHeight", { value: 315 });
      mockBody.append(nestedIframe);

      Object.defineProperty(iframe, "contentDocument", {
        value: { body: mockBody },
        configurable: true,
      });

      container.append(iframe);

      let capturedBody: HTMLElement | null = null;
      mockToPng.mockImplementation(async (el: HTMLElement) => {
        capturedBody = el;
        // During capture of the outer iframe's body, nested iframes should be replaced
        const nestedIframes = el.querySelectorAll("iframe");
        expect(nestedIframes.length).toBe(0);

        const placeholder = el.querySelector("div");
        expect(placeholder).toBeTruthy();
        expect(placeholder?.textContent).toContain("youtube.com");

        return "data:image/png;base64,captured";
      });

      await replaceIframesForCapture(container, mockToPng);

      // Verify toPng was called on the iframe body
      expect(capturedBody).toBe(mockBody);

      // After capture, nested iframe should be restored inside the outer iframe
      const restoredNested = mockBody.querySelector("iframe");
      expect(restoredNested).toBe(nestedIframe);
    });

    it("should handle multiple nested iframes", async () => {
      const iframe = document.createElement("iframe");
      Object.defineProperty(iframe, "offsetWidth", { value: 420 });
      Object.defineProperty(iframe, "offsetHeight", { value: 630 });

      const mockBody = document.createElement("body");

      const nested1 = document.createElement("iframe");
      nested1.src = "https://youtube.com/embed/1";
      Object.defineProperty(nested1, "offsetWidth", { value: 420 });
      Object.defineProperty(nested1, "offsetHeight", { value: 315 });

      const nested2 = document.createElement("iframe");
      nested2.src = "https://vimeo.com/embed/2";
      Object.defineProperty(nested2, "offsetWidth", { value: 420 });
      Object.defineProperty(nested2, "offsetHeight", { value: 315 });

      mockBody.append(nested1);
      mockBody.append(nested2);

      Object.defineProperty(iframe, "contentDocument", {
        value: { body: mockBody },
        configurable: true,
      });

      container.append(iframe);

      mockToPng.mockImplementation(async (el: HTMLElement) => {
        // Both nested iframes should be replaced with placeholders
        const iframes = el.querySelectorAll("iframe");
        expect(iframes.length).toBe(0);

        const placeholders = el.querySelectorAll("div");
        expect(placeholders.length).toBe(2);

        return "data:image/png;base64,captured";
      });

      await replaceIframesForCapture(container, mockToPng);

      // After capture, both nested iframes should be restored
      const restored = mockBody.querySelectorAll("iframe");
      expect(restored.length).toBe(2);
    });
  });

  describe("cleanup and restore", () => {
    it("should restore all iframes in correct positions", async () => {
      const before = document.createElement("span");
      before.textContent = "before";
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      const after = document.createElement("span");
      after.textContent = "after";

      container.append(before);
      container.append(iframe);
      container.append(after);

      const restore = await replaceIframesForCapture(container, mockToPng);

      // Verify order during capture
      expect(container.children[0]).toBe(before);
      expect(container.children[1]).toBeInstanceOf(HTMLDivElement); // placeholder
      expect(container.children[2]).toBe(after);

      restore();

      // Verify order after restore
      expect(container.children[0]).toBe(before);
      expect(container.children[1]).toBe(iframe);
      expect(container.children[2]).toBe(after);
    });

    it("should handle multiple iframes", async () => {
      const iframe1 = createCrossOriginIframe("https://example1.com", 400, 300);
      const iframe2 = createCrossOriginIframe("https://example2.com", 200, 150);

      container.append(iframe1);
      container.append(iframe2);

      const restore = await replaceIframesForCapture(container, mockToPng);

      expect(container.querySelectorAll("iframe").length).toBe(0);
      expect(container.querySelectorAll("div").length).toBe(2);

      restore();

      const iframes = container.querySelectorAll("iframe");
      expect(iframes.length).toBe(2);
      expect(iframes[0]).toBe(iframe1);
      expect(iframes[1]).toBe(iframe2);
    });

    it("should be idempotent when called multiple times", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      const restore1 = await replaceIframesForCapture(container, mockToPng);
      restore1();

      const restore2 = await replaceIframesForCapture(container, mockToPng);
      restore2();

      expect(container.querySelectorAll("iframe").length).toBe(1);
      expect(container.querySelector("iframe")).toBe(iframe);
    });
  });

  describe("edge cases", () => {
    it("should handle empty container", async () => {
      const restore = await replaceIframesForCapture(container, mockToPng);
      restore();

      expect(container.children.length).toBe(0);
    });

    it("should handle container with no iframes", async () => {
      const div = document.createElement("div");
      div.textContent = "Hello";
      container.append(div);

      const restore = await replaceIframesForCapture(container, mockToPng);

      expect(container.querySelector("div")).toBe(div);

      restore();

      expect(container.querySelector("div")).toBe(div);
    });

    it("should skip iframes without parentNode", async () => {
      const iframe = document.createElement("iframe");
      // Don't append to container - no parentNode

      // Create a mock querySelectorAll that returns the orphan iframe
      const originalQuerySelectorAll =
        container.querySelectorAll.bind(container);
      vi.spyOn(container, "querySelectorAll").mockImplementation(
        (selector: string) => {
          if (selector === "iframe") {
            return [iframe] as unknown as NodeListOf<HTMLIFrameElement>;
          }
          return originalQuerySelectorAll(selector);
        },
      );

      const restore = await replaceIframesForCapture(container, mockToPng);
      restore();

      // Should not throw and should handle gracefully
      expect(true).toBe(true);
    });

    it("should handle iframe with null contentDocument (cross-origin)", async () => {
      const iframe = document.createElement("iframe");
      iframe.src = "https://cross-origin.example.com";
      Object.defineProperty(iframe, "offsetWidth", { value: 400 });
      Object.defineProperty(iframe, "offsetHeight", { value: 300 });
      // contentDocument is null for cross-origin iframes
      Object.defineProperty(iframe, "contentDocument", {
        value: null,
        configurable: true,
      });
      container.append(iframe);

      const restore = await replaceIframesForCapture(container, mockToPng);

      // Should create placeholder for cross-origin iframe
      const placeholder = container.querySelector("div");
      expect(placeholder).toBeTruthy();
      expect(placeholder?.textContent).toContain("cross-origin.example.com");

      restore();

      expect(container.querySelector("iframe")).toBe(iframe);
    });

    it("should handle iframe where contentDocument access throws", async () => {
      const iframe = document.createElement("iframe");
      iframe.src = "https://secure.example.com";
      Object.defineProperty(iframe, "offsetWidth", { value: 400 });
      Object.defineProperty(iframe, "offsetHeight", { value: 300 });
      // Some browsers throw when accessing contentDocument on cross-origin iframes
      Object.defineProperty(iframe, "contentDocument", {
        get() {
          throw new DOMException("Blocked by CORS");
        },
        configurable: true,
      });
      container.append(iframe);

      const restore = await replaceIframesForCapture(container, mockToPng);

      // Should create placeholder when contentDocument access throws
      const placeholder = container.querySelector("div");
      expect(placeholder).toBeTruthy();

      restore();

      expect(container.querySelector("iframe")).toBe(iframe);
    });
  });
});
