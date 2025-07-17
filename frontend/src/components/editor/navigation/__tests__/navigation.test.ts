/* Copyright 2024 Marimo. All rights reserved. */
// @vitest-environment jsdom

import type { EditorView } from "@codemirror/view";
import { act, renderHook } from "@testing-library/react";
import { Provider } from "jotai";
import React, { createRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { MockNotebook } from "@/__mocks__/notebook";
import { aiCompletionCellAtom } from "@/core/ai/state";
import type { CellActions } from "@/core/cells/cells";
import { notebookAtom } from "@/core/cells/cells";
import { configOverridesAtom, userConfigAtom } from "@/core/config/config";
import { store } from "@/core/state/jotai";
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

vi.mock("@/core/network/requests", () => ({
  saveCellConfig: vi.fn(),
}));

// Get mocked functions
const mockUseCellActions = vi.mocked(
  await import("@/core/cells/cells"),
).useCellActions;

const mockUseSaveNotebook = vi.mocked(
  await import("@/core/saving/save-component"),
).useSaveNotebook;
const mockUseRunCells = vi.mocked(
  await import("../../cell/useRunCells"),
).useRunCells;
const mockUseCellClipboard = vi.mocked(
  await import("../clipboard"),
).useCellClipboard;

import { defaultUserConfig } from "@/core/config/config-schema";
import { saveCellConfig } from "@/core/network/requests";
import { focusCell, focusCellEditor } from "../focus-utils";
import {
  type CellSelectionState,
  exportedForTesting as selectionTesting,
  useCellSelectionState,
  useIsCellSelected,
} from "../selection";

// Shared render helper
const renderWithProvider = <T>(hook: () => T) => {
  return renderHook(hook, {
    wrapper: ({ children }) =>
      React.createElement(Provider, { store }, children),
  });
};

// Shared mock setup
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
  moveCell: vi.fn(),
  sendToTop: vi.fn(),
  sendToBottom: vi.fn(),
  updateCellConfig: vi.fn(),
  markTouched: vi.fn(),
  deleteCell: vi.fn(),
  undoDeleteCell: vi.fn(),
});

const mockSaveCellConfig = vi.mocked(saveCellConfig);

// Helper to setup selection
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

const [cellId1, cellId2, cellId3] = MockNotebook.cellIds();
const mockCellId = cellId1;

describe("useCellNavigationProps", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Setup mocks
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

    // Setup default config in store
    store.set(userConfigAtom, {
      ...defaultUserConfig(),
      keymap: {
        preset: "default",
        overrides: {},
      },
    });

    // Setup notebook state with test cells - cellId1 first, cellId3 last for bulk selection tests
    const notebookState = MockNotebook.notebookState({
      cellData: {
        [cellId1]: {
          id: cellId1,
          config: { hide_code: false, disabled: false },
        },
        [cellId2]: {
          id: cellId2,
          config: { hide_code: false, disabled: false },
        },
        [cellId3]: {
          id: cellId3,
          config: { hide_code: true, disabled: false },
        },
      },
    });
    store.set(notebookAtom, notebookState);

    // Clear AI completion state
    store.set(aiCompletionCellAtom, null);

    // Clear selection
    const selectionActions = setupSelection();
    selectionActions.clear();
  });

  const options = {
    canMoveX: false,
    editorView: createRef<EditorView>(),
    cellActionDropdownRef: createRef<CellActionsDropdownHandle>(),
  };

  // Add a mock EditorView for tests that need it
  const mockEditorView = {
    focus: vi.fn(),
    contentDOM: { blur: vi.fn() },
  } as unknown as EditorView;

  const optionsWithMockEditor = {
    ...options,
    editorView: { current: mockEditorView } as React.RefObject<EditorView>,
  };

  describe("keyboard shortcuts", () => {
    it("should copy cell when 'c' key is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "c" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCopyCell).toHaveBeenCalledWith([mockCellId]);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should paste cell when 'v' key is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "v" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockPasteCell).toHaveBeenCalledWith(mockCellId);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should move to next cell when ArrowDown is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowDown" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
    });

    it("should move to previous cell when ArrowUp is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: true,
      });
    });

    it("should focus cell editor when Enter is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", shiftKey: false });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(focusCellEditor).toHaveBeenCalledWith(
        expect.anything(),
        mockCellId,
      );
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should run cell and move to next when Shift+Enter is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", shiftKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockRunCell).toHaveBeenCalled();
      expect(mockCellActions.moveToNextCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should save notebook when 's' key is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "s" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockSaveOrNameNotebook).toHaveBeenCalled();
    });

    it("should create cell before when 'a' key is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "a" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.createNewCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: true,
        autoFocus: true,
      });
    });

    it("should create cell after when 'b' key is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "b" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.createNewCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
        autoFocus: true,
      });
    });

    it("should move to top cell when Cmd+ArrowUp is pressed (or Ctrl)", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusTopCell).toHaveBeenCalled();
    });

    it("should move to bottom cell when Cmd+ArrowDown is pressed (or Ctrl)", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "ArrowDown",
        ctrlKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusBottomCell).toHaveBeenCalled();
    });

    it("should move to top cell when Ctrl+ArrowUp is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "ArrowUp", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusTopCell).toHaveBeenCalled();
    });

    it("should move to bottom cell when Ctrl+ArrowDown is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "ArrowDown",
        ctrlKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusBottomCell).toHaveBeenCalled();
    });

    it("should extend selection up when Shift+ArrowUp is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "ArrowUp",
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: true,
      });
    });

    it("should extend selection down when Shift+ArrowDown is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "ArrowDown",
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
    });

    it("should clear selection when Escape is pressed", () => {
      // Add selection
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: mockCellId });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Escape" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should set temporarily shown code when Enter is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(focusCellEditor).toHaveBeenCalledWith(
        expect.anything(),
        mockCellId,
      );
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("vim mode navigation", () => {
    beforeEach(() => {
      // Set up vim mode in store
      store.set(configOverridesAtom, {
        keymap: {
          preset: "vim",
        },
      });
    });

    it("should move down when 'j' key is pressed in vim mode", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "j" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
    });

    it("should move up when 'k' key is pressed in vim mode", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "k" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: true,
      });
    });

    it("should extend selection down when 'J' key is pressed in vim mode", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "J", shiftKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: false,
      });
    });

    it("should extend selection up when 'K' key is pressed in vim mode", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "K", shiftKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: mockCellId,
        before: true,
      });
    });

    it("should focus cell editor when 'i' key is pressed in vim mode", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "i" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(focusCellEditor).toHaveBeenCalledWith(
        expect.anything(),
        mockCellId,
      );
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("input event handling", () => {
    it("should ignore events from input elements", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "c",
        target: document.createElement("input"), // Input element
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCopyCell).not.toHaveBeenCalled();
      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });
  });

  describe("unknown keys", () => {
    it("should continue propagation for unknown keys", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "x",
        target: document.createElement("div"),
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });
  });

  describe("single cell operations", () => {
    it("should run single cell when no selection", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockRunCell).toHaveBeenCalledWith([cellId1]);
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should move single cell when no selection", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId2, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "9",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId2,
        before: true,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("doesn't move the cell if it's at the top of the notebook", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "9",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).not.toHaveBeenCalled();
      expect(mockEvent.preventDefault).not.toHaveBeenCalled();
    });

    it("doesn't move the cell if it's at the bottom of the notebook", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId3, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "0",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).not.toHaveBeenCalled();
      expect(mockEvent.preventDefault).not.toHaveBeenCalled();
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
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
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusBottomCell).toHaveBeenCalled();

      // Check that selection is cleared
      const { result: selectionResult } = renderWithProvider(() =>
        useCellSelectionState(),
      );
      expect(selectionResult.current.selected.size).toBe(0);
    });
  });

  describe("cell hide code functionality", () => {
    it("should toggle hide code when shortcut is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "h", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockSaveCellConfig).toHaveBeenCalledWith({
        configs: {
          [cellId1]: { hide_code: true },
        },
      });
      expect(mockCellActions.updateCellConfig).toHaveBeenCalledWith({
        cellId: cellId1,
        config: { hide_code: true },
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should toggle hide code to false when cell already has hide_code true", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId3, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "h", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockSaveCellConfig).toHaveBeenCalledWith({
        configs: {
          [cellId3]: { hide_code: false },
        },
      });
      expect(mockCellActions.updateCellConfig).toHaveBeenCalledWith({
        cellId: cellId3,
        config: { hide_code: false },
      });
    });

    it("should toggle hide code for multiple selected cells", () => {
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

      const mockEvent = Mocks.keyboardEvent({ key: "h", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockSaveCellConfig).toHaveBeenCalledWith({
        configs: {
          [cellId1]: { hide_code: true },
          [cellId2]: { hide_code: true },
        },
      });
      expect(mockCellActions.updateCellConfig).toHaveBeenCalledWith({
        cellId: cellId1,
        config: { hide_code: true },
      });
      expect(mockCellActions.updateCellConfig).toHaveBeenCalledWith({
        cellId: cellId2,
        config: { hide_code: true },
      });
    });
  });

  describe("AI completion functionality", () => {
    it("should toggle AI completion when shortcut is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, optionsWithMockEditor),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "e",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(store.get(aiCompletionCellAtom)).toEqual({ cellId: cellId1 });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should close AI completion when already open for same cell", () => {
      // Set AI completion to be open for cellId1
      store.set(aiCompletionCellAtom, { cellId: cellId1 });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, optionsWithMockEditor),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "e",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(store.get(aiCompletionCellAtom)).toBeNull();
      expect(mockEditorView.focus).toHaveBeenCalled();
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should switch AI completion to different cell when already open", () => {
      // Set AI completion to be open for cellId1
      store.set(aiCompletionCellAtom, { cellId: cellId1 });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId2, optionsWithMockEditor),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "e",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(store.get(aiCompletionCellAtom)).toEqual({ cellId: cellId2 });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("cell actions dropdown", () => {
    it("should toggle cell actions dropdown when shortcut is pressed", () => {
      const mockToggle = vi.fn();
      const optionsWithDropdown = {
        ...options,
        cellActionDropdownRef: {
          current: { toggle: mockToggle },
        } as React.RefObject<CellActionsDropdownHandle>,
      };

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, optionsWithDropdown),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "p", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockToggle).toHaveBeenCalled();
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should handle null cell actions dropdown ref", () => {
      const optionsWithNullDropdown = {
        ...options,
        cellActionDropdownRef: {
          current: null,
        } as unknown as React.RefObject<CellActionsDropdownHandle>,
      };

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, optionsWithNullDropdown),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "p", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("move left/right functionality", () => {
    it("should move cell left when shortcut is pressed and canMoveX is true", () => {
      const optionsWithMoveX = { ...options, canMoveX: true };

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, optionsWithMoveX),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "7",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId1,
        direction: "left",
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should move cell right when shortcut is pressed and canMoveX is true", () => {
      const optionsWithMoveX = { ...options, canMoveX: true };

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, optionsWithMoveX),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "8",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId1,
        direction: "right",
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should not move cell left when canMoveX is false", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "7",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).not.toHaveBeenCalled();
      expect(mockEvent.preventDefault).not.toHaveBeenCalled();
    });

    it("should not move cell right when canMoveX is false", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "8",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).not.toHaveBeenCalled();
      expect(mockEvent.preventDefault).not.toHaveBeenCalled();
    });

    it("should move multiple cells left when multiple cells selected", () => {
      const optionsWithMoveX = { ...options, canMoveX: true };

      // Set up selection of multiple cells
      const selectionActions = setupSelection();
      selectionActions.select({ cellId: cellId1 });
      selectionActions.extend({
        cellId: cellId2,
        allCellIds: store.get(notebookAtom).cellIds,
      });

      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, optionsWithMoveX),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "7",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId1,
        direction: "left",
      });
      expect(mockCellActions.moveCell).toHaveBeenCalledWith({
        cellId: cellId2,
        direction: "left",
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("focus up/down functionality", () => {
    it("should focus cell down when shortcut is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "j",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: cellId1,
        before: false,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it("should focus cell up when shortcut is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(cellId1, options),
      );

      const mockEvent = Mocks.keyboardEvent({
        key: "k",
        ctrlKey: true,
        shiftKey: true,
      });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.focusCell).toHaveBeenCalledWith({
        cellId: cellId1,
        before: true,
      });
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe("create cell shortcuts with modifier keys", () => {
    it("should not create cell before when 'a' key is pressed with modifier", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "a", ctrlKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.createNewCell).not.toHaveBeenCalled();
      expect(mockEvent.preventDefault).not.toHaveBeenCalled();
    });

    it("should not create cell after when 'b' key is pressed with modifier", () => {
      const { result } = renderWithProvider(() =>
        useCellNavigationProps(mockCellId, options),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "b", shiftKey: true });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(mockCellActions.createNewCell).not.toHaveBeenCalled();
      expect(mockEvent.preventDefault).not.toHaveBeenCalled();
    });
  });
});

describe("useCellEditorNavigationProps", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("keyboard shortcuts", () => {
    it("should focus cell when Escape is pressed", () => {
      const { result } = renderWithProvider(() =>
        useCellEditorNavigationProps(mockCellId),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Escape" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(focusCell).toHaveBeenCalledWith(mockCellId);
      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });

    it("should continue propagation for other keys", () => {
      const { result } = renderWithProvider(() =>
        useCellEditorNavigationProps(mockCellId),
      );

      const mockEvent = Mocks.keyboardEvent({ key: "Enter" });

      act(() => {
        result.current.onKeyDown?.(mockEvent);
      });

      expect(focusCell).not.toHaveBeenCalled();
      expect(mockEvent.continuePropagation).not.toHaveBeenCalled();
    });
  });
});
