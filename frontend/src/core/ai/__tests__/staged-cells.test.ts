/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { getDefaultStore, Provider } from "jotai";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import {
  type Edit,
  stagedAICellsAtom,
  useStagedAICell,
  useStagedCells,
  visibleForTesting,
} from "../staged-cells";

const { createActions, reducer, initialState } = visibleForTesting;

// Mock the dependencies
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
  getRequestClient: () => ({}),
}));

vi.mock("../../codemirror/language/cell-code", () => ({
  prepareCellCodeUpdate: vi.fn(() => ({ effects: [] })),
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

    it("drops a replaced cell while preserving the four remaining pending edits", () => {
      const original = cellId("original");
      const remaining = [cellId("a"), cellId("b"), cellId("c"), cellId("d")];
      const state = new Map<CellId, Edit>([
        [original, { type: "add_cell" }],
        [remaining[0], { type: "add_cell" }],
        [remaining[1], { type: "add_cell" }],
        [remaining[2], { type: "update_cell", previousCode: "x = 1" }],
        [remaining[3], { type: "delete_cell", previousCode: "y = 2" }],
      ]);
      const next = reducer(state, {
        type: "reconcileStagedCells",
        payload: remaining,
      });
      expect(next).toEqual(
        new Map([...state].filter(([id]) => id !== original)),
      );
      expect(
        reducer(next, { type: "reconcileStagedCells", payload: remaining }),
      ).toBe(next);
      expect(
        reducer(next, { type: "reconcileStagedCells", payload: [] }),
      ).toEqual(new Map());
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

  describe("useStagedCells", () => {
    const stage = (id: CellId, edit: Edit) =>
      store.set(stagedAICellsAtom, new Map([[id, edit]]));

    it("keeps added and updated cells by unstaging them", () => {
      const { result } = renderHook(() => useStagedCells());
      stage(cellId1, { type: "update_cell", previousCode: "x = 1" });
      result.current.acceptStagedCell(cellId1, {
        type: "update_cell",
        previousCode: "x = 1",
      });
      expect(store.get(stagedAICellsAtom).size).toBe(0);
      expect(mockDeleteCellCallback).not.toHaveBeenCalled();
    });

    it("deletes the cell when a proposed deletion is kept", () => {
      const { result } = renderHook(() => useStagedCells());
      const edit: Edit = { type: "delete_cell", previousCode: "x = 1" };
      stage(cellId1, edit);
      result.current.acceptStagedCell(cellId1, edit);
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId1 });
      expect(store.get(stagedAICellsAtom).size).toBe(0);
    });

    it("restores the previous code when an update is discarded", () => {
      const { result } = renderHook(() => useStagedCells());
      const edit: Edit = { type: "update_cell", previousCode: "x = 1" };
      stage(cellId1, edit);
      result.current.rejectStagedCell(cellId1, edit);
      expect(
        mockCellHandle.current.editorViewOrNull.dispatch,
      ).toHaveBeenCalled();
      expect(store.get(stagedAICellsAtom).size).toBe(0);
    });

    it("writes to the document when the editor is not mounted", async () => {
      const { getCellEditorView } = await import("../../cells/cells");
      vi.mocked(getCellEditorView).mockReturnValueOnce(undefined);
      const { result } = renderHook(() => useStagedCells());
      const edit: Edit = { type: "update_cell", previousCode: "x = 1" };
      stage(cellId1, edit);
      result.current.rejectStagedCell(cellId1, edit);
      expect(mockSetCellCode).toHaveBeenCalledWith({
        cellId: cellId1,
        code: "x = 1",
      });
    });

    it("deletes an added cell and leaves a proposed deletion in place when discarded", () => {
      const { result } = renderHook(() => useStagedCells());
      stage(cellId1, { type: "add_cell" });
      result.current.rejectStagedCell(cellId1, { type: "add_cell" });
      expect(mockDeleteCellCallback).toHaveBeenCalledWith({ cellId: cellId1 });

      mockDeleteCellCallback.mockClear();
      const deletion: Edit = { type: "delete_cell", previousCode: "x = 1" };
      stage(cellId2, deletion);
      result.current.rejectStagedCell(cellId2, deletion);
      expect(mockDeleteCellCallback).not.toHaveBeenCalled();
      expect(store.get(stagedAICellsAtom).size).toBe(0);
    });
  });
});
