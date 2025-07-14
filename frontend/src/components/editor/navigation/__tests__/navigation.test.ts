/* Copyright 2024 Marimo. All rights reserved. */
// @vitest-environment jsdom

import type { EditorView } from "@codemirror/view";
import { act, renderHook } from "@testing-library/react";
import { Provider } from "jotai";
import React, { createRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { MockNotebook } from "@/__mocks__/notebook";
import type { CellActions, NotebookState } from "@/core/cells/cells";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { createCell, createCellRuntimeState } from "@/core/cells/types";
import { store } from "@/core/state/jotai";
import { CollapsibleTree, MultiColumn } from "@/utils/id-tree";
import type { CellActionsDropdownHandle } from "../../cell/cell-actions";
import {
  useCellEditorNavigationProps,
  useCellNavigationProps,
} from "../navigation";

// Mock only the essential dependencies that we need to control
vi.mock("@/core/cells/cells", async (importOriginal) => ({
  ...(await importOriginal()),
  useCellActions: vi.fn(),
}));

vi.mock("@/core/cells/focus", () => ({
  useSetLastFocusedCellId: vi.fn(),
}));

vi.mock("@/core/saving/save-component", () => ({
  useSaveNotebook: vi.fn(),
}));

vi.mock("../../cell/useRunCells", () => ({
  useRunCells: vi.fn(),
}));

vi.mock("../clipboard", () => ({
  useCellClipboard: vi.fn(),
}));

vi.mock("../focus-utils", () => ({
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
const mockUseRunCells = vi.mocked(
  await import("../../cell/useRunCells"),
).useRunCells;
const mockUseCellClipboard = vi.mocked(
  await import("../clipboard"),
).useCellClipboard;

import { focusCell, focusCellEditor } from "../focus-utils";
import {
  type CellSelectionState,
  exportedForTesting as selectionTesting,
  useCellSelectionState,
  useIsCellSelected,
} from "../selection";

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
    mockUseRunCells.mockReturnValue(mockRunCell);
    mockUseCellClipboard.mockReturnValue({
      copyCells: mockCopyCell,
      pasteAtCell: mockPasteCell,
    });
  });

  const options = {
    canMoveX: false,
    editorView: createRef<EditorView>(),
    cellActionDropdownRef: createRef<CellActionsDropdownHandle>(),
  };

  describe("keyboard shortcuts", () => {
    it("should copy cell when 'c' key is pressed", () => {
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "c" });

      act(() => {
        // Simulate the keyboard event
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCopyCell).toHaveBeenCalledWith([mockCellId]);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should paste cell when 'v' key is pressed", () => {
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", shiftKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockRunCell).toHaveBeenCalled();
      expect(mockCellActions.moveToNextCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should save notebook when 's' key is pressed", () => {
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "s" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockSaveOrNameNotebook).toHaveBeenCalled();
    });

    it("should create cell before when 'a' key is pressed", () => {
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp", ctrlKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusTopCell).toHaveBeenCalled();
    });

    it("should move to bottom cell when Cmd+ArrowDown is pressed (or Ctrl)", () => {
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp", ctrlKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusTopCell).toHaveBeenCalled();
    });

    it("should move to bottom cell when Ctrl+ArrowDown is pressed", () => {
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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
      const { result } = renderHook(() =>
        useCellNavigationProps(mockCellId, options),
      );

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

describe("useCellNavigationProps - Bulk Selection", () => {
  const [cellId1, cellId2, cellId3] = MockNotebook.cellIds();
  const mockCellActions = MockNotebook.cellActions({
    focusCell: vi.fn(),
    moveCell: vi.fn(),
    sendToTop: vi.fn(),
    sendToBottom: vi.fn(),
    createNewCell: vi.fn(),
    moveToNextCell: vi.fn(),
    focusTopCell: vi.fn(),
    focusBottomCell: vi.fn(),
    updateCellConfig: vi.fn(),
    markTouched: vi.fn(),
  });

  const mockSetLastFocusedCellId = vi.fn();
  const mockSaveOrNameNotebook = vi.fn();
  const mockRunCell = vi.fn();
  const mockCopyCell = vi.fn();
  const mockPasteCell = vi.fn();

  const options = {
    canMoveX: false,
    editorView: createRef<EditorView>(),
    cellActionDropdownRef: createRef<CellActionsDropdownHandle>(),
  };

  // Helper to create notebook state with multiple cells
  const createNotebookState = (cellIds: CellId[]): NotebookState => ({
    ...initialNotebookState(),
    cellIds: new MultiColumn([CollapsibleTree.from(cellIds)]),
    cellData: Object.fromEntries(cellIds.map((id) => [id, createCell({ id })])),
    cellRuntime: Object.fromEntries(
      cellIds.map((id) => [
        id,
        createCellRuntimeState({
          output: null,
          status: "queued",
          outline: { items: [] },
        }),
      ]),
    ),
    cellHandles: Object.fromEntries(cellIds.map((id) => [id, createRef()])),
  });

  const renderWithProvider = <T>(hook: () => T) => {
    return renderHook(hook, {
      wrapper: ({ children }) =>
        React.createElement(Provider, { store }, children),
    });
  };

  const setupSelection = () => {
    const { reducer, cellSelectionAtom } = selectionTesting;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const dispatch = (action: any) => {
      store.set(cellSelectionAtom, (prev: CellSelectionState) =>
        reducer(prev, action),
      );
    };
    return selectionTesting.createActions(dispatch);
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Set up notebook state
    store.set(notebookAtom, createNotebookState([cellId1, cellId2, cellId3]));

    // Clear selection
    const selectionActions = setupSelection();
    selectionActions.clear();

    // Setup mocks
    mockUseCellActions.mockReturnValue(
      mockCellActions as unknown as CellActions,
    );
    mockUseSetLastFocusedCellId.mockReturnValue(mockSetLastFocusedCellId);
    mockUseSaveNotebook.mockReturnValue({
      saveOrNameNotebook: mockSaveOrNameNotebook,
      saveIfNotebookIsPersistent: vi.fn(),
    });
    mockUseRunCells.mockReturnValue(mockRunCell);
    mockUseCellClipboard.mockReturnValue({
      copyCells: mockCopyCell,
      pasteAtCell: mockPasteCell,
    });
  });

  describe("single cell operations", () => {
    it("should run single cell when no selection", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", ctrlKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockRunCell).toHaveBeenCalledWith([cellId1]);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should move single cell when no selection", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "9",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId1,
        before: true,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("bulk cell operations", () => {
    it("should run multiple cells when multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId2,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", ctrlKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockRunCell).toHaveBeenCalledWith([cellId1, cellId2]);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should copy multiple cells when multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId3,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId2, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "c" });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCopyCell).toHaveBeenCalledWith([cellId1, cellId2, cellId3]);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should move multiple cells up when multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId2 });
      selectionActions.extend({
        cellId: cellId3,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId2, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "9",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId2,
        before: true,
      });
      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId3,
        before: true,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should move multiple cells down when multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId2,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "0",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      // For move down, cells should be moved in reverse order
      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId2,
        before: false,
      });
      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId1,
        before: false,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should send multiple cells to top when multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId2 });
      selectionActions.extend({
        cellId: cellId3,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId2, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "1",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.sendToTop).toHaveBeenCalledWith({
        cellId: cellId2,
      });
      expect(mockCellActions.sendToTop).toHaveBeenCalledWith({
        cellId: cellId3,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should send multiple cells to bottom when multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId2,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "2",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.sendToBottom).toHaveBeenCalledWith({
        cellId: cellId1,
      });
      expect(mockCellActions.sendToBottom).toHaveBeenCalledWith({
        cellId: cellId2,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should run and move to next cell for multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId2,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", shiftKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockRunCell).toHaveBeenCalledWith([cellId1, cellId2]);
      // Should move to next cell after the last selected cell
      expect(mockCellActions.moveToNextCell).toHaveBeenCalledWith({
        cellId: cellId2,
        before: false,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should run and move to previous cell for multiple cells selected", () => {
      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId2 });
      selectionActions.extend({
        cellId: cellId3,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId2, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "Enter",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockRunCell).toHaveBeenCalledWith([cellId2, cellId3]);
      // Should move to previous cell before the first selected cell
      expect(mockCellActions.moveToNextCell).toHaveBeenCalledWith({
        cellId: cellId2,
        before: true,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("selection state management", () => {
    it("should indicate cell is selected when in selection", () => {
      // Set up selection
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });

      const { result } = renderWithProvider(() => useIsCellSelected(cellId1));

      expect(result.current).toBe(true);
    });

    it("should indicate cell is not selected when not in selection", () => {
      // Set up selection that doesn't include cellId2
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });

      const { result } = renderWithProvider(() => useIsCellSelected(cellId2));

      expect(result.current).toBe(false);
    });

    it("should clear selection when moving with Ctrl+Up", () => {
      // Set up selection
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId2,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp", ctrlKey: true });

      act(() => {
        if (result.current.onKeyDown) {
          result.current.onKeyDown(mockEvent);
        }
      });

      expect(mockCellActions.focusTopCell).toHaveBeenCalled();

      // Check that selection is cleared
      const { result: selectionResult } = renderWithProvider(() =>
        useCellSelectionState(),
      );
      expect(selectionResult.current.selected.size).toBe(0);
    });

    it("should clear selection when moving with Ctrl+Down", () => {
      // Set up selection
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId2,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

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

      // Check that selection is cleared
      const { result: selectionResult } = renderWithProvider(() =>
        useCellSelectionState(),
      );
      expect(selectionResult.current.selected.size).toBe(0);
    });
  });
});
