/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { createKeyedSelectorHook } from "../create-keyed-selector-hook";

function setup() {
  const source = atom(
    new Map([
      ["a", 1],
      ["b", 2],
    ]),
  );
  const store = createStore();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  const select = vi.fn((state: Map<string, number>, key: string) =>
    state.get(key),
  );
  const useEntry = createKeyedSelectorHook(source, select);
  return { source, store, wrapper, select, useEntry };
}

describe("createKeyedSelectorHook", () => {
  it("isolates renders while observing changes and removal of its own entry", () => {
    const { source, store, wrapper, useEntry } = setup();
    const renders = vi.fn();
    const { result } = renderHook(
      () => {
        renders();
        return useEntry("a");
      },
      { wrapper },
    );
    renders.mockClear();

    act(() =>
      store.set(
        source,
        new Map([
          ["a", 1],
          ["b", 3],
        ]),
      ),
    );
    expect(renders).not.toHaveBeenCalled();
    expect(result.current).toBe(1);

    act(() =>
      store.set(
        source,
        new Map([
          ["a", 4],
          ["b", 3],
        ]),
      ),
    );
    expect(result.current).toBe(4);
    expect(renders).toHaveBeenCalledTimes(1);

    act(() => store.set(source, new Map([["b", 3]])));
    expect(result.current).toBeUndefined();
    expect(renders).toHaveBeenCalledTimes(2);
  });

  it("keeps the selector stable on rerender and switches keys without stale reads", () => {
    const { source, store, wrapper, select, useEntry } = setup();
    const renders = vi.fn();
    const { result, rerender } = renderHook(
      ({ id }) => {
        renders();
        return useEntry(id);
      },
      { wrapper, initialProps: { id: "a" } },
    );
    select.mockClear();
    rerender({ id: "a" });
    expect(select).not.toHaveBeenCalled();

    rerender({ id: "b" });
    expect(result.current).toBe(2);
    select.mockClear();
    renders.mockClear();
    act(() =>
      store.set(
        source,
        new Map([
          ["a", 9],
          ["b", 2],
        ]),
      ),
    );
    expect(renders).not.toHaveBeenCalled();
    expect(select.mock.calls.map(([, key]) => key)).toEqual(["b"]);
  });

  it("releases the source subscription and stops selecting after unmount", () => {
    const { source, store, wrapper, select, useEntry } = setup();
    const dispose = vi.fn();
    source.onMount = () => dispose;
    const { unmount } = renderHook(() => useEntry("a"), { wrapper });
    select.mockClear();
    unmount();
    expect(dispose).toHaveBeenCalledTimes(1);
    act(() => store.set(source, new Map([["a", 3]])));
    expect(select).not.toHaveBeenCalled();
  });

  it("uses the current Provider store without sharing values between stores", () => {
    const { source, store, wrapper, useEntry } = setup();
    const otherStore = createStore();
    otherStore.set(source, new Map([["a", 7]]));
    const first = renderHook(() => useEntry("a"), { wrapper });
    const second = renderHook(() => useEntry("a"), {
      wrapper: ({ children }) => (
        <Provider store={otherStore}>{children}</Provider>
      ),
    });
    expect(first.result.current).toBe(1);
    expect(second.result.current).toBe(7);
    act(() => store.set(source, new Map([["a", 9]])));
    expect(first.result.current).toBe(9);
    expect(second.result.current).toBe(7);
  });
});
