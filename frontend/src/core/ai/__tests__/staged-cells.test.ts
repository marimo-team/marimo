/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { getDefaultStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { CellId } from "@/core/cells/ids";
import { getCellEditorView } from "../../cells/cells";
import { updateEditorCodeFromPython } from "../../codemirror/language/utils";
import {
  type StagedAICells,
  stagedAICellsAtom,
  stagedGenerationInProgressAtom,
  useStagedCells,
  visibleForTesting,
} from "../staged-cells";

const { stagedGenerationAtom, createActions, reducer, initialState } =
  visibleForTesting;

// Mock the dependencies
const mockCreateNewCell = vi.fn();
const mockUpdateCellCode = vi.fn();
const mockDeleteCellCallback = vi.fn();

// Mock cell handle with editor view
const mockCellHandle = {
  current: {
    editorViewOrNull: {
      dispatch: vi.fn(),
    },
  },
};

vi.mock("../../cells/cells", async () => {
  const { atom } = await import("jotai");
  return {
    notebookAtom: atom({ cellData: {}, cellIds: { inOrderIds: [] } }),
    useCellActions: () => ({
      createNewCell: mockCreateNewCell,
      updateCellCode: mockUpdateCellCode,
    }),
    cellHandleAtom: vi.fn(() => ({
      read: vi.fn(() => mockCellHandle),
    })),
    getCellEditorView: vi.fn(() => mockCellHandle.current.editorViewOrNull),
  };
});

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => mockDeleteCellCallback,
}));

vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => ({ sendRun: vi.fn() }),
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
    vi.mocked(CellId.create).mockReset();

    // Reset the atom state
    store.set(stagedAICellsAtom, new Map());
    store.set(stagedGenerationAtom, null);
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

describe("staged cell generation", () => {
  let store: ReturnType<typeof getDefaultStore>;
  beforeEach(() => {
    store = getDefaultStore();
    vi.clearAllMocks();
    vi.mocked(CellId.create).mockReset();
    store.set(stagedAICellsAtom, new Map());
    store.set(stagedGenerationAtom, null);
  });

  it("should begin generation", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    // No cell or cell update should have been called
    expect(mockCreateNewCell).not.toHaveBeenCalled();
    expect(updateEditorCodeFromPython).not.toHaveBeenCalled();
    expect(store.get(stagedGenerationInProgressAtom)).toBe(true);
  });

  it("should mark generation complete after a successful finish", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();
    result.current.finishStagedCellGeneration(true);

    expect(store.get(stagedGenerationInProgressAtom)).toBe(false);
  });

  it("should only accept cells owned by the completed generation", () => {
    const firstGeneration = renderHook(() => useStagedCells(store));
    firstGeneration.result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create).mockReturnValueOnce(cellId("superseded-cell"));
    firstGeneration.result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "old" }],
      },
    });
    firstGeneration.result.current.finishStagedCellGeneration(true);

    const activeGeneration = renderHook(() => useStagedCells(store));
    activeGeneration.result.current.beginStagedCellGeneration();
    vi.mocked(CellId.create).mockReturnValueOnce(cellId("active-cell"));
    activeGeneration.result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "active" }],
      },
    });
    activeGeneration.result.current.finishStagedCellGeneration(true);

    expect(firstGeneration.result.current.hasOwnedStagedCells()).toBe(false);
    expect(firstGeneration.result.current.acceptOwnedStagedCells()).toBe(false);
    expect(store.get(stagedAICellsAtom)).toEqual(
      new Map([[cellId("active-cell"), { type: "add_cell" }]]),
    );

    expect(activeGeneration.result.current.hasOwnedStagedCells()).toBe(true);
    expect(activeGeneration.result.current.acceptOwnedStagedCells()).toBe(true);
    expect(store.get(stagedAICellsAtom)).toEqual(new Map());
  });

  it("should leave staged cells from another workflow untouched when accepting", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create).mockReturnValueOnce(cellId("generated-cell"));
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "generated" }],
      },
    });
    result.current.finishStagedCellGeneration(true);
    result.current.addStagedCell({
      cellId: cellId("chat-edited-cell"),
      edit: { type: "update_cell", previousCode: "before" },
    });

    expect(result.current.acceptOwnedStagedCells()).toBe(true);
    expect(store.get(stagedAICellsAtom)).toEqual(
      new Map([
        [
          cellId("chat-edited-cell"),
          { type: "update_cell", previousCode: "before" },
        ],
      ]),
    );
  });

  it("should only discard the generation's remaining staged cells", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create)
      .mockReturnValueOnce(cellId("accepted-cell"))
      .mockReturnValueOnce(cellId("pending-cell"));
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [
          { language: "python", code: "accepted" },
          { language: "python", code: "pending" },
        ],
      },
    });
    result.current.finishStagedCellGeneration(true);
    result.current.removeStagedCell(cellId("accepted-cell"));
    result.current.addStagedCell({
      cellId: cellId("chat-edited-cell"),
      edit: { type: "update_cell", previousCode: "before" },
    });

    expect(result.current.discardOwnedStagedCells()).toBe(true);
    expect(mockDeleteCellCallback).not.toHaveBeenCalledWith({
      cellId: cellId("accepted-cell"),
    });
    expect(mockDeleteCellCallback).toHaveBeenCalledWith({
      cellId: cellId("pending-cell"),
    });
    expect(mockDeleteCellCallback).not.toHaveBeenCalledWith({
      cellId: cellId("chat-edited-cell"),
    });
    expect(store.get(stagedAICellsAtom)).toEqual(
      new Map([
        [
          cellId("chat-edited-cell"),
          { type: "update_cell", previousCode: "before" },
        ],
      ]),
    );
  });

  it.each([
    { name: "no cells", cells: [] },
    {
      name: "an empty cell",
      cells: [{ language: "python" as const, code: "" }],
    },
  ])("should reject $name", ({ cells }) => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    expect(() =>
      result.current.onData({
        type: "data-notebook-cells-completion",
        data: { cells },
      }),
    ).toThrow();
  });

  it("should create cells from a validated completion", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    // Mock CellId.create to return a predictable ID
    const mockCellId = cellId("mock-cell-id");
    vi.mocked(CellId.create).mockReturnValue(mockCellId);

    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "print('```')" }],
      },
    });

    expect(mockCreateNewCell).toHaveBeenCalledWith({
      cellId: "__end__",
      code: "print('```')",
      before: false,
      newCellId: "mock-cell-id",
    });
  });

  it("should create multiple cells", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create)
      .mockReturnValueOnce(cellId("first-cell"))
      .mockReturnValueOnce(cellId("second-cell"));

    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [
          { language: "python", code: "value = 1" },
          { language: "python", code: "value" },
        ],
      },
    });

    expect(mockCreateNewCell).toHaveBeenCalledWith(
      expect.objectContaining({
        code: "value = 1",
        newCellId: "first-cell",
      }),
    );
    expect(mockCreateNewCell).toHaveBeenCalledWith(
      expect.objectContaining({
        code: "value",
        newCellId: "second-cell",
      }),
    );
  });

  it("should apply cumulative snapshots without recreating cells", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create)
      .mockReturnValueOnce(cellId("first-cell"))
      .mockReturnValueOnce(cellId("second-cell"));

    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "value" }],
      },
    });
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [
          { language: "python", code: "value = 1" },
          { language: "python", code: "value" },
        ],
      },
    });
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [
          { language: "python", code: "value = 1" },
          { language: "python", code: "value + 1" },
        ],
      },
    });

    expect(mockCreateNewCell).toHaveBeenCalledTimes(2);
    expect(store.get(stagedAICellsAtom).has(cellId("first-cell"))).toBe(true);
    expect(store.get(stagedAICellsAtom).has(cellId("second-cell"))).toBe(true);
    expect(updateEditorCodeFromPython).toHaveBeenCalledTimes(2);
  });

  it("should update notebook state when the cell editor is not mounted", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create).mockReturnValueOnce(cellId("unmounted-cell"));
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "value" }],
      },
    });

    vi.mocked(getCellEditorView).mockReturnValueOnce(null);
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "value = 1" }],
      },
    });

    expect(mockUpdateCellCode).toHaveBeenCalledWith({
      cellId: cellId("unmounted-cell"),
      code: "value = 1",
      formattingChange: false,
    });
  });

  it("should remove trailing cells when a retry produces a shorter snapshot", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create)
      .mockReturnValueOnce(cellId("first-cell"))
      .mockReturnValueOnce(cellId("second-cell"));

    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [
          { language: "python", code: "value = 1" },
          { language: "python", code: "value" },
        ],
      },
    });
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "replacement = 2" }],
      },
    });

    expect(mockDeleteCellCallback).toHaveBeenCalledWith({
      cellId: cellId("second-cell"),
    });
    expect(store.get(stagedAICellsAtom).has(cellId("first-cell"))).toBe(true);
    expect(store.get(stagedAICellsAtom).has(cellId("second-cell"))).toBe(false);
  });

  it("should remove a provisional marimo import when a retry no longer needs it", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create)
      .mockReturnValueOnce(cellId("generated-cell"))
      .mockReturnValueOnce(cellId("marimo-import"));

    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "sql", code: "result = mo.sql('SELECT 1')" }],
      },
    });
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "result = 1" }],
      },
    });

    expect(mockDeleteCellCallback).toHaveBeenCalledWith({
      cellId: cellId("marimo-import"),
    });
    expect(store.get(stagedAICellsAtom).has(cellId("marimo-import"))).toBe(
      false,
    );
  });

  it("should discard provisional cells when generation fails", () => {
    const { result } = renderHook(() => useStagedCells(store));
    result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create).mockReturnValue(cellId("partial-cell"));
    result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "partial" }],
      },
    });
    result.current.finishStagedCellGeneration(false);

    expect(mockDeleteCellCallback).toHaveBeenCalledWith({
      cellId: cellId("partial-cell"),
    });
    expect(store.get(stagedAICellsAtom)).toEqual(new Map());
    expect(store.get(stagedGenerationInProgressAtom)).toBe(false);
  });

  it("should not let a superseded generation mutate active cells", () => {
    const firstGeneration = renderHook(() => useStagedCells(store));
    firstGeneration.result.current.beginStagedCellGeneration();

    vi.mocked(CellId.create).mockReturnValueOnce(cellId("superseded-cell"));
    firstGeneration.result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "old" }],
      },
    });

    const activeGeneration = renderHook(() => useStagedCells(store));
    activeGeneration.result.current.beginStagedCellGeneration();
    mockDeleteCellCallback.mockClear();

    vi.mocked(CellId.create).mockReturnValueOnce(cellId("active-cell"));
    activeGeneration.result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "active" }],
      },
    });

    firstGeneration.result.current.finishStagedCellGeneration(false);
    firstGeneration.result.current.onData({
      type: "data-notebook-cells-completion",
      data: {
        cells: [{ language: "python", code: "stale" }],
      },
    });

    expect(mockDeleteCellCallback).not.toHaveBeenCalledWith({
      cellId: cellId("active-cell"),
    });
    expect(store.get(stagedAICellsAtom)).toEqual(
      new Map([[cellId("active-cell"), { type: "add_cell" }]]),
    );
    expect(store.get(stagedGenerationInProgressAtom)).toBe(true);
  });
});
