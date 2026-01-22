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

  it("should add printing classes before capture", async () => {
    vi.mocked(toPng).mockImplementation(async () => {
      // Check classes are applied during capture
      expect(mockElement.classList.contains("printing-output")).toBe(true);
      expect(document.body.classList.contains("printing")).toBe(true);
      expect(mockElement.style.overflow).toBe("auto");
      return mockDataUrl;
    });

    await getImageDataUrlForCell("cell-1" as CellId);
  });

  it("should remove printing classes after capture", async () => {
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId);

    expect(mockElement.classList.contains("printing-output")).toBe(false);
    expect(document.body.classList.contains("printing")).toBe(false);
  });

  it("should restore original overflow style after capture", async () => {
    mockElement.style.overflow = "hidden";
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    await getImageDataUrlForCell("cell-1" as CellId);

    expect(mockElement.style.overflow).toBe("hidden");
  });

  it("should return undefined and log error on failure", async () => {
    vi.mocked(toPng).mockRejectedValue(new Error("Capture failed"));

    const result = await getImageDataUrlForCell("cell-1" as CellId);

    expect(result).toBeUndefined();
    expect(Logger.error).toHaveBeenCalledWith(
      "Failed to capture element as PNG.",
    );
  });

  it("should cleanup even on failure", async () => {
    mockElement.style.overflow = "scroll";
    vi.mocked(toPng).mockRejectedValue(new Error("Capture failed"));

    await getImageDataUrlForCell("cell-1" as CellId);

    expect(mockElement.classList.contains("printing-output")).toBe(false);
    expect(document.body.classList.contains("printing")).toBe(false);
    expect(mockElement.style.overflow).toBe("scroll");
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

  it("should not add body.printing when prepare is provided", async () => {
    vi.mocked(toPng).mockImplementation(async () => {
      // body.printing should NOT be added by downloadHTMLAsImage when prepare is provided
      // (the prepare function may add it itself)
      return mockDataUrl;
    });
    const prepare = vi.fn().mockReturnValue(() => {
      // <noop>
    });

    await downloadHTMLAsImage({
      element: mockElement,
      filename: "test",
      prepare,
    });

    // After completion, body.printing should be removed by cleanup, not downloadHTMLAsImage
    expect(document.body.classList.contains("printing")).toBe(false);
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
