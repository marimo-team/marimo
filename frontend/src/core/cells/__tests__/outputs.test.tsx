/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { type AppMode, viewStateAtom } from "@/core/mode";
import { useExpandedConsoleOutput, useExpandedOutput } from "../outputs";

const saveCellConfig = vi.fn().mockResolvedValue(null);

vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => ({ saveCellConfig }),
}));

function setup(opts: { mode: AppMode; expandOutput?: boolean }) {
  const cellId = CellId.create();
  const store = createStore();
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: {
        [cellId]: { config: { expand_output: opts.expandOutput ?? false } },
      },
    }),
  );
  store.set(viewStateAtom, { mode: opts.mode, cellAnchor: null });

  const { result } = renderHook(() => useExpandedOutput(cellId), {
    wrapper: ({ children }) => <Provider store={store}>{children}</Provider>,
  });

  return { cellId, store, result };
}

const configOf = (store: ReturnType<typeof createStore>, cellId: CellId) =>
  store.get(notebookAtom).cellData[cellId].config;

describe("useExpandedOutput", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads the initial state from the cell's expand_output config", () => {
    expect(setup({ mode: "edit" }).result.current[0]).toBe(false);
    expect(setup({ mode: "edit", expandOutput: true }).result.current[0]).toBe(
      true,
    );
  });

  it("persists the toggle to the cell's config in edit mode", () => {
    const { cellId, store, result } = setup({ mode: "edit" });

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
    expect(configOf(store, cellId).expand_output).toBe(true);
    expect(saveCellConfig).toHaveBeenCalledWith({
      configs: { [cellId]: { expand_output: true } },
    });
  });

  it("collapses by clearing the config", () => {
    const { cellId, store, result } = setup({
      mode: "edit",
      expandOutput: true,
    });

    act(() => result.current[1](false));

    expect(result.current[0]).toBe(false);
    expect(configOf(store, cellId).expand_output).toBe(false);
    expect(saveCellConfig).toHaveBeenCalledWith({
      configs: { [cellId]: { expand_output: false } },
    });
  });

  it("keeps the toggle in memory outside of edit mode", () => {
    const { cellId, store, result } = setup({ mode: "read" });

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
    // Cell configs are read-only outside of edit mode.
    expect(configOf(store, cellId).expand_output).toBe(false);
    expect(saveCellConfig).not.toHaveBeenCalled();
  });

  it("still honors expand_output outside of edit mode", () => {
    const { result } = setup({ mode: "read", expandOutput: true });
    expect(result.current[0]).toBe(true);
  });

  // `expand_output` covers the cell's output area only. Console output is
  // clamped independently and stays an in-memory, per-session toggle.
  it("does not touch the config when console output is expanded", () => {
    const cellId = CellId.create();
    const store = createStore();
    store.set(
      notebookAtom,
      MockNotebook.notebookState({ cellData: { [cellId]: {} } }),
    );
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });

    const { result } = renderHook(() => useExpandedConsoleOutput(cellId), {
      wrapper: ({ children }) => <Provider store={store}>{children}</Provider>,
    });

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
    expect(configOf(store, cellId).expand_output).toBe(false);
    expect(saveCellConfig).not.toHaveBeenCalled();
  });
});
