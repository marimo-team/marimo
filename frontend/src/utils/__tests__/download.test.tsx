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
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Loading...",
        duration: Infinity,
      }),
    );
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

  it("should show a finish toast when finishTitle is provided", async () => {
    await withLoadingToast(
      "Uploading files...",
      async () => "done",
      "Upload complete",
    );

    expect(toast).toHaveBeenCalledTimes(2);
    expect(toast).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        title: "Upload complete",
      }),
    );
  });

  it("should not show a finish toast when the operation fails", async () => {
    await expect(
      withLoadingToast(
        "Uploading files...",
        async () => {
          throw new Error("Upload failed");
        },
        "Upload complete",
      ),
    ).rejects.toThrow("Upload failed");

    expect(toast).toHaveBeenCalledTimes(1);
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
    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        filter: expect.any(Function),
        onImageErrorHandler: expect.any(Function),
      }),
    );
  });

  it("should pass style options to prevent clipping", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId);

    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        style: {
          maxHeight: "none",
          overflow: "visible",
        },
      }),
    );
  });

  it("should pass scrollHeight as height option", async () => {
    // Set up element with scrollHeight
    Object.defineProperty(mockElement, "scrollHeight", {
      value: 500,
      configurable: true,
    });
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId);

    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        height: 500,
      }),
    );
  });

  it("should pass scrollbar hiding styles via extraStyleContent", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId);

    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        extraStyleContent: expect.stringContaining("scrollbar-width: none"),
      }),
    );
  });

  it("should not modify the live DOM element", async () => {
    mockElement.style.overflow = "hidden";
    mockElement.style.maxHeight = "100px";
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId);

    // DOM should remain unchanged
    expect(mockElement.style.overflow).toBe("hidden");
    expect(mockElement.style.maxHeight).toBe("100px");
  });

  it("should throw error on failure", async () => {
    vi.mocked(toPng).mockRejectedValue(new Error("Capture failed"));

    await expect(getImageDataUrlForCell("cell-1" as CellId)).rejects.toThrow(
      "Capture failed",
    );
  });

  it("should handle concurrent captures correctly", async () => {
    // Create a second element
    const mockElement2 = document.createElement("div");
    mockElement2.id = CellOutputId.create("cell-2" as CellId);
    document.body.append(mockElement2);

    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    const capture1 = getImageDataUrlForCell("cell-1" as CellId);
    const capture2 = getImageDataUrlForCell("cell-2" as CellId);

    await Promise.all([capture1, capture2]);

    expect(toPng).toHaveBeenCalledTimes(2);

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

    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        filter: expect.any(Function),
        onImageErrorHandler: expect.any(Function),
      }),
    );
    expect(mockAnchor.href).toBe(mockDataUrl);
    expect(mockAnchor.download).toBe("test.png");
    expect(mockAnchor.click).toHaveBeenCalled();
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

  it("should show error toast if element not found", async () => {
    await downloadCellOutputAsImage("nonexistent" as CellId, "test");

    expect(toPng).not.toHaveBeenCalled();
    expect(Logger.error).toHaveBeenCalledWith(
      "Output element not found for cell nonexistent",
    );
    expect(toast).toHaveBeenCalledWith({
      title: "Failed to download PNG",
      description: expect.any(String),
      variant: "danger",
    });
  });

  it("should show error toast if toPng fails", async () => {
    vi.mocked(toPng).mockRejectedValue(new Error("Screenshot failed"));

    await downloadCellOutputAsImage("cell-1" as CellId, "result");

    expect(toast).toHaveBeenCalledWith({
      title: "Failed to download PNG",
      description: expect.stringContaining("Screenshot failed"),
      variant: "danger",
    });
  });

  it("should download cell output as image", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await downloadCellOutputAsImage("cell-1" as CellId, "result");

    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        filter: expect.any(Function),
        onImageErrorHandler: expect.any(Function),
      }),
    );
    expect(mockAnchor.download).toBe("result.png");
  });

  it("should pass style options to toPng for full content capture", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await downloadCellOutputAsImage("cell-1" as CellId, "result");

    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        style: {
          maxHeight: "none",
          overflow: "visible",
        },
      }),
    );
  });

  it("should not modify the live DOM element", async () => {
    mockElement.style.overflow = "hidden";
    mockElement.style.maxHeight = "100px";
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await downloadCellOutputAsImage("cell-1" as CellId, "result");

    // DOM should remain unchanged
    expect(mockElement.style.overflow).toBe("hidden");
    expect(mockElement.style.maxHeight).toBe("100px");
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
