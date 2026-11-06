/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { getDefaultStore, Provider } from "jotai";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { CellId } from "@/core/cells/ids";
import {
  stagedAICellsAtom,
  useStagedAICell,
  useStagedCells,
  visibleForTesting,
} from "../staged-cells";

const { createActions, reducer, initialState } = visibleForTesting;

// Mock the dependencies
const mockCreateCell = vi.fn();
const mockSetCellCode = vi.fn();
const mockDeleteCellCallback = vi.fn();

// Mock cell handle with editor view
const mockCellHandle = {
  current: {
    editorViewOrNull: {
      dispatch: vi.fn(),
    },
  },
};

vi.mock("../../cells/actions", () => ({
  useCellActions: () => ({
    createCell: mockCreateCell,
    setCellCode: mockSetCellCode,
  }),
}));
vi.mock("../../cells/cells", async () => {
  const { atom } = await import("jotai");
  return {
    notebookAtom: atom({ cellData: {}, cellIds: [] }),
    getCellEditorView: vi.fn(() => mockCellHandle.current.editorViewOrNull),
  };
});

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => mockDeleteCellCallback,
}));

vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => ({ sendRun: vi.fn() }),
}));

vi.mock("../../codemirror/language/cell-code", () => ({
  prepareCellCodeUpdate: vi.fn(() => ({ effects: [] })),
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
    vi.mocked(CellId.create).mockReset();

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

    it("should preserve state when removing a cell that is not staged", () => {
      const state = new Map([[cellId1, { type: "add_cell" as const }]]);
      const newState = reducer(state, {
        type: "removeStagedCell",
        payload: cellId2,
      });

      expect(newState).toBe(state);
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
    });

    it("should initialize atom with empty map", () => {
      const state = store.get(stagedAICellsAtom);
      expect(state).toEqual(new Map());
    });

    it("should not rerender a cell when another cell's staging changes", () => {
      let renderCount = 0;
      const wrapper = ({ children }: { children: ReactNode }) =>
        createElement(Provider, { store }, children);

      renderHook(
        () => {
          renderCount++;
          return useStagedAICell(cellId2);
        },
        { wrapper },
      );
      const initialRenderCount = renderCount;

      act(() => {
        store.set(
          stagedAICellsAtom,
          new Map([[cellId1, { type: "add_cell" }]]),
        );
      });
      expect(renderCount).toBe(initialRenderCount);

      act(() => {
        store.set(
          stagedAICellsAtom,
          new Map([[cellId2, { type: "add_cell" }]]),
        );
      });
      expect(renderCount).toBeGreaterThan(initialRenderCount);
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
      expect(mockCreateCell).toHaveBeenCalledWith({
        code: testCode,
        id: mockCellId,
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

    it("should handle multiple operations correctly", () => {
      const { result } = renderHook(() => useStagedCells(store));

      // Create a staged cell
      const mockCellId = cellId("mock-cell-id");
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      const createdCellId = result.current.createStagedCell("test code");

      // Verify it was created and added
      expect(createdCellId).toBe(mockCellId);
      expect(mockCreateCell).toHaveBeenCalled();

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
