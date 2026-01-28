/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it } from "vitest";
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

const mockClipboardData = {
  cells: [{ code: "x = 1", name: "cell1" }],
  version: "1.0" as const,
};

describe("pending-cut-service", () => {
  it("markForCut sets cellIds and clipboardData", () => {
    const { wrapper, store } = createTestWrapper();
    const cellIds: CellId[] = ["cell-1" as CellId, "cell-2" as CellId];

    const { result } = renderHook(
      () => ({
        actions: usePendingCutActions(),
        state: usePendingCutState(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.actions.markForCut({ cellIds, clipboardData: mockClipboardData });
    });

    const state = store.get(pendingCutStateAtom);
    expect(state.cellIds).toEqual(new Set(cellIds));
    expect(state.clipboardData).toEqual(mockClipboardData);
  });

  it("clear resets to initial state", () => {
    const { wrapper, store } = createTestWrapper();
    const cellIds: CellId[] = ["cell-1" as CellId];

    const { result } = renderHook(
      () => ({
        actions: usePendingCutActions(),
        state: usePendingCutState(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.actions.markForCut({
        cellIds,
        clipboardData: mockClipboardData,
      });
    });
    expect(store.get(pendingCutStateAtom).cellIds.size).toBe(1);

    act(() => {
      result.current.actions.clear();
    });
    const state = store.get(pendingCutStateAtom);
    expect(state.cellIds.size).toBe(0);
    expect(state.clipboardData).toBeNull();
  });

  it("useIsPendingCut returns true when cellId is marked for cut", () => {
    const { wrapper } = createTestWrapper();
    const cellId = "cell-1" as CellId;

    const { result: actionsResult } = renderHook(() => usePendingCutActions(), {
      wrapper,
    });
    const { result: isPendingResult } = renderHook(
      () => useIsPendingCut(cellId),
      { wrapper },
    );

    expect(isPendingResult.current).toBe(false);

    act(() => {
      actionsResult.current.markForCut({
        cellIds: [cellId],
        clipboardData: mockClipboardData,
      });
    });

    expect(isPendingResult.current).toBe(true);
  });

  it("useIsPendingCut returns false when cellId is not marked for cut", () => {
    const { wrapper } = createTestWrapper();
    const { result } = renderHook(
      () => useIsPendingCut("other-cell" as CellId),
      { wrapper },
    );

    const { result: actionsResult } = renderHook(() => usePendingCutActions(), {
      wrapper,
    });
    act(() => {
      actionsResult.current.markForCut({
        cellIds: ["cell-1" as CellId],
        clipboardData: mockClipboardData,
      });
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
      actionsResult.current.markForCut({
        cellIds: ["cell-1" as CellId],
        clipboardData: mockClipboardData,
      });
    });

    expect(hasPendingResult.current).toBe(true);
  });
});
