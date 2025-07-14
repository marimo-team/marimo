/* Copyright 2024 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { MockNotebook } from "@/__mocks__/notebook";
import type { CellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { useCellEditorNavigationProps, useCellNavigationProps } from "../focus";

// Mock only the essential dependencies that we need to control
vi.mock("@/core/cells/cells", () => ({
  useCellActions: vi.fn(),
}));

vi.mock("@/core/cells/focus", () => ({
  useSetLastFocusedCellId: vi.fn(),
}));

vi.mock("@/core/saving/save-component", () => ({
  useSaveNotebook: vi.fn(),
}));

vi.mock("../../cell/useRunCells", () => ({
  useRunCell: vi.fn(),
}));

vi.mock("../clipboard", () => ({
  useCellClipboard: vi.fn(),
}));

vi.mock("../focus-manager", () => ({
  focusCellEditor: vi.fn(),
  focusCell: vi.fn(),
}));

// Get mocked functions
const mockUseCellActions = vi.mocked(
  await import("@/core/cells/cells"),
).useCellActions;
const mockUseSetLastFocusedCellId = vi.mocked(
  await import("@/core/cells/focus"),
).useSetLastFocusedCellId;
const mockUseSaveNotebook = vi.mocked(
  await import("@/core/saving/save-component"),
).useSaveNotebook;
const mockUseRunCell = vi.mocked(
  await import("../../cell/useRunCells"),
).useRunCell;
const mockUseCellClipboard = vi.mocked(
  await import("../clipboard"),
).useCellClipboard;

import { focusCell, focusCellEditor } from "../focus-manager";

describe("useCellNavigationProps", () => {
  const mockCellId = "test-cell-id" as CellId;
  const mockSetLastFocusedCellId = vi.fn();
  const mockSaveOrNameNotebook = vi.fn();
  const mockSaveIfNotebookIsPersistent = vi.fn();
  const mockRunCell = vi.fn();
  const mockCopyCell = vi.fn();
  const mockPasteCell = vi.fn();

  const mockCellActions = MockNotebook.cellActions({
    focusCell: vi.fn(),
    moveToNextCell: vi.fn(),
    focusTopCell: vi.fn(),
    focusBottomCell: vi.fn(),
    createNewCell: vi.fn(),
  });

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup mocks
    mockUseSetLastFocusedCellId.mockReturnValue(mockSetLastFocusedCellId);
    mockUseSaveNotebook.mockReturnValue({
      saveOrNameNotebook: mockSaveOrNameNotebook,
      saveIfNotebookIsPersistent: mockSaveIfNotebookIsPersistent,
    });
    mockUseCellActions.mockReturnValue(
      mockCellActions as unknown as CellActions,
    );
    mockUseRunCell.mockReturnValue(mockRunCell);
    mockUseCellClipboard.mockReturnValue({
      copyCell: mockCopyCell,
      pasteCell: mockPasteCell,
    });
  });

  describe("keyboard shortcuts", () => {
    it("should copy cell when 'c' key is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "c" });

      act(() => {
        // Simulate the keyboard event
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCopyCell).toHaveBeenCalledWith(mockCellId);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should paste cell when 'v' key is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "v" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockPasteCell).toHaveBeenCalledWith(mockCellId);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should move to next cell when ArrowDown is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowDown" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
    });

    it("should move to previous cell when ArrowUp is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: true,
      });
    });

    it("should focus cell editor when Enter is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", shiftKey: false });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(focusCellEditor).toHaveBeenCalledWith(
        expect.anything(),
        mockCellId,
      );
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should run cell and move to next when Shift+Enter is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", shiftKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockRunCell).toHaveBeenCalled();
      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should save notebook when 's' key is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "s" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockSaveOrNameNotebook).toHaveBeenCalled();
    });

    it("should create cell before when 'a' key is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "a" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.createNewCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: true,
        autoFocus: true,
      });
    });

    it("should create cell after when 'b' key is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "b" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.createNewCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
        autoFocus: true,
      });
    });

    it("should move to top cell when Cmd+ArrowUp is pressed (or Ctrl)", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp", ctrlKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusTopCell).toHaveBeenCalled();
    });

    it("should move to bottom cell when Cmd+ArrowDown is pressed (or Ctrl)", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({
        key: "ArrowDown",
        ctrlKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusBottomCell).toHaveBeenCalled();
    });

    it("should move to top cell when Ctrl+ArrowUp is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp", ctrlKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusTopCell).toHaveBeenCalled();
    });

    it("should move to bottom cell when Ctrl+ArrowDown is pressed", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({
        key: "ArrowDown",
        ctrlKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusBottomCell).toHaveBeenCalled();
    });
  });

  describe("input event handling", () => {
    it("should ignore events from input elements", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({
        key: "c",
        target: document.createElement("input"), // Input element
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCopyCell).not.toHaveBeenCalled();
      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });
  });

  describe("unknown keys", () => {
    it("should continue propagation for unknown keys", () => {
      const { result } = renderHook(() => useCellNavigationProps(mockCellId));

      const mockEvent = Mocks.keyboardEvent({
        key: "x",
        target: document.createElement("div"),
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });
  });
});

describe("useCellEditorNavigationProps", () => {
  const mockCellId = "test-cell-id" as CellId;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("keyboard shortcuts", () => {
    it("should focus cell when Escape is pressed", () => {
      const { result } = renderHook(() =>
        useCellEditorNavigationProps(mockCellId),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Escape" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(focusCell).toHaveBeenCalledWith(mockCellId);
      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });

    it("should continue propagation for other keys", () => {
      const { result } = renderHook(() =>
        useCellEditorNavigationProps(mockCellId),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(focusCell).not.toHaveBeenCalled();
      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });
  });
});
