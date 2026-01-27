/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CellId } from "@/core/cells/ids";
import { CellOutputId } from "@/core/cells/ids";
import {
  downloadByURL,
  downloadCellOutputAsImage,
  downloadHTMLAsImage,
  getImageDataUrlForCell,
  withLoadingToast,
} from "../download";

// Mock html-to-image
vi.mock("html-to-image", () => ({
  toPng: vi.fn(),
}));

// Mock the toast module
const mockDismiss = vi.fn();
vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(() => ({
    dismiss: mockDismiss,
  })),
}));

// Mock the Spinner component
vi.mock("@/components/icons/spinner", () => ({
  Spinner: () => "MockSpinner",
}));

// Mock Logger
vi.mock("@/utils/Logger", () => ({
  Logger: {
    error: vi.fn(),
  },
}));

// Mock Filenames
vi.mock("@/utils/filenames", () => ({
  Filenames: {
    toPNG: (name: string) => `${name}.png`,
  },
}));

import { toPng } from "html-to-image";
import { toast } from "@/components/ui/use-toast";
import { Logger } from "@/utils/Logger";

describe("withLoadingToast", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should show a loading toast and dismiss on success", async () => {
    const result = await withLoadingToast("Loading...", async () => {
      return "success";
    });

    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith({
      title: "Loading...",
      duration: Infinity,
    });
    expect(mockDismiss).toHaveBeenCalledTimes(1);
    expect(result).toBe("success");
  });

  it("should dismiss toast and rethrow on error", async () => {
    const error = new Error("Operation failed");

    await expect(
      withLoadingToast("Loading...", async () => {
        throw error;
      }),
    ).rejects.toThrow("Operation failed");

    expect(toast).toHaveBeenCalledTimes(1);
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  it("should return the value from the async function", async () => {
    const expectedValue = { data: "test", count: 42 };

    const result = await withLoadingToast("Processing...", async () => {
      return expectedValue;
    });

    expect(result).toEqual(expectedValue);
  });

  it("should handle void functions", async () => {
    let sideEffect = false;

    await withLoadingToast("Saving...", async () => {
      sideEffect = true;
    });

    expect(sideEffect).toBe(true);
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  it("should use the provided title in the toast", async () => {
    const customTitle = "Downloading PDF...";

    await withLoadingToast(customTitle, async () => "done");

    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: customTitle,
      }),
    );
  });

  it("should wait for the async function to complete", async () => {
    const events: string[] = [];

    await withLoadingToast("Loading...", async () => {
      events.push("start");
      await new Promise((resolve) => setTimeout(resolve, 10));
      events.push("end");
    });

    expect(events).toEqual(["start", "end"]);
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });
});

describe("getImageDataUrlForCell", () => {
  const mockDataUrl = "data:image/png;base64,mockbase64data";
  let mockElement: HTMLElement;

  beforeEach(() => {
    vi.clearAllMocks();
    mockElement = document.createElement("div");
    mockElement.id = CellOutputId.create("cell-1" as CellId);
    document.body.append(mockElement);
  });

  afterEach(() => {
    mockElement.remove();
  });

  it("should return undefined if element is not found", async () => {
    const result = await getImageDataUrlForCell("nonexistent" as CellId);

    expect(result).toBeUndefined();
    expect(Logger.error).toHaveBeenCalledWith(
      "Output element not found for cell nonexistent",
    );
  });

  it("should capture screenshot and return data URL", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    const result = await getImageDataUrlForCell("cell-1" as CellId);

    expect(result).toBe(mockDataUrl);
    expect(toPng).toHaveBeenCalledWith(mockElement);
  });

  it("should add printing classes before capture when enablePrintMode is true", async () => {
    vi.mocked(toPng).mockImplementation(async () => {
      // Check classes are applied during capture
      expect(mockElement.classList.contains("printing-output")).toBe(true);
      expect(document.body.classList.contains("printing")).toBe(true);
      expect(mockElement.style.overflow).toBe("auto");
      return mockDataUrl;
    });

    await getImageDataUrlForCell("cell-1" as CellId, true);
  });

  it("should remove printing classes after capture when enablePrintMode is true", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId, true);

    expect(mockElement.classList.contains("printing-output")).toBe(false);
    expect(document.body.classList.contains("printing")).toBe(false);
  });

  it("should add printing-output but NOT body.printing when enablePrintMode is false", async () => {
    vi.mocked(toPng).mockImplementation(async () => {
      // printing-output should still be added to the element
      expect(mockElement.classList.contains("printing-output")).toBe(true);
      // but body.printing should NOT be added
      expect(document.body.classList.contains("printing")).toBe(false);
      expect(mockElement.style.overflow).toBe("auto");
      return mockDataUrl;
    });

    await getImageDataUrlForCell("cell-1" as CellId, false);
  });

  it("should cleanup printing-output when enablePrintMode is false", async () => {
    mockElement.style.overflow = "hidden";
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId, false);

    expect(mockElement.classList.contains("printing-output")).toBe(false);
    expect(document.body.classList.contains("printing")).toBe(false);
    expect(mockElement.style.overflow).toBe("hidden");
  });

  it("should restore original overflow style after capture", async () => {
    mockElement.style.overflow = "hidden";
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId);

    expect(mockElement.style.overflow).toBe("hidden");
  });

  it("should throw error on failure", async () => {
    vi.mocked(toPng).mockRejectedValue(new Error("Capture failed"));

    await expect(getImageDataUrlForCell("cell-1" as CellId)).rejects.toThrow(
      "Capture failed",
    );
  });

  it("should cleanup even on failure", async () => {
    mockElement.style.overflow = "scroll";
    vi.mocked(toPng).mockRejectedValue(new Error("Capture failed"));

    await expect(getImageDataUrlForCell("cell-1" as CellId)).rejects.toThrow();

    expect(mockElement.classList.contains("printing-output")).toBe(false);
    expect(document.body.classList.contains("printing")).toBe(false);
    expect(mockElement.style.overflow).toBe("scroll");
  });

  it("should maintain body.printing during concurrent captures when enablePrintMode is true", async () => {
    // Create a second element
    const mockElement2 = document.createElement("div");
    mockElement2.id = CellOutputId.create("cell-2" as CellId);
    document.body.append(mockElement2);

    // Track body.printing state during each capture
    const printingStateDuringCaptures: boolean[] = [];
    let resolveFirst: () => void;
    let resolveSecond: () => void;

    const firstPromise = new Promise<void>((resolve) => {
      resolveFirst = resolve;
    });
    const secondPromise = new Promise<void>((resolve) => {
      resolveSecond = resolve;
    });

    vi.mocked(toPng).mockImplementation(async (element) => {
      printingStateDuringCaptures.push(
        document.body.classList.contains("printing"),
      );

      // Simulate async work - first capture takes longer
      await (element.id.includes("cell-1") ? firstPromise : secondPromise);

      // Check state again after waiting
      printingStateDuringCaptures.push(
        document.body.classList.contains("printing"),
      );

      return mockDataUrl;
    });

    // Start both captures concurrently with enablePrintMode = true
    const capture1 = getImageDataUrlForCell("cell-1" as CellId, true);
    const capture2 = getImageDataUrlForCell("cell-2" as CellId, true);

    // Let second capture complete first
    resolveSecond!();
    await new Promise((r) => setTimeout(r, 0));

    // body.printing should still be present because cell-1 is still capturing
    expect(document.body.classList.contains("printing")).toBe(true);

    // Now let first capture complete
    resolveFirst!();
    await Promise.all([capture1, capture2]);

    // After all captures complete, body.printing should be removed
    expect(document.body.classList.contains("printing")).toBe(false);

    // All captures should have seen body.printing = true
    expect(printingStateDuringCaptures.every(Boolean)).toBe(true);

    mockElement2.remove();
  });

  it("should not interfere with body.printing during concurrent captures when enablePrintMode is false", async () => {
    // Create a second element
    const mockElement2 = document.createElement("div");
    mockElement2.id = CellOutputId.create("cell-2" as CellId);
    document.body.append(mockElement2);

    vi.mocked(toPng).mockImplementation(async () => {
      // body.printing should never be added when enablePrintMode is false
      expect(document.body.classList.contains("printing")).toBe(false);
      return mockDataUrl;
    });

    // Start both captures concurrently with enablePrintMode = false
    const capture1 = getImageDataUrlForCell("cell-1" as CellId, false);
    const capture2 = getImageDataUrlForCell("cell-2" as CellId, false);

    await Promise.all([capture1, capture2]);

    // body.printing should still not be present
    expect(document.body.classList.contains("printing")).toBe(false);

    mockElement2.remove();
  });
});

describe("downloadHTMLAsImage", () => {
  const mockDataUrl = "data:image/png;base64,mockbase64data";
  let mockElement: HTMLElement;
  let mockAppEl: HTMLElement;
  let mockAnchor: HTMLAnchorElement;

  beforeEach(() => {
    vi.clearAllMocks();
    mockElement = document.createElement("div");
    mockAppEl = document.createElement("div");
    mockAppEl.id = "App";
    // Mock scrollTo since jsdom doesn't implement it
    mockAppEl.scrollTo = vi.fn();
    document.body.append(mockElement);
    document.body.append(mockAppEl);

    // Mock anchor element for download
    mockAnchor = document.createElement("a");
    vi.spyOn(document, "createElement").mockReturnValue(mockAnchor);
    vi.spyOn(mockAnchor, "click").mockImplementation(() => {
      // <noop></noop>
    });
    vi.spyOn(mockAnchor, "remove").mockImplementation(() => {
      // noop
    });
  });

  afterEach(() => {
    mockElement.remove();
    mockAppEl.remove();
    vi.restoreAllMocks();
  });

  it("should download image without prepare function", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await downloadHTMLAsImage({ element: mockElement, filename: "test" });

    expect(toPng).toHaveBeenCalledWith(mockElement);
    expect(mockAnchor.href).toBe(mockDataUrl);
    expect(mockAnchor.download).toBe("test.png");
    expect(mockAnchor.click).toHaveBeenCalled();
  });

  it("should add body.printing class without prepare function", async () => {
    vi.mocked(toPng).mockImplementation(async () => {
      expect(document.body.classList.contains("printing")).toBe(true);
      return mockDataUrl;
    });

    await downloadHTMLAsImage({ element: mockElement, filename: "test" });
  });

  it("should remove body.printing class after download without prepare", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await downloadHTMLAsImage({ element: mockElement, filename: "test" });

    expect(document.body.classList.contains("printing")).toBe(false);
  });

  it("should use prepare function when provided", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);
    const cleanup = vi.fn();
    const prepare = vi.fn().mockReturnValue(cleanup);

    await downloadHTMLAsImage({
      element: mockElement,
      filename: "test",
      prepare,
    });

    expect(prepare).toHaveBeenCalledWith(mockElement);
    expect(cleanup).toHaveBeenCalled();
  });

  it("should delegate body.printing management to prepare function", async () => {
    let bodyPrintingDuringCapture = false;
    vi.mocked(toPng).mockImplementation(async () => {
      // Capture the state during toPng execution
      bodyPrintingDuringCapture = document.body.classList.contains("printing");
      return mockDataUrl;
    });
    const cleanup = vi.fn();
    // Mock prepare that adds body.printing
    const prepare = vi.fn().mockImplementation(() => {
      document.body.classList.add("printing");
      return () => {
        document.body.classList.remove("printing");
        cleanup();
      };
    });

    await downloadHTMLAsImage({
      element: mockElement,
      filename: "test",
      prepare,
    });

    // body.printing should be added by prepare function
    expect(bodyPrintingDuringCapture).toBe(true);
    expect(document.body.classList.contains("printing")).toBe(false);
    expect(prepare).toHaveBeenCalledWith(mockElement);
    expect(cleanup).toHaveBeenCalled();
  });

  it("should show error toast on failure", async () => {
    vi.mocked(toPng).mockRejectedValue(new Error("Failed"));

    await downloadHTMLAsImage({ element: mockElement, filename: "test" });

    expect(toast).toHaveBeenCalledWith({
      title: "Error",
      description: "Failed to download as PNG.",
      variant: "danger",
    });
  });

  it("should cleanup on failure", async () => {
    vi.mocked(toPng).mockRejectedValue(new Error("Failed"));

    await downloadHTMLAsImage({ element: mockElement, filename: "test" });

    expect(document.body.classList.contains("printing")).toBe(false);
  });
});

describe("downloadCellOutputAsImage", () => {
  const mockDataUrl = "data:image/png;base64,mockbase64data";
  let mockElement: HTMLElement;
  let mockAppEl: HTMLElement;
  let mockAnchor: HTMLAnchorElement;

  beforeEach(() => {
    vi.clearAllMocks();
    mockElement = document.createElement("div");
    mockElement.id = CellOutputId.create("cell-1" as CellId);
    mockAppEl = document.createElement("div");
    mockAppEl.id = "App";
    // Mock scrollTo since jsdom doesn't implement it
    mockAppEl.scrollTo = vi.fn();
    document.body.append(mockElement);
    document.body.append(mockAppEl);

    mockAnchor = document.createElement("a");
    vi.spyOn(document, "createElement").mockReturnValue(mockAnchor);
    vi.spyOn(mockAnchor, "click").mockImplementation(() => {
      // <noop></noop>
    });
    vi.spyOn(mockAnchor, "remove").mockImplementation(() => {
      // <noop></noop>
    });
  });

  afterEach(() => {
    mockElement.remove();
    mockAppEl.remove();
    vi.restoreAllMocks();
  });

  it("should return early if element not found", async () => {
    await downloadCellOutputAsImage("nonexistent" as CellId, "test");

    expect(toPng).not.toHaveBeenCalled();
    expect(Logger.error).toHaveBeenCalledWith(
      "Output element not found for cell nonexistent",
    );
  });

  it("should download cell output as image", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await downloadCellOutputAsImage("cell-1" as CellId, "result");

    expect(toPng).toHaveBeenCalledWith(mockElement);
    expect(mockAnchor.download).toBe("result.png");
  });

  it("should apply cell-specific preparation", async () => {
    vi.mocked(toPng).mockImplementation(async () => {
      // Check that cell-specific classes are applied
      expect(mockElement.classList.contains("printing-output")).toBe(true);
      expect(document.body.classList.contains("printing")).toBe(true);
      expect(mockElement.style.overflow).toBe("auto");
      return mockDataUrl;
    });

    await downloadCellOutputAsImage("cell-1" as CellId, "result");
  });

  it("should cleanup after download", async () => {
    mockElement.style.overflow = "visible";
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await downloadCellOutputAsImage("cell-1" as CellId, "result");

    expect(mockElement.classList.contains("printing-output")).toBe(false);
    expect(document.body.classList.contains("printing")).toBe(false);
    expect(mockElement.style.overflow).toBe("visible");
  });

  it("should apply preparation to iframe clone, not original", async () => {
    const iframe = document.createElement("iframe");
    iframe.src = "https://example.com";
    Object.defineProperty(iframe, "offsetWidth", { value: 400 });
    Object.defineProperty(iframe, "offsetHeight", { value: 300 });
    Object.defineProperty(iframe, "contentDocument", {
      value: null,
      configurable: true,
    });
    mockElement.append(iframe);

    vi.mocked(toPng).mockImplementation(async (el: HTMLElement) => {
      expect(el).not.toBe(mockElement);
      expect(el.classList.contains("printing-output")).toBe(true);
      expect(mockElement.classList.contains("printing-output")).toBe(false);
      return mockDataUrl;
    });

    expect(mockElement.querySelector("iframe")).not.toBeNull();

    await downloadCellOutputAsImage("cell-1" as CellId, "result");
  });
});

describe("downloadByURL", () => {
  let mockAnchor: HTMLAnchorElement;

  beforeEach(() => {
    mockAnchor = document.createElement("a");
    vi.spyOn(document, "createElement").mockReturnValue(mockAnchor);
    vi.spyOn(mockAnchor, "click").mockImplementation(() => {
      // <noop></noop>
    });
    vi.spyOn(mockAnchor, "remove").mockImplementation(() => {
      // <noop></noop>
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should create anchor, set attributes, click, and remove", () => {
    downloadByURL("data:test", "filename.png");

    expect(document.createElement).toHaveBeenCalledWith("a");
    expect(mockAnchor.href).toBe("data:test");
    expect(mockAnchor.download).toBe("filename.png");
    expect(mockAnchor.click).toHaveBeenCalled();
    expect(mockAnchor.remove).toHaveBeenCalled();
  });
});

describe("iframe handling in getImageDataUrlForCell", () => {
  const mockDataUrl = "data:image/png;base64,mockbase64data";
  let mockElement: HTMLElement;

  beforeEach(() => {
    vi.clearAllMocks();
    mockElement = document.createElement("div");
    mockElement.id = CellOutputId.create("cell-iframe" as CellId);
    document.body.append(mockElement);
  });

  afterEach(() => {
    mockElement.remove();
  });

  it("should replace cross-origin iframes with placeholders during capture", async () => {
    // Create a cross-origin iframe (contentDocument will be null)
    const iframe = document.createElement("iframe");
    iframe.src = "https://example.com";
    // Set dimensions for placeholder
    Object.defineProperty(iframe, "offsetWidth", { value: 400 });
    Object.defineProperty(iframe, "offsetHeight", { value: 300 });
    mockElement.append(iframe);

    let capturedElement: HTMLElement | null = null;
    vi.mocked(toPng).mockImplementation(async (el: HTMLElement | null) => {
      capturedElement = el;
      if (!capturedElement) {
        throw new Error("Capture failed");
      }
      // During capture, iframe should be replaced with placeholder
      const iframes = capturedElement.querySelectorAll("iframe");
      expect(iframes.length).toBe(0);

      const placeholder = capturedElement.querySelector("div");
      expect(placeholder).toBeTruthy();
      expect(placeholder?.textContent).toContain("Embedded");

      return mockDataUrl;
    });

    await getImageDataUrlForCell("cell-iframe" as CellId);

    // After capture, iframe should be restored
    const iframes = mockElement.querySelectorAll("iframe");
    expect(iframes.length).toBe(1);
    expect(iframes[0]).toBe(iframe);
  });

  it("should restore iframes even if capture fails", async () => {
    const iframe = document.createElement("iframe");
    iframe.src = "https://example.com";
    Object.defineProperty(iframe, "offsetWidth", { value: 400 });
    Object.defineProperty(iframe, "offsetHeight", { value: 300 });
    mockElement.append(iframe);

    vi.mocked(toPng).mockRejectedValue(new Error("Capture failed"));

    await expect(
      getImageDataUrlForCell("cell-iframe" as CellId),
    ).rejects.toThrow("Capture failed");

    // Iframe should still be restored
    const iframes = mockElement.querySelectorAll("iframe");
    expect(iframes.length).toBe(1);
    expect(iframes[0]).toBe(iframe);
  });

  it("should handle multiple iframes", async () => {
    const iframe1 = document.createElement("iframe");
    iframe1.src = "https://example1.com";
    Object.defineProperty(iframe1, "offsetWidth", { value: 400 });
    Object.defineProperty(iframe1, "offsetHeight", { value: 300 });

    const iframe2 = document.createElement("iframe");
    iframe2.src = "https://example2.com";
    Object.defineProperty(iframe2, "offsetWidth", { value: 200 });
    Object.defineProperty(iframe2, "offsetHeight", { value: 150 });

    mockElement.append(iframe1);
    mockElement.append(iframe2);

    vi.mocked(toPng).mockImplementation(async (el) => {
      const iframes = el.querySelectorAll("iframe");
      expect(iframes.length).toBe(0);
      return mockDataUrl;
    });

    await getImageDataUrlForCell("cell-iframe" as CellId);

    // Both iframes should be restored
    const iframes = mockElement.querySelectorAll("iframe");
    expect(iframes.length).toBe(2);
  });

  it("should handle nested iframes (mo.iframe with embedded content)", async () => {
    // Simulate mo.iframe() which creates a same-origin iframe containing cross-origin embed
    const outerIframe = document.createElement("iframe");
    Object.defineProperty(outerIframe, "offsetWidth", { value: 420 });
    Object.defineProperty(outerIframe, "offsetHeight", { value: 315 });

    // Create mock body with nested cross-origin iframe
    const mockBody = document.createElement("body");
    const nestedIframe = document.createElement("iframe");
    nestedIframe.src = "https://www.youtube.com/embed/abc123";
    Object.defineProperty(nestedIframe, "offsetWidth", { value: 420 });
    Object.defineProperty(nestedIframe, "offsetHeight", { value: 315 });
    mockBody.append(nestedIframe);

    // Mock contentDocument to simulate same-origin iframe
    Object.defineProperty(outerIframe, "contentDocument", {
      value: { body: mockBody },
      configurable: true,
    });

    mockElement.append(outerIframe);

    vi.mocked(toPng).mockImplementation(async (el: HTMLElement) => {
      // When capturing the outer iframe's body, nested iframes should be placeholders
      if (el === mockBody) {
        const nestedIframes = el.querySelectorAll("iframe");
        expect(nestedIframes.length).toBe(0);
        const placeholder = el.querySelector("div");
        expect(placeholder?.textContent).toContain("youtube.com");
      }
      return mockDataUrl;
    });

    await getImageDataUrlForCell("cell-iframe" as CellId);

    // After capture, nested iframe should be restored
    const restoredNested = mockBody.querySelector("iframe");
    expect(restoredNested).toBe(nestedIframe);
  });
});
