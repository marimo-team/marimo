/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getIframeCaptureTarget } from "../iframe";

// Mock Logger
vi.mock("@/utils/Logger", () => ({
  Logger: {
    debug: vi.fn(),
    error: vi.fn(),
  },
}));

describe("getIframeCaptureTarget", () => {
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
   * Helper to create a cross-origin iframe (contentDocument is null in jsdom)
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

    const mockBody = document.createElement("body");
    mockBody.innerHTML = bodyContent;

    Object.defineProperty(iframe, "contentDocument", {
      value: { body: mockBody },
      configurable: true,
    });

    return iframe;
  }

  describe("no iframes present", () => {
    it("should return original element when no iframes exist", async () => {
      const div = document.createElement("div");
      div.textContent = "No iframes here";
      container.append(div);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      expect(target).toBe(container);
      expect(document.querySelectorAll("[aria-hidden='true']").length).toBe(0);

      cleanup?.();
    });

    it("should not call toPng when no iframes exist", async () => {
      container.innerHTML = "<p>Just text</p>";

      await getIframeCaptureTarget(container, mockToPng);

      expect(mockToPng).not.toHaveBeenCalled();
    });

    it("should return original element for empty container", async () => {
      const { target } = await getIframeCaptureTarget(container, mockToPng);

      expect(target).toBe(container);
    });
  });

  describe("with iframes present", () => {
    it("should create offscreen clone when iframes exist", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      // Should return a clone, not the original
      expect(target).not.toBe(container);
      // Original should still have iframe
      expect(container.querySelector("iframe")).toBe(iframe);
      // Clone should have placeholder instead of iframe
      expect(target.querySelector("iframe")).toBeNull();
      expect(target.querySelector("div")).toBeTruthy();

      // Offscreen container should exist
      const offscreenContainer = document.querySelector("[aria-hidden='true']");
      expect(offscreenContainer).toBeTruthy();
      expect((offscreenContainer as HTMLElement).style.left).toBe("-10000px");

      cleanup?.();

      // Offscreen container should be removed after cleanup
      expect(document.querySelector("[aria-hidden='true']")).toBeNull();
    });

    it("should not mutate original element", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      const originalHTML = container.innerHTML;

      const { cleanup } = await getIframeCaptureTarget(container, mockToPng);

      // Original should be unchanged
      expect(container.innerHTML).toBe(originalHTML);
      expect(container.querySelector("iframe")).toBe(iframe);

      cleanup?.();

      // Still unchanged after cleanup
      expect(container.innerHTML).toBe(originalHTML);
    });

    it("should preserve other content in clone", async () => {
      const text = document.createElement("p");
      text.textContent = "Some text";
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);

      container.append(text);
      container.append(iframe);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      expect(target.querySelector("p")?.textContent).toBe("Some text");
      expect(target.querySelector("iframe")).toBeNull();

      cleanup?.();
    });
  });

  describe("placeholder creation", () => {
    it("should create placeholder with correct dimensions", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 420, 315);
      container.append(iframe);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      const placeholder = target.querySelector("div")!;
      expect(placeholder.style.width).toBe("420px");
      expect(placeholder.style.height).toBe("315px");

      cleanup?.();
    });

    it("should create placeholder with hostname label", async () => {
      const iframe = createCrossOriginIframe(
        "https://www.youtube.com/embed/abc123",
        400,
        300,
      );
      container.append(iframe);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      const placeholder = target.querySelector("div")!;
      expect(placeholder.textContent).toBe("[Embedded: www.youtube.com]");

      cleanup?.();
    });

    it("should apply visual styles for placeholder", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      const placeholder = target.querySelector("div")!;
      expect(placeholder.style.backgroundColor).toBe("rgb(245, 245, 245)");
      expect(placeholder.style.display).toBe("flex");
      expect(placeholder.style.alignItems).toBe("center");
      expect(placeholder.style.justifyContent).toBe("center");
      expect(placeholder.style.border).toBe("1px dashed rgb(204, 204, 204)");

      cleanup?.();
    });
  });

  describe("same-origin iframe capture", () => {
    it("should capture same-origin iframe and replace with image", async () => {
      const iframe = createSameOriginIframe("<p>Hello</p>", 400, 300);
      container.append(iframe);

      const capturedDataUrl = "data:image/png;base64,captured";
      mockToPng.mockResolvedValue(capturedDataUrl);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      expect(mockToPng).toHaveBeenCalled();

      const img = target.querySelector("img");
      expect(img).toBeTruthy();
      expect(img?.src).toBe(capturedDataUrl);
      expect(img?.style.width).toBe("400px");
      expect(img?.style.height).toBe("300px");

      cleanup?.();
    });

    it("should fall back to placeholder when capture fails", async () => {
      const iframe = createSameOriginIframe("<p>Hello</p>", 400, 300);
      container.append(iframe);

      mockToPng.mockRejectedValue(new Error("Capture failed"));

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      // Should fall back to placeholder
      const placeholder = target.querySelector("div");
      expect(placeholder).toBeTruthy();
      expect(placeholder?.textContent).toBe("[Embedded content]");

      cleanup?.();
    });
  });

  describe("nested iframes", () => {
    it("should handle nested cross-origin iframes within same-origin iframe", async () => {
      const iframe = document.createElement("iframe");
      Object.defineProperty(iframe, "offsetWidth", { value: 420 });
      Object.defineProperty(iframe, "offsetHeight", { value: 315 });

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
        // During capture, nested iframes should be replaced with placeholders
        const nestedIframes = el.querySelectorAll("iframe");
        expect(nestedIframes.length).toBe(0);

        const placeholder = el.querySelector("div");
        expect(placeholder).toBeTruthy();
        expect(placeholder?.textContent).toContain("youtube.com");

        return "data:image/png;base64,captured";
      });

      const { cleanup } = await getIframeCaptureTarget(container, mockToPng);

      expect(capturedBody).toBe(mockBody);

      // After capture, nested iframe should be restored in the original
      const restoredNested = mockBody.querySelector("iframe");
      expect(restoredNested).toBe(nestedIframe);

      cleanup?.();
    });
  });

  describe("multiple iframes", () => {
    it("should handle multiple iframes", async () => {
      const iframe1 = createCrossOriginIframe("https://example1.com", 400, 300);
      const iframe2 = createCrossOriginIframe("https://example2.com", 200, 150);

      container.append(iframe1);
      container.append(iframe2);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      // Clone should have 2 placeholders
      expect(target.querySelectorAll("div").length).toBe(2);
      expect(target.querySelectorAll("iframe").length).toBe(0);

      // Original should be unchanged
      expect(container.querySelectorAll("iframe").length).toBe(2);

      cleanup?.();
    });
  });

  describe("cleanup behavior", () => {
    it("should remove offscreen container after cleanup", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      const containersBefore = document.querySelectorAll(
        "[aria-hidden='true']",
      ).length;

      const { cleanup } = await getIframeCaptureTarget(container, mockToPng);

      expect(
        document.querySelectorAll("[aria-hidden='true']").length,
      ).toBeGreaterThan(containersBefore);

      cleanup?.();

      expect(document.querySelectorAll("[aria-hidden='true']").length).toBe(
        containersBefore,
      );
    });

    it("should not leave orphaned containers after multiple calls", async () => {
      const iframe = createCrossOriginIframe("https://example.com", 400, 300);
      container.append(iframe);

      const containersBefore = document.querySelectorAll(
        "[aria-hidden='true']",
      ).length;

      for (let i = 0; i < 3; i++) {
        const { cleanup } = await getIframeCaptureTarget(container, mockToPng);
        cleanup?.();
      }

      expect(document.querySelectorAll("[aria-hidden='true']").length).toBe(
        containersBefore,
      );
    });
  });

  describe("edge cases", () => {
    it("should handle iframe with null contentDocument (cross-origin)", async () => {
      const iframe = document.createElement("iframe");
      iframe.src = "https://cross-origin.example.com";
      Object.defineProperty(iframe, "offsetWidth", { value: 400 });
      Object.defineProperty(iframe, "offsetHeight", { value: 300 });
      Object.defineProperty(iframe, "contentDocument", {
        value: null,
        configurable: true,
      });
      container.append(iframe);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      const placeholder = target.querySelector("div");
      expect(placeholder).toBeTruthy();
      expect(placeholder?.textContent).toContain("cross-origin.example.com");

      cleanup?.();
    });

    it("should handle iframe where contentDocument access throws", async () => {
      const iframe = document.createElement("iframe");
      iframe.src = "https://secure.example.com";
      Object.defineProperty(iframe, "offsetWidth", { value: 400 });
      Object.defineProperty(iframe, "offsetHeight", { value: 300 });
      Object.defineProperty(iframe, "contentDocument", {
        get() {
          throw new DOMException("Blocked by CORS");
        },
        configurable: true,
      });
      container.append(iframe);

      const { target, cleanup } = await getIframeCaptureTarget(
        container,
        mockToPng,
      );

      const placeholder = target.querySelector("div");
      expect(placeholder).toBeTruthy();

      cleanup?.();
    });
  });
});
