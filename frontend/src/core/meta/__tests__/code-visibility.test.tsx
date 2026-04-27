/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { showCodeInRunModeAtom } from "@/core/meta/state";
import { type AppMode, kioskModeAtom, viewStateAtom } from "@/core/mode";
import { useNotebookCodeAvailable } from "../code-visibility";

interface StoreOpts {
  mode?: AppMode;
  kiosk?: boolean;
  showInRunMode?: boolean;
}

function makeStore({
  mode = "read",
  kiosk = false,
  showInRunMode = true,
}: StoreOpts = {}) {
  const store = createStore();
  store.set(viewStateAtom, { mode, cellAnchor: null });
  store.set(kioskModeAtom, kiosk);
  store.set(showCodeInRunModeAtom, showInRunMode);
  return store;
}

function wrap(store: ReturnType<typeof createStore>) {
  return ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
}

const cellsWithCode = [{ code: "x = 1" }, { code: "" }];
const cellsWithoutCode = [{ code: "" }, { code: "" }];

const originalLocation = window.location;

function setSearch(search: string) {
  // jsdom doesn't allow direct assignment to window.location, so swap the
  // whole object for the duration of a test.
  Object.defineProperty(window, "location", {
    value: { ...originalLocation, search },
    writable: true,
    configurable: true,
  });
}

describe("useNotebookCodeAvailable", () => {
  beforeEach(() => {
    setSearch("");
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  it("returns true in edit mode regardless of cells", () => {
    const store = makeStore({ mode: "edit" });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithoutCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(true);
  });

  it("returns true in present mode (only reachable from edit)", () => {
    const store = makeStore({ mode: "present" });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithoutCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(true);
  });

  it("returns true in kiosk mode even when read mode and no code", () => {
    const store = makeStore({
      mode: "read",
      kiosk: true,
      showInRunMode: false,
    });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithoutCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(true);
  });

  it("returns true in read mode when at least one cell has code", () => {
    const store = makeStore({ mode: "read" });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(true);
  });

  it("returns false in read mode when every cell.code is empty (server stripped)", () => {
    const store = makeStore({ mode: "read" });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithoutCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(false);
  });

  it("returns false in read mode when host opts out via showAppCode", () => {
    const store = makeStore({ mode: "read", showInRunMode: false });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(false);
  });

  it("returns false in read mode when ?include-code=false", () => {
    setSearch("?include-code=false");
    const store = makeStore({ mode: "read" });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(false);
  });

  it("ignores ?include-code=false in kiosk mode", () => {
    setSearch("?include-code=false");
    const store = makeStore({ mode: "read", kiosk: true });
    const { result } = renderHook(
      () => useNotebookCodeAvailable(cellsWithoutCode),
      { wrapper: wrap(store) },
    );
    expect(result.current).toBe(true);
  });

  it("returns false for non-edit/non-read modes (home, gallery)", () => {
    for (const mode of ["home", "gallery"] as const) {
      const store = makeStore({ mode });
      const { result } = renderHook(
        () => useNotebookCodeAvailable(cellsWithCode),
        { wrapper: wrap(store) },
      );
      expect(result.current).toBe(false);
    }
  });
});
