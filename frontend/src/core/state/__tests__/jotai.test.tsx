/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { atom, Provider } from "jotai";
import type React from "react";
import { describe, expect, it, vi } from "vitest";
import { store, useJotaiEffect, waitFor } from "../jotai";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <Provider store={store}>{children}</Provider>
);

describe("waitFor function", () => {
  it("should resolve when the atom satisfies the predicate", async () => {
    const testAtom = atom(0);
    store.set(testAtom, 10);

    const result = await waitFor(testAtom, (value) => value === 10);
    expect(result).toBe(10);
  });

  it("should resolve when the atom changes to satisfy the predicate", async () => {
    const testAtom = atom(0);

    setTimeout(() => store.set(testAtom, 15), 5);
    setTimeout(() => store.set(testAtom, 20), 10);

    const result = await waitFor(testAtom, (value) => value === 20);
    expect(result).toBe(20);
  });
});

describe("useJotaiEffect", () => {
  it("calls the effect with the new and previous values", () => {
    const testAtom = atom(0);
    const effect = vi.fn();
    renderHook(() => useJotaiEffect(testAtom, effect), { wrapper });

    act(() => store.set(testAtom, 1));
    act(() => store.set(testAtom, 2));

    expect(effect.mock.calls).toEqual([
      [1, 0],
      [2, 1],
    ]);
  });

  it("calls only the latest callback after a rerender", () => {
    const testAtom = atom(0);
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(
      ({ effect }) => useJotaiEffect(testAtom, effect),
      { initialProps: { effect: first }, wrapper },
    );

    rerender({ effect: second });
    act(() => store.set(testAtom, 1));

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("subscribes once per rerender with an inline callback", () => {
    const testAtom = atom(0);
    const calls: number[] = [];
    const { rerender } = renderHook(
      () => useJotaiEffect(testAtom, (value) => calls.push(value)),
      { wrapper },
    );

    rerender();
    rerender();
    act(() => store.set(testAtom, 1));

    expect(calls).toEqual([1]);
  });

  it("stops listening to the previous atom when the atom changes", () => {
    const firstAtom = atom(0);
    const secondAtom = atom(0);
    const effect = vi.fn();
    const { rerender } = renderHook(
      ({ target }) => useJotaiEffect(target, effect),
      { initialProps: { target: firstAtom }, wrapper },
    );

    rerender({ target: secondAtom });
    act(() => store.set(firstAtom, 1));
    expect(effect).not.toHaveBeenCalled();

    act(() => store.set(secondAtom, 1));
    expect(effect).toHaveBeenCalledTimes(1);
  });

  it("unsubscribes on unmount", () => {
    const testAtom = atom(0);
    const effect = vi.fn();
    const { unmount } = renderHook(() => useJotaiEffect(testAtom, effect), {
      wrapper,
    });

    unmount();
    act(() => store.set(testAtom, 1));

    expect(effect).not.toHaveBeenCalled();
  });
});
