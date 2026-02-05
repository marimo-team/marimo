/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CellId } from "@/core/cells/ids";
import { CellOutputId } from "@/core/cells/ids";
import type { CellRuntimeState } from "@/core/cells/types";
import { ProgressState } from "@/utils/progress";
import {
  captureTracker,
  updateCellOutputsWithScreenshots,
  useEnrichCellOutputs,
} from "../hooks";

// Mock html-to-image
vi.mock("html-to-image", () => ({
  toPng: vi.fn(),
}));

// Mock Logger
vi.mock("@/utils/Logger", () => ({
  Logger: {
    error: vi.fn(),
  },
}));

// Mock toast
vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

// Mock cellsRuntimeAtom - must be defined inline in the factory function
vi.mock("@/core/cells/cells", async () => {
  const { atom } = await import("jotai");
  return {
    cellsRuntimeAtom: atom({}),
  };
});

const progress = ProgressState.indeterminate();

import { toPng } from "html-to-image";
import { toast } from "@/components/ui/use-toast";
import { cellsRuntimeAtom } from "@/core/cells/cells";
import { Logger } from "@/utils/Logger";

describe("useEnrichCellOutputs", () => {
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    vi.clearAllMocks();
    store = createStore();
    captureTracker.reset();
  });

  const wrapper = ({ children }: { children: ReactNode }) =>
    React.createElement(Provider, { store }, children);

  // Helper to set the mocked atom (cast to any to work around type mismatch)
  const setCellsRuntime = (value: Record<CellId, CellRuntimeState>) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    store.set(cellsRuntimeAtom as any, value);
  };

  const createMockCellRuntimes = (
    cells: Record<string, Partial<CellRuntimeState>>,
  ): Record<CellId, CellRuntimeState> => {
    return Object.fromEntries(
      Object.entries(cells).map(([cellId, cell]) => [
        cellId as CellId,
        {
          output: cell.output || null,
          status: cell.status || "idle",
          interrupted: false,
          errored: false,
          runStartTimestamp: null,
          runElapsedTimeMs: null,
          stallTime: null as unknown as number,
          ...cell,
        } as CellRuntimeState,
      ]),
    ) as Record<CellId, CellRuntimeState>;
  };

  it("should return empty object when no cells need screenshots", async () => {
    vi.spyOn(document, "getElementById");

    // Set up cell runtimes with no text/html outputs
    setCellsRuntime(
      createMockCellRuntimes({
        "cell-1": {
          output: {
            channel: "output",
            mimetype: "text/plain",
            data: "Hello World",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    expect(output).toEqual({});
    expect(document.getElementById).not.toHaveBeenCalled();
    expect(toPng).not.toHaveBeenCalled();
  });

  it("should capture screenshots for cells with text/html output", async () => {
    const cellId = "cell-1" as CellId;
    const mockElement = document.createElement("div");
    const mockDataUrl = "data:image/png;base64,mockImageData";

    // Mock document.getElementById
    vi.spyOn(document, "getElementById").mockReturnValue(mockElement);
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    expect(document.getElementById).toHaveBeenCalledWith(
      CellOutputId.create(cellId),
    );
    expect(toPng).toHaveBeenCalledWith(
      mockElement,
      expect.objectContaining({
        filter: expect.any(Function),
        onImageErrorHandler: expect.any(Function),
      }),
    );
    expect(output).toEqual({
      [cellId]: ["image/png", mockDataUrl],
    });
  });

  it("should skip cells where output has not changed", async () => {
    const cellId = "cell-1" as CellId;
    const mockElement = document.createElement("div");
    const mockDataUrl = "data:image/png;base64,mockImageData";
    const htmlData = "<div>Chart</div>";

    vi.spyOn(document, "getElementById").mockReturnValue(mockElement);
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: htmlData,
            timestamp: 0,
          },
        },
      }),
    );

    const { result, rerender } = renderHook(() => useEnrichCellOutputs(), {
      wrapper,
    });

    // First call - should capture
    let takeScreenshots = result.current;
    let output = await takeScreenshots({ progress });
    expect(output).toEqual({ [cellId]: ["image/png", mockDataUrl] });
    expect(toPng).toHaveBeenCalledTimes(1);

    // Rerender to get updated atom state
    rerender();

    // Second call with same output - should not capture again
    takeScreenshots = result.current;
    output = await takeScreenshots({ progress });
    expect(output).toEqual({}); // Empty because output hasn't changed
    expect(toPng).toHaveBeenCalledTimes(1); // Still only 1 call
  });

  it("should handle screenshot errors gracefully", async () => {
    const cellId = "cell-1" as CellId;
    const mockElement = document.createElement("div");
    const error = new Error("Screenshot failed");

    vi.spyOn(document, "getElementById").mockReturnValue(mockElement);
    vi.mocked(toPng).mockRejectedValue(error);

    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    expect(output).toEqual({}); // Failed screenshot should be filtered out
    expect(Logger.error).toHaveBeenCalledWith(
      `Error screenshotting cell ${cellId}:`,
      error,
    );
  });

  it("should retry failed screenshots on next call", async () => {
    const cellId = "cell-1" as CellId;
    const mockElement = document.createElement("div");
    const error = new Error("Screenshot failed");
    const mockDataUrl = "data:image/png;base64,retrySuccess";

    vi.spyOn(document, "getElementById").mockReturnValue(mockElement);
    // First call fails, second call succeeds
    vi.mocked(toPng)
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce(mockDataUrl);

    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result, rerender } = renderHook(() => useEnrichCellOutputs(), {
      wrapper,
    });

    // First call - screenshot fails
    let takeScreenshots = result.current;
    let output = await takeScreenshots({ progress });
    expect(output).toEqual({});
    expect(Logger.error).toHaveBeenCalled();

    rerender();

    // Second call - should retry since the first one failed
    takeScreenshots = result.current;
    output = await takeScreenshots({ progress });
    expect(output).toEqual({ [cellId]: ["image/png", mockDataUrl] });
    expect(toPng).toHaveBeenCalledTimes(2);
  });

  it("should handle missing DOM elements", async () => {
    const cellId = "cell-1" as CellId;

    vi.spyOn(document, "getElementById").mockReturnValue(null);

    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    expect(output).toEqual({});
    expect(Logger.error).toHaveBeenCalledWith(
      `Output element not found for cell ${cellId}`,
    );
    expect(toPng).not.toHaveBeenCalled();
  });

  it("should process multiple cells in parallel", async () => {
    const cell1 = "cell-1" as CellId;
    const cell2 = "cell-2" as CellId;
    const mockElement1 = document.createElement("div");
    const mockElement2 = document.createElement("div");
    const mockDataUrl1 = "data:image/png;base64,image1";
    const mockDataUrl2 = "data:image/png;base64,image2";

    vi.spyOn(document, "getElementById")
      .mockReturnValueOnce(mockElement1)
      .mockReturnValueOnce(mockElement2);

    vi.mocked(toPng)
      .mockResolvedValueOnce(mockDataUrl1)
      .mockResolvedValueOnce(mockDataUrl2);

    setCellsRuntime(
      createMockCellRuntimes({
        [cell1]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart 1</div>",
            timestamp: 0,
          },
        },
        [cell2]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart 2</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    expect(output).toEqual({
      [cell1]: ["image/png", mockDataUrl1],
      [cell2]: ["image/png", mockDataUrl2],
    });
    expect(toPng).toHaveBeenCalledTimes(2);
  });

  it("should filter out null results from failed screenshots", async () => {
    // Setup: one successful, one failed screenshot
    const cell1 = "cell-1" as CellId;
    const cell2 = "cell-2" as CellId;
    const mockElement1 = document.createElement("div");
    const mockDataUrl = "data:image/png;base64,image1";

    vi.spyOn(document, "getElementById")
      .mockReturnValueOnce(mockElement1)
      .mockReturnValueOnce(null); // Second cell fails to find element

    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    setCellsRuntime(
      createMockCellRuntimes({
        [cell1]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart 1</div>",
            timestamp: 0,
          },
        },
        [cell2]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart 2</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    // Only the successful screenshot should be in the result
    expect(output).toEqual({
      [cell1]: ["image/png", mockDataUrl],
    });
    expect(Logger.error).toHaveBeenCalledWith(
      `Output element not found for cell ${cell2}`,
    );
  });

  it("should only capture screenshots for cells with changed output", async () => {
    const cellId = "cell-1" as CellId;
    const mockElement = document.createElement("div");
    const mockDataUrl1 = "data:image/png;base64,image1";
    const mockDataUrl2 = "data:image/png;base64,image2";

    vi.spyOn(document, "getElementById").mockReturnValue(mockElement);
    vi.mocked(toPng)
      .mockResolvedValueOnce(mockDataUrl1)
      .mockResolvedValueOnce(mockDataUrl2);

    // First call - cell should be captured
    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart v1</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result, rerender } = renderHook(() => useEnrichCellOutputs(), {
      wrapper,
    });

    // First screenshot
    let takeScreenshots = result.current;
    let output = await takeScreenshots({ progress });
    expect(output).toEqual({ [cellId]: ["image/png", mockDataUrl1] });

    // Second call - same output, should not be captured
    rerender();
    takeScreenshots = result.current;
    output = await takeScreenshots({ progress });
    expect(output).toEqual({});

    // Third call - output changed, should be captured
    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Chart v2</div>", // Changed!
            timestamp: 0,
          },
        },
      }),
    );

    rerender();
    takeScreenshots = result.current;
    output = await takeScreenshots({ progress });
    expect(output).toEqual({ [cellId]: ["image/png", mockDataUrl2] });
    expect(toPng).toHaveBeenCalledTimes(2);
  });

  it("should ignore cells with non-text/html mimetype", async () => {
    vi.spyOn(document, "getElementById");

    setCellsRuntime(
      createMockCellRuntimes({
        "cell-1": {
          output: {
            channel: "output",
            mimetype: "application/json",
            data: '{"key": "value"}',
            timestamp: 0,
          },
        },
        "cell-2": {
          output: {
            channel: "output",
            mimetype: "text/plain",
            data: "Plain text",
            timestamp: 0,
          },
        },
        "cell-3": {
          output: {
            channel: "output",
            mimetype: "image/png",
            data: "data:image/png;base64,existing",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    // None of these should trigger screenshots
    expect(output).toEqual({});
    expect(document.getElementById).not.toHaveBeenCalled();
    expect(toPng).not.toHaveBeenCalled();
  });

  it("should ignore cells with null or undefined output", async () => {
    vi.spyOn(document, "getElementById");

    setCellsRuntime(
      createMockCellRuntimes({
        "cell-1": {
          output: null,
        },
        "cell-2": {
          output: undefined,
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    expect(output).toEqual({});
    expect(document.getElementById).not.toHaveBeenCalled();
    expect(toPng).not.toHaveBeenCalled();
  });

  it("should return correctly formatted result with CellId and tuple", async () => {
    // Expected format: Record<CellId, ["image/png", string]>
    const cellId = "test-cell" as CellId;
    const mockElement = document.createElement("div");
    const mockDataUrl = "data:image/png;base64,testData";

    vi.spyOn(document, "getElementById").mockReturnValue(mockElement);
    vi.mocked(toPng).mockResolvedValue(mockDataUrl);

    setCellsRuntime(
      createMockCellRuntimes({
        [cellId]: {
          output: {
            channel: "output",
            mimetype: "text/html",
            data: "<div>Content</div>",
            timestamp: 0,
          },
        },
      }),
    );

    const { result } = renderHook(() => useEnrichCellOutputs(), { wrapper });

    const takeScreenshots = result.current;
    const output = await takeScreenshots({ progress });

    // Verify the exact return type structure
    expect(output).toHaveProperty(cellId);
    const cellOutput = output[cellId];
    expect(cellOutput).toBeDefined();
    expect(Array.isArray(cellOutput)).toBe(true);
    if (cellOutput) {
      expect(cellOutput[0]).toBe("image/png");
      expect(cellOutput[1]).toBe(mockDataUrl);
    }
  });
});

describe("updateCellOutputsWithScreenshots", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should call updateCellOutputs when there are screenshots", async () => {
    const cellId = "cell-1" as CellId;
    const mockScreenshots = {
      [cellId]: ["image/png", "data:image/png;base64,test"] as [
        "image/png",
        string,
      ],
    };

    const takeScreenshots = vi.fn().mockResolvedValue(mockScreenshots);
    const updateCellOutputs = vi.fn().mockResolvedValue(null);

    await updateCellOutputsWithScreenshots({
      takeScreenshots,
      updateCellOutputs,
    });

    expect(takeScreenshots).toHaveBeenCalledTimes(1);
    expect(updateCellOutputs).toHaveBeenCalledTimes(1);
    expect(updateCellOutputs).toHaveBeenCalledWith({
      cellIdsToOutput: mockScreenshots,
    });
  });

  it("should not call updateCellOutputs when there are no screenshots", async () => {
    const takeScreenshots = vi.fn().mockResolvedValue({});
    const updateCellOutputs = vi.fn().mockResolvedValue(null);

    await updateCellOutputsWithScreenshots({
      takeScreenshots,
      updateCellOutputs,
    });

    expect(takeScreenshots).toHaveBeenCalledTimes(1);
    expect(updateCellOutputs).not.toHaveBeenCalled();
  });

  it("should handle multiple cell screenshots", async () => {
    const cell1 = "cell-1" as CellId;
    const cell2 = "cell-2" as CellId;
    const mockScreenshots = {
      [cell1]: ["image/png", "data:image/png;base64,image1"] as [
        "image/png",
        string,
      ],
      [cell2]: ["image/png", "data:image/png;base64,image2"] as [
        "image/png",
        string,
      ],
    };

    const takeScreenshots = vi.fn().mockResolvedValue(mockScreenshots);
    const updateCellOutputs = vi.fn().mockResolvedValue(null);

    await updateCellOutputsWithScreenshots({
      takeScreenshots,
      updateCellOutputs,
    });

    expect(updateCellOutputs).toHaveBeenCalledWith({
      cellIdsToOutput: mockScreenshots,
    });
  });

  it("should catch errors from takeScreenshots and show toast", async () => {
    const error = new Error("Screenshot failed");
    const takeScreenshots = vi.fn().mockRejectedValue(error);
    const updateCellOutputs = vi.fn().mockResolvedValue(null);

    // Should not throw - errors are caught and shown via toast
    await updateCellOutputsWithScreenshots({
      takeScreenshots,
      updateCellOutputs,
    });

    expect(updateCellOutputs).not.toHaveBeenCalled();
    expect(Logger.error).toHaveBeenCalledWith(
      "Error updating cell outputs with screenshots:",
      error,
    );
    expect(toast).toHaveBeenCalledWith({
      title: "Failed to capture cell outputs",
      description:
        "Some outputs may not appear in the PDF. Continuing with export.",
      variant: "danger",
    });
  });

  it("should catch errors from updateCellOutputs and show toast", async () => {
    const cellId = "cell-1" as CellId;
    const mockScreenshots = {
      [cellId]: ["image/png", "data:image/png;base64,test"] as [
        "image/png",
        string,
      ],
    };
    const error = new Error("Update failed");

    const takeScreenshots = vi.fn().mockResolvedValue(mockScreenshots);
    const updateCellOutputs = vi.fn().mockRejectedValue(error);

    // Should not throw - errors are caught and shown via toast
    await updateCellOutputsWithScreenshots({
      takeScreenshots,
      updateCellOutputs,
    });

    expect(Logger.error).toHaveBeenCalledWith(
      "Error updating cell outputs with screenshots:",
      error,
    );
    expect(toast).toHaveBeenCalledWith({
      title: "Failed to capture cell outputs",
      description:
        "Some outputs may not appear in the PDF. Continuing with export.",
      variant: "danger",
    });
  });
});
