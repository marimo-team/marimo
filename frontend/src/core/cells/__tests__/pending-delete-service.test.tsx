/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook, waitFor } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { createCellRuntimeState } from "@/core/cells/types";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";
import type { Milliseconds } from "@/utils/time";
import {
  usePendingDelete,
  usePendingDeleteService,
} from "../pending-delete-service";

const mockDeleteCell = vi.fn();
const mockDeleteManyCells = vi.fn();
vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => mockDeleteCell,
  useDeleteManyCellsCallback: () => mockDeleteManyCells,
}));

function createTestWrapper() {
  const store = createStore();
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return { wrapper, store };
}

// Don't clear all mocks - just reset the specific one we care about
beforeEach(() => {
  vi.resetAllMocks();
});

describe("pending-delete-service", () => {
  it("auto-deletes simple cells (no dependencies, short execution time)", async () => {
    const { wrapper, store } = createTestWrapper();

    const cellId = CellId.create();
    const notebook = MockNotebook.notebookState({
      cellData: {
        [cellId]: { code: "print('hello')" },
      },
    });

    notebook.cellRuntime[cellId] = createCellRuntimeState({
      runElapsedTimeMs: 1 as Milliseconds,
    });

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {});

    const { result } = renderHook(
      () => {
        const service = usePendingDeleteService();
        const deleteState = usePendingDelete(cellId);
        return { service, deleteState };
      },
      { wrapper },
    );

    act(() => {
      result.current.service.submit([cellId]);
    });

    // should flush single cell
    await waitFor(() => {
      expect(mockDeleteCell).toHaveBeenCalledWith({ cellId: cellId });
    });
  });

  it("requires confirmation for expensive cells (long execution time)", () => {
    const { wrapper, store } = createTestWrapper();

    const cellId = CellId.create();
    const notebook = MockNotebook.notebookState({
      cellData: {
        [cellId]: { code: "expensive_computation()" },
      },
    });

    notebook.cellRuntime[cellId] = createCellRuntimeState({
      runElapsedTimeMs: 100_000 as Milliseconds,
    });

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {});

    const { result: serviceResult } = renderHook(
      () => usePendingDeleteService(),
      { wrapper },
    );

    act(() => {
      serviceResult.current.submit([cellId]);
    });

    const { result } = renderHook(() => usePendingDelete(cellId), {
      wrapper,
    });

    expect(mockDeleteManyCells).not.toHaveBeenCalled();
    expect(result.current.isPending).toBe(true);
    act(() => {
      if (result.current.isPending && "confirm" in result.current) {
        result.current.confirm();
      }
    });

    expect(mockDeleteManyCells).toHaveBeenCalledWith({
      cellIds: [cellId],
    });
  });

  it("requires confirmation for cells with dependencies", () => {
    const { wrapper, store } = createTestWrapper();

    const cell1Id = CellId.create();
    const cell2Id = CellId.create();

    const notebook = MockNotebook.notebookState({
      cellData: {
        [cell1Id]: { code: "x = 1" },
        [cell2Id]: { code: "y = x + 1" },
      },
    });

    // Both have short execution times
    notebook.cellRuntime[cell1Id] = createCellRuntimeState({
      runElapsedTimeMs: 100 as Milliseconds,
    });
    notebook.cellRuntime[cell2Id] = createCellRuntimeState({
      runElapsedTimeMs: 50 as Milliseconds,
    });

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {
      ["x" as VariableName]: {
        name: "x" as VariableName,
        declaredBy: [cell1Id],
        usedBy: [cell2Id],
      },
    });

    // cell1 with dependencies
    const { result: serviceResult } = renderHook(
      () => usePendingDeleteService(),
      { wrapper },
    );

    act(() => {
      serviceResult.current.submit([cell1Id]);
    });

    // ensure doesn't auto-delete
    renderHook(() => usePendingDelete(cell1Id), { wrapper });
    expect(mockDeleteManyCells).not.toHaveBeenCalled();
  });

  it("prevents individual confirmation when multiple cells are pending", () => {
    const { wrapper, store } = createTestWrapper();

    const cell1Id = CellId.create();
    const cell2Id = CellId.create();
    const notebook = MockNotebook.notebookState({
      cellData: {
        [cell1Id]: { code: "expensive1()" },
        [cell2Id]: { code: "expensive2()" },
      },
    });

    notebook.cellRuntime[cell1Id] = createCellRuntimeState({
      runElapsedTimeMs: 3000 as Milliseconds,
    });
    notebook.cellRuntime[cell2Id] = createCellRuntimeState({
      runElapsedTimeMs: 4000 as Milliseconds,
    });

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {});

    const { result: serviceResult } = renderHook(
      () => usePendingDeleteService(),
      { wrapper },
    );
    act(() => {
      serviceResult.current.submit([cell1Id, cell2Id]);
    });

    const { result } = renderHook(() => usePendingDelete(cell1Id), {
      wrapper,
    });
    expect(result.current.isPending).toBe(true);
    if (result.current.isPending) {
      expect(result.current.shouldConfirmDelete).toBe(false);
      expect("confirm" in result.current).toBe(false);
    }
  });
});
