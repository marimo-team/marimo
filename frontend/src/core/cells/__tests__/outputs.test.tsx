/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, describe, expect, it } from "vitest";
import { mockDocumentModel } from "@/__mocks__/document";
import { CellId } from "@/core/cells/ids";
import { DocumentProvider } from "@/core/notebook/document";
import {
  cell,
  CONFIG,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { type AppMode, viewStateAtom } from "@/core/mode";
import { useExpandedConsoleOutput, useExpandedOutput } from "../outputs";

const stops: Array<() => void> = [];

afterEach(() => {
  for (const stop of stops.splice(0)) {
    stop();
  }
});

function setup(opts: { mode: AppMode; expandOutput?: boolean }) {
  const cellId = CellId.create();
  const store = createStore();
  const { model, stop } = mockDocumentModel(
    store,
    withCells(
      documentOf(),
      {
        c1: null,
        c2: null,
        [cellId]: cell(cellId, "", {
          config: { ...CONFIG, expand_output: opts.expandOutput ?? false },
        }),
      },
      [cellId],
    ),
  );
  stops.push(stop);
  store.set(viewStateAtom, { mode: opts.mode, cellAnchor: null });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <DocumentProvider model={model}>{children}</DocumentProvider>
    </Provider>
  );
  const expanded = () =>
    store.get(model.documentAtom)?.cells.get(cellId)?.config.expand_output;

  return { cellId, store, wrapper, expanded };
}

describe("useExpandedOutput", () => {
  it("reads the initial state from the cell's expand_output config", () => {
    const collapsed = setup({ mode: "edit" });
    expect(
      renderHook(() => useExpandedOutput(collapsed.cellId), {
        wrapper: collapsed.wrapper,
      }).result.current[0],
    ).toBe(false);

    const expanded = setup({ mode: "edit", expandOutput: true });
    expect(
      renderHook(() => useExpandedOutput(expanded.cellId), {
        wrapper: expanded.wrapper,
      }).result.current[0],
    ).toBe(true);
  });

  it("persists the toggle to the cell's config in edit mode", () => {
    const { cellId, wrapper, expanded } = setup({ mode: "edit" });
    const { result } = renderHook(() => useExpandedOutput(cellId), {
      wrapper,
    });

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
    expect(expanded()).toBe(true);
  });

  it("collapses by clearing the config", () => {
    const { cellId, wrapper, expanded } = setup({
      mode: "edit",
      expandOutput: true,
    });
    const { result } = renderHook(() => useExpandedOutput(cellId), {
      wrapper,
    });

    act(() => result.current[1](false));

    expect(result.current[0]).toBe(false);
    expect(expanded()).toBe(false);
  });

  it("keeps the toggle in memory outside of edit mode", () => {
    const { cellId, wrapper, expanded } = setup({ mode: "read" });
    const { result } = renderHook(() => useExpandedOutput(cellId), {
      wrapper,
    });

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
    // Cell configs are read-only outside of edit mode.
    expect(expanded()).toBe(false);
  });

  it("still honors expand_output outside of edit mode", () => {
    const { cellId, wrapper } = setup({ mode: "read", expandOutput: true });
    const { result } = renderHook(() => useExpandedOutput(cellId), {
      wrapper,
    });
    expect(result.current[0]).toBe(true);
  });

  // `expand_output` covers the cell's output area only. Console output is
  // clamped independently and stays an in-memory, per-session toggle.
  it("does not touch the config when console output is expanded", () => {
    const { cellId, wrapper, expanded } = setup({ mode: "edit" });
    const { result } = renderHook(() => useExpandedConsoleOutput(cellId), {
      wrapper,
    });

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
    expect(expanded()).toBe(false);
  });
});
