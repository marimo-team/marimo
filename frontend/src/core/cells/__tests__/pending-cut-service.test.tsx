/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import {
  pendingCutStateAtom,
  useHasPendingCut,
  useIsPendingCut,
  usePendingCutActions,
  usePendingCutState,
} from "../pending-cut-service";

function createTestWrapper() {
  const store = createStore();
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return { wrapper, store };
}

describe("pending-cut-service", () => {
  it("markForCut sets cellIds", () => {
    const { wrapper, store } = createTestWrapper();
    const cellIds: CellId[] = [cellId("cell-1"), cellId("cell-2")];

    const { result } = renderHook(
      () => ({
        actions: usePendingCutActions(),
        state: usePendingCutState(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.actions.markForCut({ cellIds });
    });

    const state = store.get(pendingCutStateAtom);
    expect(state.cellIds).toEqual(new Set(cellIds));
  });

  it("clear resets to initial state", () => {
    const { wrapper, store } = createTestWrapper();
    const cellIds: CellId[] = [cellId("cell-1")];

    const { result } = renderHook(
      () => ({
        actions: usePendingCutActions(),
        state: usePendingCutState(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.actions.markForCut({ cellIds });
    });
    expect(store.get(pendingCutStateAtom).cellIds.size).toBe(1);

    act(() => {
      result.current.actions.clear();
    });
    const state = store.get(pendingCutStateAtom);
    expect(state.cellIds.size).toBe(0);
  });

  it("useIsPendingCut returns true when cellId is marked for cut", () => {
    const { wrapper } = createTestWrapper();
    const targetCellId = cellId("cell-1");

    const { result: actionsResult } = renderHook(() => usePendingCutActions(), {
      wrapper,
    });
    const { result: isPendingResult } = renderHook(
      () => useIsPendingCut(targetCellId),
      { wrapper },
    );

    expect(isPendingResult.current).toBe(false);

    act(() => {
      actionsResult.current.markForCut({ cellIds: [targetCellId] });
    });

    expect(isPendingResult.current).toBe(true);
  });

  it("useIsPendingCut returns false when cellId is not marked for cut", () => {
    const { wrapper } = createTestWrapper();
    const { result } = renderHook(() => useIsPendingCut(cellId("other-cell")), {
      wrapper,
    });

    const { result: actionsResult } = renderHook(() => usePendingCutActions(), {
      wrapper,
    });
    act(() => {
      actionsResult.current.markForCut({ cellIds: [cellId("cell-1")] });
    });

    expect(result.current).toBe(false);
  });

  it("useHasPendingCut returns true when any cells are marked for cut", () => {
    const { wrapper } = createTestWrapper();
    const { result: hasPendingResult } = renderHook(() => useHasPendingCut(), {
      wrapper,
    });
    const { result: actionsResult } = renderHook(() => usePendingCutActions(), {
      wrapper,
    });

    expect(hasPendingResult.current).toBe(false);

    act(() => {
      actionsResult.current.markForCut({ cellIds: [cellId("cell-1")] });
    });

    expect(hasPendingResult.current).toBe(true);
  });
});
