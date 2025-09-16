/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { getDefaultStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import { updateEditorCodeFromPython } from "../../codemirror/language/utils";
import {
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
    cellId1 = "cell-1" as CellId;
    cellId2 = "cell-2" as CellId;

    // Reset mocks
    vi.clearAllMocks();

    // Reset the atom state
    store.set(stagedAICellsAtom, new Set<CellId>());
  });

  describe("reducer and actions", () => {
    it("should initialize with empty map", () => {
      const state = initialState();
      expect(state).toEqual(new Set());
    });

    it("should add cell IDs", () => {
      let state = initialState();
      state = reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId1 },
      });
      state = reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId2 },
      });

      expect(state.has(cellId1)).toBe(true);
      expect(state.has(cellId2)).toBe(true);
    });

    it("should remove cell IDs", () => {
      const state = new Set([cellId1, cellId2]);
      const newState = reducer(state, {
        type: "removeStagedCell",
        payload: cellId1,
      });

      expect(newState.has(cellId1)).toBe(false);
      expect(newState.has(cellId2)).toBe(true);
    });

    it("should clear all cell IDs", () => {
      const state = new Set([cellId1, cellId2]);
      const newState = reducer(state, {
        type: "clearStagedCells",
        payload: undefined,
      });

      expect(newState).toEqual(new Set());
    });

    it("should not mutate original state", () => {
      const state = new Set([cellId1]);
      const originalSize = state.size;

      reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId2 },
      });

      expect(state.size).toBe(originalSize);
      expect(state.has(cellId1)).toBe(true);
      expect(state.has(cellId2)).toBe(false);
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
      expect(state).toEqual(new Set());
    });
  });

  describe("useStagedCells hook", () => {
    it("should create a staged cell with code", () => {
      const { result } = renderHook(() => useStagedCells(store));
      const testCode = "print('hello world')";

      // Mock CellId.create to return a predictable ID
      const mockCellId = "mock-cell-id" as CellId;
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
      const testCellId = "test-cell-id" as CellId;

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
      store.set(stagedAICellsAtom, new Set([cellId1, cellId2]));

      const { result } = renderHook(() => useStagedCells(store));
      result.current.deleteAllStagedCells();

      expect(mockDeleteCellCallback).toHaveBeenCalledTimes(2);
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId1 });
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId2 });

      // Verify cells were cleared from the atom
      const state = store.get(stagedAICellsAtom);
      expect(state).toEqual(new Set());
    });
  });

  it("should add staged cell", () => {
    const { result } = renderHook(() => useStagedCells(store));

    result.current.addStagedCell({ cellId: cellId1 });

    // Check that the cell was added to the atom
    const state = store.get(stagedAICellsAtom);
    expect(state.has(cellId1)).toBe(true);
  });

  it("should remove staged cell", () => {
    const { result } = renderHook(() => useStagedCells(store));

    // First add cells
    result.current.addStagedCell({ cellId: cellId1 });
    result.current.addStagedCell({ cellId: cellId2 });

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
    result.current.addStagedCell({ cellId: cellId1 });
    result.current.addStagedCell({ cellId: cellId2 });

    // Then clear all
    result.current.clearStagedCells();

    // Check that no cells remain
    const state = store.get(stagedAICellsAtom);
    expect(state).toEqual(new Set());
  });

  it("should handle multiple operations correctly", () => {
    const { result } = renderHook(() => useStagedCells(store));

    // Create a staged cell
    const mockCellId = "mock-cell-id" as CellId;
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    const createdCellId = result.current.createStagedCell("test code");

    // Verify it was created and added
    expect(createdCellId).toBe(mockCellId);
    expect(mockCreateNewCell).toHaveBeenCalled();

    let state = store.get(stagedAICellsAtom);
    expect(state.has(mockCellId)).toBe(true);

    // Delete the staged cell
    result.current.deleteStagedCell(mockCellId);
    expect(mockDeleteCellCallback).toHaveBeenCalledWith({
      cellId: mockCellId,
    });

    // Verify it was removed from staged cells
    state = store.get(stagedAICellsAtom);
    expect(state.has(mockCellId)).toBe(false);
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

  it("should create cells when text-delta is received and a stream has been created", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({ type: "text-start", id: "test-id" });

    // Mock CellId.create to return a predictable ID
    const mockCellId = "mock-cell-id" as CellId;
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "some code",
    });

    expect(mockCreateNewCell).toHaveBeenCalledWith({
      cellId: "__end__",
      code: "some code",
      before: false,
      newCellId: "mock-cell-id",
    });
  });

  it("should handle delta chunks", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.onStream({ type: "text-start", id: "test-id" });

    const mockCellId = "mock-cell-id" as CellId;
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "``",
    });

    expect(mockCreateNewCell).toHaveBeenCalledWith({
      cellId: "__end__",
      code: "``",
      before: false,
      newCellId: "mock-cell-id",
    });

    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "```python\nsome code",
    });

    // Now the cell is recognized and only some code is seen
    expect(vi.mocked(updateEditorCodeFromPython)).toHaveBeenCalledWith(
      mockCellHandle.current.editorViewOrNull,
      "some code",
    );

    result.current.onStream({
      type: "text-delta",
      id: "test-id",
      delta: "\n```",
    });
  });
});
