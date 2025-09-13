/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { getDefaultStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import {
  type StagedCellData,
  stagedAICellsAtom,
  useStagedCells,
  visibleForTesting,
} from "../staged-cells";

const { createActions, reducer, initialState } = visibleForTesting;

// Mock the dependencies
const mockCreateNewCell = vi.fn();
const mockUpdateCellCode = vi.fn();
const mockDeleteCellCallback = vi.fn();

vi.mock("../../cells/cells", () => ({
  useCellActions: () => ({
    createNewCell: mockCreateNewCell,
    updateCellCode: mockUpdateCellCode,
  }),
}));

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => mockDeleteCellCallback,
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
    store.set(stagedAICellsAtom, {
      cellsMap: new Map<CellId, StagedCellData>(),
    });
  });

  describe("reducer and actions", () => {
    it("should initialize with empty map", () => {
      const state = initialState();
      expect(state.cellsMap).toEqual(new Map());
    });

    it("should add cell IDs", () => {
      let state = initialState();
      state = reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId1, code: "test1" },
      });
      state = reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId2, code: "test2" },
      });

      expect(state.cellsMap.has(cellId1)).toBe(true);
      expect(state.cellsMap.has(cellId2)).toBe(true);
      expect(state.cellsMap.get(cellId1)?.code).toBe("test1");
      expect(state.cellsMap.get(cellId2)?.code).toBe("test2");
    });

    it("should remove cell IDs", () => {
      const state = {
        cellsMap: new Map([
          [cellId1, { code: "test1" }],
          [cellId2, { code: "test2" }],
        ]),
      };
      const newState = reducer(state, {
        type: "removeStagedCell",
        payload: cellId1,
      });

      expect(newState.cellsMap.has(cellId1)).toBe(false);
      expect(newState.cellsMap.has(cellId2)).toBe(true);
    });

    it("should clear all cell IDs", () => {
      const state = {
        cellsMap: new Map([
          [cellId1, { code: "test1" }],
          [cellId2, { code: "test2" }],
        ]),
      };
      const newState = reducer(state, {
        type: "clearStagedCells",
        payload: undefined,
      });

      expect(newState.cellsMap).toEqual(new Map());
    });

    it("should not mutate original state", () => {
      const state = {
        cellsMap: new Map([[cellId1, { code: "test1" }]]),
      };
      const originalSize = state.cellsMap.size;

      reducer(state, {
        type: "addStagedCell",
        payload: { cellId: cellId2, code: "test2" },
      });

      expect(state.cellsMap.size).toBe(originalSize);
      expect(state.cellsMap.has(cellId1)).toBe(true);
      expect(state.cellsMap.has(cellId2)).toBe(false);
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
      expect(state.cellsMap).toEqual(new Map());
    });
  });

  describe("useStagedCells hook", () => {
    it("should create a staged cell with code", () => {
      const { result } = renderHook(() => useStagedCells());
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
      const { result } = renderHook(() => useStagedCells());
      const testCellId = "test-cell-id" as CellId;

      result.current.deleteStagedCell(testCellId);

      expect(mockDeleteCellCallback).toHaveBeenCalledWith({
        cellId: testCellId,
      });
    });

    it("should delete all staged cells when none exist", () => {
      const { result } = renderHook(() => useStagedCells());

      // Should not throw when no cells exist
      expect(() => result.current.deleteAllStagedCells()).not.toThrow();
      expect(mockDeleteCellCallback).not.toHaveBeenCalled();
    });

    it("should delete all staged cells when cells exist", () => {
      // First set the atom state before rendering the hook
      store.set(stagedAICellsAtom, {
        cellsMap: new Map([
          [cellId1, { code: "test1" }],
          [cellId2, { code: "test2" }],
        ]),
      });

      const { result } = renderHook(() => useStagedCells());

      // Verify cells are in the atom
      let state = store.get(stagedAICellsAtom);
      expect(state.cellsMap.has(cellId1)).toBe(true);
      expect(state.cellsMap.has(cellId2)).toBe(true);

      result.current.deleteAllStagedCells();

      expect(mockDeleteCellCallback).toHaveBeenCalledTimes(2);
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId1 });
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId2 });

      // Verify cells were cleared from the atom
      state = store.get(stagedAICellsAtom);
      expect(state.cellsMap).toEqual(new Map());
    });

    it("should add staged cell", () => {
      const { result } = renderHook(() => useStagedCells());

      result.current.addStagedCell({ cellId: cellId1, code: "test code" });

      // Check that the cell was added to the atom
      const state = store.get(stagedAICellsAtom);
      expect(state.cellsMap.has(cellId1)).toBe(true);
      expect(state.cellsMap.get(cellId1)?.code).toBe("test code");
    });

    it("should remove staged cell", () => {
      const { result } = renderHook(() => useStagedCells());

      // First add cells
      result.current.addStagedCell({ cellId: cellId1, code: "test1" });
      result.current.addStagedCell({ cellId: cellId2, code: "test2" });

      // Then remove one
      result.current.removeStagedCell(cellId1);

      // Check that only the remaining cell is in the map
      const state = store.get(stagedAICellsAtom);
      expect(state.cellsMap.has(cellId1)).toBe(false);
      expect(state.cellsMap.has(cellId2)).toBe(true);
    });

    it("should clear all staged cells", () => {
      const { result } = renderHook(() => useStagedCells());

      // First add some cells
      result.current.addStagedCell({ cellId: cellId1, code: "test1" });
      result.current.addStagedCell({ cellId: cellId2, code: "test2" });

      // Then clear all
      result.current.clearStagedCells();

      // Check that no cells remain
      const state = store.get(stagedAICellsAtom);
      expect(state.cellsMap).toEqual(new Map());
    });

    it("should handle multiple operations correctly", () => {
      const { result } = renderHook(() => useStagedCells());

      // Create a staged cell
      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      const createdCellId = result.current.createStagedCell("test code");

      // Verify it was created and added
      expect(createdCellId).toBe(mockCellId);
      expect(mockCreateNewCell).toHaveBeenCalled();

      let state = store.get(stagedAICellsAtom);
      expect(state.cellsMap.has(mockCellId)).toBe(true);

      // Delete the staged cell
      result.current.deleteStagedCell(mockCellId);
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({
        cellId: mockCellId,
      });

      // Verify it was removed from staged cells
      state = store.get(stagedAICellsAtom);
      expect(state.cellsMap.has(mockCellId)).toBe(false);
    });
  });
});
