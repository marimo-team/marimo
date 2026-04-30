/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { getDefaultStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { CellId } from "@/core/cells/ids";
import { updateEditorCodeFromPython } from "../../codemirror/language/utils";
import {
  type StagedAICells,
  stagedAICellsAtom,
  useStagedCells,
  visibleForTesting,
} from "../staged-cells";

const { createActions, reducer, initialState } = visibleForTesting;

// Mock the dependencies
const mockCreateNewCell = vi.fn();
const mockUpdateCellEditor = vi.fn();
const mockDeleteCellCallback = vi.fn();

// Mock cell handle with editor view
const mockCellHandle = {
  current: {
    editorViewOrNull: {
      dispatch: vi.fn(),
    },
  },
};

vi.mock("../../cells/cells", () => ({
  useCellActions: () => ({
    createNewCell: mockCreateNewCell,
    updateCellEditor: mockUpdateCellEditor,
  }),
  cellHandleAtom: vi.fn(() => ({
    read: vi.fn(() => mockCellHandle),
  })),
  getCellEditorView: vi.fn(() => mockCellHandle.current.editorViewOrNull),
}));

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => mockDeleteCellCallback,
}));

vi.mock("../../codemirror/language/utils", () => ({
  updateEditorCodeFromPython: vi.fn(),
}));

// Mock CellId.create
vi.mock("@/core/cells/ids", () => ({
  CellId: {
    create: vi.fn(),
  },
}));

describe("staged-cells", () => {
  let store: ReturnType<typeof getDefaultStore>;
  let cellId1: CellId;
  let cellId2: CellId;

  beforeEach(() => {
    store = getDefaultStore();
    cellId1 = cellId("cell-1");
    cellId2 = cellId("cell-2");

    // Reset mocks
    vi.clearAllMocks();

    // Reset the atom state
    store.set(stagedAICellsAtom, new Map());
  });

  describe("reducer and actions", () => {
    it("should initialize with empty map", () => {
      const state = initialState();
      expect(state).toEqual(new Map());
    });

    it("should add cells with update_cell edit", () => {
      let state = initialState();
      state = reducer(state, {
        type: "addStagedCell",
        payload: {
          cellId: cellId1,
          edit: { type: "update_cell", previousCode: "old code 1" },
        },
      });
      state = reducer(state, {
        type: "addStagedCell",
        payload: {
          cellId: cellId2,
          edit: { type: "update_cell", previousCode: "old code 2" },
        },
      });

      expect(state.has(cellId1)).toBe(true);
      expect(state.has(cellId2)).toBe(true);
      expect(state.get(cellId1)).toEqual({
        type: "update_cell",
        previousCode: "old code 1",
      });
      expect(state.get(cellId2)).toEqual({
        type: "update_cell",
        previousCode: "old code 2",
      });
    });

    it("should add cells with add_cell edit", () => {
      let state = initialState();
      state = reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId1, edit: { type: "add_cell" } },
      });

      expect(state.has(cellId1)).toBe(true);
      expect(state.get(cellId1)).toEqual({ type: "add_cell" });
    });

    it("should add cells with delete_cell edit", () => {
      let state = initialState();
      state = reducer(state, {
        type: "addStagedCell",
        payload: {
          cellId: cellId1,
          edit: { type: "delete_cell", previousCode: "deleted code" },
        },
      });

      expect(state.has(cellId1)).toBe(true);
      expect(state.get(cellId1)).toEqual({
        type: "delete_cell",
        previousCode: "deleted code",
      });
    });

    it("should remove cell IDs", () => {
      const state = new Map([
        [cellId1, { type: "add_cell" as const }],
        [cellId2, { type: "add_cell" as const }],
      ]);
      const newState = reducer(state, {
        type: "removeStagedCell",
        payload: cellId1,
      });

      expect(newState.has(cellId1)).toBe(false);
      expect(newState.has(cellId2)).toBe(true);
    });

    it("should clear all cells", () => {
      const state = new Map([
        [cellId1, { type: "add_cell" as const }],
        [cellId2, { type: "add_cell" as const }],
      ]);
      const newState = reducer(state, {
        type: "clearStagedCells",
        payload: undefined,
      });

      expect(newState).toEqual(new Map());
    });

    it("should not mutate original state when adding", () => {
      const state = new Map([[cellId1, { type: "add_cell" as const }]]);
      const originalSize = state.size;

      reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId2, edit: { type: "add_cell" } },
      });

      expect(state.size).toBe(originalSize);
      expect(state.has(cellId1)).toBe(true);
      expect(state.has(cellId2)).toBe(false);
    });

    it("should not mutate original state when removing", () => {
      const state = new Map([
        [cellId1, { type: "add_cell" as const }],
        [cellId2, { type: "add_cell" as const }],
      ]);
      const originalSize = state.size;

      reducer(state, {
        type: "removeStagedCell",
        payload: cellId1,
      });

      expect(state.size).toBe(originalSize);
      expect(state.has(cellId1)).toBe(true);
      expect(state.has(cellId2)).toBe(true);
    });

    it("should create action functions", () => {
      const mockDispatch = vi.fn();
      const actions = createActions(mockDispatch);

      expect(typeof actions.addStagedCell).toBe("function");
      expect(typeof actions.removeStagedCell).toBe("function");
      expect(typeof actions.clearStagedCells).toBe("function");
    });

    it("should initialize atom with empty map", () => {
      const state = store.get(stagedAICellsAtom);
      expect(state).toEqual(new Map());
    });
  });

  describe("useStagedCells hook", () => {
    it("should create a staged cell with code", () => {
      const { result } = renderHook(() => useStagedCells(store));
      const testCode = "print('hello world')";

      // Mock CellId.create to return a predictable ID
      const mockCellId = cellId("mock-cell-id");
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      const returnedCellId = result.current.createStagedCell(testCode);

      expect(returnedCellId).toBe(mockCellId);
      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: testCode,
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should delete a staged cell", () => {
      const { result } = renderHook(() => useStagedCells(store));
      const testCellId = cellId("test-cell-id");

      result.current.deleteStagedCell(testCellId);

      expect(mockDeleteCellCallback).toHaveBeenCalledWith({
        cellId: testCellId,
      });
    });

    it("should delete all staged cells when none exist", () => {
      const { result } = renderHook(() => useStagedCells(store));

      // Should not throw when no cells exist
      expect(() => result.current.deleteAllStagedCells()).not.toThrow();
      expect(mockDeleteCellCallback).not.toHaveBeenCalled();
    });

    it("should delete all staged cells when cells exist", () => {
      // First set the atom state before rendering the hook
      const initialState: StagedAICells = new Map([
        [cellId1, { type: "add_cell" }],
        [cellId2, { type: "add_cell" }],
      ]);
      store.set(stagedAICellsAtom, initialState);

      const { result } = renderHook(() => useStagedCells(store));
      result.current.deleteAllStagedCells();

      expect(mockDeleteCellCallback).toHaveBeenCalledTimes(2);
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId1 });
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId2 });

      // Verify cells were cleared from the atom
      const state = store.get(stagedAICellsAtom);
      expect(state).toEqual(new Map());
    });

    it("should add staged cell with edit info", () => {
      const { result } = renderHook(() => useStagedCells(store));

      result.current.addStagedCell({
        cellId: cellId1,
        edit: { type: "update_cell", previousCode: "old code" },
      });

      // Check that the cell was added to the atom with edit info
      const state = store.get(stagedAICellsAtom);
      expect(state.has(cellId1)).toBe(true);
      expect(state.get(cellId1)).toEqual({
        type: "update_cell",
        previousCode: "old code",
      });
    });

    it("should remove staged cell", () => {
      const { result } = renderHook(() => useStagedCells(store));

      // First add cells
      result.current.addStagedCell({
        cellId: cellId1,
        edit: { type: "add_cell" },
      });
      result.current.addStagedCell({
        cellId: cellId2,
        edit: { type: "add_cell" },
      });

      // Then remove one
      result.current.removeStagedCell(cellId1);

      // Check that only the remaining cell is in the map
      const state = store.get(stagedAICellsAtom);
      expect(state.has(cellId1)).toBe(false);
      expect(state.has(cellId2)).toBe(true);
    });

    it("should clear all staged cells", () => {
      const { result } = renderHook(() => useStagedCells(store));

      // First add some cells
      result.current.addStagedCell({
        cellId: cellId1,
        edit: { type: "add_cell" },
      });
      result.current.addStagedCell({
        cellId: cellId2,
        edit: { type: "add_cell" },
      });

      // Then clear all
      result.current.clearStagedCells();

      // Check that no cells remain
      const state = store.get(stagedAICellsAtom);
      expect(state).toEqual(new Map());
    });

    it("should handle multiple operations correctly", () => {
      const { result } = renderHook(() => useStagedCells(store));

      // Create a staged cell
      const mockCellId = cellId("mock-cell-id");
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      const createdCellId = result.current.createStagedCell("test code");

      // Verify it was created and added
      expect(createdCellId).toBe(mockCellId);
      expect(mockCreateNewCell).toHaveBeenCalled();

      let state = store.get(stagedAICellsAtom);
      expect(state.has(mockCellId)).toBe(true);
      expect(state.get(mockCellId)).toEqual({ type: cellId("add_cell") });

      // Delete the staged cell
      result.current.deleteStagedCell(mockCellId);
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({
        cellId: mockCellId,
      });

      // Verify it was removed from staged cells
      state = store.get(stagedAICellsAtom);
      expect(state.has(mockCellId)).toBe(false);
    });

    it("should track edit history for updated cells", () => {
      const { result } = renderHook(() => useStagedCells(store));

      // Add a cell with update_cell edit type
      result.current.addStagedCell({
        cellId: cellId1,
        edit: { type: "update_cell", previousCode: "previous code" },
      });

      const state = store.get(stagedAICellsAtom);
      const edit = state.get(cellId1);
      expect(edit).toEqual({
        type: "update_cell",
        previousCode: "previous code",
      });
    });

    it("should track edit history for deleted cells", () => {
      const { result } = renderHook(() => useStagedCells(store));

      // Add a cell with delete_cell edit type
      result.current.addStagedCell({
        cellId: cellId1,
        edit: { type: "delete_cell", previousCode: "deleted content" },
      });

      const state = store.get(stagedAICellsAtom);
      const edit = state.get(cellId1);
      expect(edit).toEqual({
        type: "delete_cell",
        previousCode: "deleted content",
      });
    });
  });
});

describe("onStream", () => {
  let store: ReturnType<typeof getDefaultStore>;
  beforeEach(() => {
    store = getDefaultStore();
  });

  it("should create a cell creation stream", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({ type: "text-start", id: "test-id" });

    // No cell or cell update should have been called
    expect(mockCreateNewCell).not.toHaveBeenCalled();
    expect(mockUpdateCellEditor).not.toHaveBeenCalled();
  });

  it("should not create cells when text-delta is received and no stream has been created", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "test-delta",
    });

    // No cell or cell update should have been called
    expect(mockCreateNewCell).not.toHaveBeenCalled();
    expect(mockUpdateCellEditor).not.toHaveBeenCalled();
  });

  it("should buffer text without fences and create cell on stop", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({ type: "text-start", id: "test-id" });

    // Mock CellId.create to return a predictable ID
    const mockCellId = cellId("mock-cell-id");
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "some code",
    });

    // Cell should NOT be created yet — waiting for a fence or stream end
    expect(mockCreateNewCell).not.toHaveBeenCalled();

    // When the stream ends, the buffered code is flushed as a cell
    result.current.onStream({ type: "text-end", id: "test-id" });

    expect(mockCreateNewCell).toHaveBeenCalledWith({
      cellId: "__end__",
      code: "some code",
      before: false,
      newCellId: "mock-cell-id",
    });
  });

  it("should not create cell from preamble when fence appears later", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({ type: "text-start", id: "test-id" });

    const mockCellId = cellId("mock-cell-id");
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    // Preamble text without fence — should be buffered
    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "I'll create a fibonacci function.\n\n",
    });

    expect(mockCreateNewCell).not.toHaveBeenCalled();

    // Now fence arrives — cell should be created with only the code
    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "```python\nsome code",
    });

    expect(mockCreateNewCell).toHaveBeenCalledWith({
      cellId: "__end__",
      code: "some code",
      before: false,
      newCellId: "mock-cell-id",
    });

    // More code arrives — cell should be updated
    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "\nmore code\n```",
    });

    expect(vi.mocked(updateEditorCodeFromPython)).toHaveBeenCalledWith(
      mockCellHandle.current.editorViewOrNull,
      "some code\nmore code",
    );
  });

  it("should handle delta chunks with fences", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({ type: "text-start", id: "test-id" });

    const mockCellId = cellId("mock-cell-id");
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "```python\nsome code",
    });

    expect(mockCreateNewCell).toHaveBeenCalledWith({
      cellId: "__end__",
      code: "some code",
      before: false,
      newCellId: "mock-cell-id",
    });

    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "\n```",
    });
  });

  it("should buffer partial fence and create cell when fence completes", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({ type: "text-start", id: "test-id" });

    const mockCellId = cellId("mock-cell-id");
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    // Chunk 1: partial fence (just two backticks)
    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "``",
    });

    // Cell should NOT be created — fence is incomplete
    expect(mockCreateNewCell).not.toHaveBeenCalled();

    // Chunk 2: fence completes + code
    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "`python\nsome code",
    });

    // NOW cell is created with actual code
    expect(mockCreateNewCell).toHaveBeenCalledWith({
      cellId: "__end__",
      code: "some code",
      before: false,
      newCellId: "mock-cell-id",
    });
  });
});
