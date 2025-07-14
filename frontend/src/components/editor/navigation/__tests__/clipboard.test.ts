/* Copyright 2024 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { asMock, Mocks, SetupMocks } from "@/__mocks__/common";
import type { CellActions, NotebookState } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { useCellClipboard } from "../clipboard";

// Mock dependencies
vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

vi.mock("@/core/cells/cells", () => ({
  getNotebook: vi.fn(),
  useCellActions: vi.fn(),
}));

vi.mock("@/utils/Logger", () => ({
  Logger: Mocks.quietLogger(),
}));

import { MockNotebook } from "@/__mocks__/notebook";
import { toast } from "@/components/ui/use-toast";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import { Logger } from "@/utils/Logger";

describe("useCellClipboard", () => {
  const [mockCellId1, mockCellId2] = MockNotebook.cellIds();
  const mockCellCode1 = "print('hello world')";
  const mockCellCode2 = "x = 42";
  const mockCreateNewCell = vi.fn();

  const mockClipboard = Mocks.clipboard();

  beforeEach(() => {
    vi.clearAllMocks();

    SetupMocks.clipboard(mockClipboard);

    // Setup default clipboard mock implementations
    mockClipboard.write.mockResolvedValue(undefined);
    mockClipboard.writeText.mockResolvedValue(undefined);
    mockClipboard.read.mockResolvedValue([]);
    mockClipboard.readText.mockResolvedValue("");

    // Setup default mocks
    asMock(getNotebook).mockReturnValue({
      cellData: {
        [mockCellId1]: {
          code: mockCellCode1,
          name: "test-cell-1",
        },
        [mockCellId2]: {
          code: mockCellCode2,
          name: "test-cell-2",
        },
      },
    } as NotebookState);

    asMock(useCellActions).mockReturnValue({
      createNewCell: mockCreateNewCell,
    } as unknown as CellActions);
  });

  describe("copyCells", () => {
    it("should copy single cell to clipboard with custom mimetype and plain text", async () => {
      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([mockCellId1]);
      });

      expect(mockClipboard.write).toHaveBeenCalledWith([
        expect.objectContaining({
          types: ["application/x-marimo-cell", "text/plain"],
        }),
      ]);

      expect(toast).toHaveBeenCalledWith({
        title: "Cell copied",
        description: "Cell has been copied to clipboard",
      });
    });

    it("should copy multiple cells to clipboard with custom mimetype and plain text", async () => {
      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([mockCellId1, mockCellId2]);
      });

      expect(mockClipboard.write).toHaveBeenCalledWith([
        expect.objectContaining({
          types: ["application/x-marimo-cell", "text/plain"],
        }),
      ]);

      expect(toast).toHaveBeenCalledWith({
        title: "2 cells copied",
        description: "2 cells have been copied to clipboard",
      });
    });

    it("should show error toast when no cells found", async () => {
      asMock(getNotebook).mockReturnValue(MockNotebook.notebookState());

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([mockCellId1]);
      });

      expect(toast).toHaveBeenCalledWith({
        title: "Error",
        description: "No cells found",
        variant: "danger",
      });
    });

    it("should show error toast when empty cell list provided", async () => {
      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([]);
      });

      expect(toast).toHaveBeenCalledWith({
        title: "Error",
        description: "No cells found",
        variant: "danger",
      });
    });

    it("should fallback to writeText when clipboard.write fails for single cell", async () => {
      mockClipboard.write.mockRejectedValue(new Error("Write failed"));
      mockClipboard.writeText.mockResolvedValue(undefined);

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([mockCellId1]);
      });

      expect(mockClipboard.write).toHaveBeenCalled();
      expect(mockClipboard.writeText).toHaveBeenCalledWith(mockCellCode1);
      expect(toast).toHaveBeenCalledWith({
        title: "Cell copied",
        description: "Cell code has been copied to clipboard",
      });
    });

    it("should fallback to writeText when clipboard.write fails for multiple cells", async () => {
      mockClipboard.write.mockRejectedValue(new Error("Write failed"));
      mockClipboard.writeText.mockResolvedValue(undefined);

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([mockCellId1, mockCellId2]);
      });

      expect(mockClipboard.write).toHaveBeenCalled();
      expect(mockClipboard.writeText).toHaveBeenCalledWith(
        `${mockCellCode1}\n\n${mockCellCode2}`,
      );
      expect(toast).toHaveBeenCalledWith({
        title: "2 cells copied",
        description: "2 cells code have been copied to clipboard",
      });
    });

    it("should show error toast when both clipboard methods fail", async () => {
      mockClipboard.write.mockRejectedValue(new Error("Write failed"));
      mockClipboard.writeText.mockRejectedValue(new Error("WriteText failed"));

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([mockCellId1]);
      });

      expect(Logger.error).toHaveBeenCalledWith(
        "Failed to copy cells to clipboard",
        expect.any(Error),
      );
      expect(toast).toHaveBeenCalledWith({
        title: "Copy failed",
        description: "Failed to copy cells to clipboard",
        variant: "danger",
      });
    });

    it("should filter out non-existent cells", async () => {
      const nonExistentCellId = "non-existent" as CellId;

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.copyCells([mockCellId1, nonExistentCellId]);
      });

      expect(mockClipboard.write).toHaveBeenCalledWith([
        expect.objectContaining({
          types: ["application/x-marimo-cell", "text/plain"],
        }),
      ]);

      expect(toast).toHaveBeenCalledWith({
        title: "Cell copied",
        description: "Cell has been copied to clipboard",
      });
    });
  });

  describe("pasteCell", () => {
    it("should paste single cell from custom mimetype", async () => {
      const clipboardData = {
        cells: [{ code: "x = 42" }],
        version: "1.0",
      };

      const mockItem = {
        types: ["application/x-marimo-cell"],
        getType: vi.fn().mockResolvedValue(
          new Blob([JSON.stringify(clipboardData)], {
            type: "application/x-marimo-cell",
          }),
        ),
      };

      mockClipboard.read.mockResolvedValue([mockItem]);

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: mockCellId1,
        before: false,
        code: "x = 42",
        autoFocus: false,
      });
    });

    it("should paste multiple cells from custom mimetype", async () => {
      const clipboardData = {
        cells: [
          { code: "x = 42" },
          { code: "y = x * 2" },
          { code: "print(y)" },
        ],
        version: "1.0",
      };

      const mockItem = {
        types: ["application/x-marimo-cell"],
        getType: vi.fn().mockResolvedValue(
          new Blob([JSON.stringify(clipboardData)], {
            type: "application/x-marimo-cell",
          }),
        ),
      };

      mockClipboard.read.mockResolvedValue([mockItem]);

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(mockCreateNewCell).toHaveBeenCalledTimes(3);
      expect(mockCreateNewCell).toHaveBeenNthCalledWith(1, {
        cellId: mockCellId1,
        before: false,
        code: "x = 42",
        autoFocus: false,
      });
      expect(mockCreateNewCell).toHaveBeenNthCalledWith(2, {
        cellId: mockCellId1,
        before: false,
        code: "y = x * 2",
        autoFocus: false,
      });
      expect(mockCreateNewCell).toHaveBeenNthCalledWith(3, {
        cellId: mockCellId1,
        before: false,
        code: "print(y)",
        autoFocus: false,
      });
    });

    it("should fallback to plain text when custom mimetype fails", async () => {
      const mockItem = {
        types: ["text/plain"],
        getType: vi.fn().mockRejectedValue(new Error("Parse failed")),
      };

      mockClipboard.read.mockResolvedValue([mockItem]);
      mockClipboard.readText.mockResolvedValue("plain text code");

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: mockCellId1,
        before: false,
        code: "plain text code",
        autoFocus: true,
      });
    });

    it("should handle invalid clipboard data gracefully", async () => {
      const mockItem = {
        types: ["application/x-marimo-cell"],
        getType: vi.fn().mockResolvedValue(
          new Blob(["invalid json"], {
            type: "application/x-marimo-cell",
          }),
        ),
      };

      mockClipboard.read.mockResolvedValue([mockItem]);
      mockClipboard.readText.mockResolvedValue("fallback text");

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(Logger.warn).toHaveBeenCalledWith(
        "Failed to parse clipboard cell data",
        expect.any(Error),
      );
      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: mockCellId1,
        before: false,
        code: "fallback text",
        autoFocus: true,
      });
    });

    it("should show error toast when clipboard is empty", async () => {
      mockClipboard.read.mockResolvedValue([]);
      mockClipboard.readText.mockResolvedValue("");

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(toast).toHaveBeenCalledWith({
        title: "Nothing to paste",
        description: "No cell or text found in clipboard",
        variant: "danger",
      });
    });

    it("should show error toast when clipboard read fails", async () => {
      mockClipboard.read.mockRejectedValue(new Error("Read failed"));

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(Logger.error).toHaveBeenCalledWith(
        "Failed to paste from clipboard",
        expect.any(Error),
      );
      expect(toast).toHaveBeenCalledWith({
        title: "Paste failed",
        description: "Failed to read from clipboard",
        variant: "danger",
      });
    });

    it("should handle whitespace-only clipboard text", async () => {
      mockClipboard.read.mockResolvedValue([]);
      mockClipboard.readText.mockResolvedValue("   \n\t  ");

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(toast).toHaveBeenCalledWith({
        title: "Nothing to paste",
        description: "No cell or text found in clipboard",
        variant: "danger",
      });
    });

    it("should handle clipboard data with wrong version", async () => {
      const clipboardData = {
        cells: [{ code: "x = 42" }],
        version: "2.0", // Wrong version
      };

      const mockItem = {
        types: ["application/x-marimo-cell"],
        getType: vi.fn().mockResolvedValue(
          new Blob([JSON.stringify(clipboardData)], {
            type: "application/x-marimo-cell",
          }),
        ),
      };

      mockClipboard.read.mockResolvedValue([mockItem]);
      mockClipboard.readText.mockResolvedValue("fallback text");

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(Logger.warn).toHaveBeenCalledWith(
        "Failed to parse clipboard cell data",
        expect.any(Error),
      );
      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: mockCellId1,
        before: false,
        code: "fallback text",
        autoFocus: true,
      });
    });

    it("should handle empty cells array", async () => {
      const clipboardData = {
        cells: [],
        version: "1.0",
      };

      const mockItem = {
        types: ["application/x-marimo-cell"],
        getType: vi.fn().mockResolvedValue(
          new Blob([JSON.stringify(clipboardData)], {
            type: "application/x-marimo-cell",
          }),
        ),
      };

      mockClipboard.read.mockResolvedValue([mockItem]);
      mockClipboard.readText.mockResolvedValue("fallback text");

      const { result } = renderHook(() => useCellClipboard());

      await act(async () => {
        await result.current.pasteAtCell(mockCellId1);
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: mockCellId1,
        before: false,
        code: "fallback text",
        autoFocus: true,
      });
    });
  });
});
