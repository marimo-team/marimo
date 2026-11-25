/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook, waitFor } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { variableName } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { variablesAtom } from "@/core/variables/state";
import {
  usePendingDelete,
  usePendingDeleteService,
  visibleForTesting,
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
  it("preserves state identity when clearing an empty service", () => {
    const { reducer, initialState } = visibleForTesting;
    const state = initialState();
    expect(reducer(state, { type: "clear", payload: undefined })).toBe(state);
  });

  it.each([25, 250, 500])(
    "does not render %i subscribers on repeated empty clears",
    (count) => {
      const { wrapper } = createTestWrapper();
      const renders = vi.fn();
      const { result } = renderHook(() => usePendingDeleteService(), {
        wrapper,
      });
      const subscribers = Array.from({ length: count }, () => {
        const cellId = CellId.create();
        return renderHook(
          () => {
            usePendingDeleteService();
            usePendingDelete(cellId);
            renders();
          },
          { wrapper },
        );
      });
      renders.mockClear();

      for (let i = 0; i < 6; i++) {
        act(() => result.current.clear());
      }

      expect(renders).not.toHaveBeenCalled();
      for (const subscriber of subscribers) {
        subscriber.unmount();
      }
    },
  );

  it("isolates same-count changes and follows a changed cell id", () => {
    const { wrapper, store } = createTestWrapper();
    const first = CellId.create();
    const second = CellId.create();
    const unrelated = CellId.create();
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [first]: { code: "expensive1()" },
          [second]: { code: "expensive2()" },
        },
      }),
    );
    MockExecutions.seed(store, [
      MockExecutions.took(first, 3000),
      MockExecutions.took(second, 4000),
    ]);
    const serviceRenders = vi.fn();
    const { result: service } = renderHook(
      () => {
        serviceRenders();
        return usePendingDeleteService();
      },
      { wrapper },
    );
    const unrelatedRenders = vi.fn();
    renderHook(
      () => {
        unrelatedRenders();
        return usePendingDelete(unrelated);
      },
      { wrapper },
    );
    const { result, rerender } = renderHook(
      ({ cellId }) => usePendingDelete(cellId),
      {
        wrapper,
        initialProps: { cellId: first },
      },
    );
    act(() => service.current.submit([first]));
    expect(result.current.isPending).toBe(true);
    serviceRenders.mockClear();
    unrelatedRenders.mockClear();

    act(() => service.current.submit([second]));
    expect(result.current).toEqual({ isPending: false });
    expect(serviceRenders).not.toHaveBeenCalled();
    expect(unrelatedRenders).not.toHaveBeenCalled();

    rerender({ cellId: second });
    expect(result.current.isPending).toBe(true);
    act(() => {
      if (result.current.isPending && result.current.shouldConfirmDelete) {
        result.current.cancel();
      }
    });
    expect(result.current).toEqual({ isPending: false });
    expect(service.current.idle).toBe(true);
    expect(mockDeleteManyCells).not.toHaveBeenCalled();
  });

  it("auto-deletes simple cells (no dependencies, short execution time)", async () => {
    const { wrapper, store } = createTestWrapper();

    const cellId = CellId.create();
    const notebook = MockNotebook.notebookState({
      cellData: {
        [cellId]: { code: "print('hello')" },
      },
    });

    MockExecutions.seed(store, [MockExecutions.took(cellId, 1)]);

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

    MockExecutions.seed(store, [MockExecutions.took(cellId, 100_000)]);

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
    MockExecutions.seed(store, [
      MockExecutions.took(cell1Id, 100),
      MockExecutions.took(cell2Id, 50),
    ]);

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {
      [variableName("x")]: {
        name: variableName("x"),
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

    MockExecutions.seed(store, [
      MockExecutions.took(cell1Id, 3000),
      MockExecutions.took(cell2Id, 4000),
    ]);

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
    if (!result.current.isPending) {
      throw new Error("Expected cell deletion to be pending");
    }
    expect(result.current.shouldConfirmDelete).toBe(false);
    expect("confirm" in result.current).toBe(false);

    expect(serviceResult.current.shouldConfirmDelete).toBe(true);
    act(() => serviceResult.current.submit([cell1Id]));
    expect(serviceResult.current.shouldConfirmDelete).toBe(false);
    expect(result.current.shouldConfirmDelete).toBe(true);
    act(() => {
      if (result.current.isPending && result.current.shouldConfirmDelete) {
        result.current.confirm();
      }
    });
    expect(mockDeleteManyCells).toHaveBeenCalledExactlyOnceWith({
      cellIds: [cell1Id],
    });
    expect(result.current).toEqual({ isPending: false });
    expect(serviceResult.current.idle).toBe(true);
  });
});
