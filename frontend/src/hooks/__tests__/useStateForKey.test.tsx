/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useStateForKey } from "../useStateForKey";

describe("useStateForKey", () => {
  it("preserves edits for the same key and creates fresh state on key changes", () => {
    const initialize = vi.fn(() => new Set<string>());
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, initialize),
      { initialProps: { key: "first" } },
    );
    const initial = result.current[0];
    act(() => result.current[1](new Set(["expanded"])));
    rerender({ key: "first" });
    expect(result.current[0]).toEqual(new Set(["expanded"]));
    expect(initialize).toHaveBeenCalledOnce();

    rerender({ key: "second" });
    expect(result.current[0]).toEqual(new Set());
    expect(result.current[0]).not.toBe(initial);
    expect(initialize).toHaveBeenCalledTimes(2);

    rerender({ key: "first" });
    expect(result.current[0]).toEqual(new Set());
    expect(initialize).toHaveBeenCalledTimes(3);
  });

  it("preserves queued functional updates and ignores setters from another key", () => {
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, () => 0),
      { initialProps: { key: "first" } },
    );
    const oldSetter = result.current[1];
    act(() => {
      result.current[1]((value) => value + 1);
      result.current[1]((value) => value + 1);
    });
    expect(result.current[0]).toBe(2);

    rerender({ key: "second" });
    const staleUpdate = vi.fn(() => 99);
    act(() => oldSetter(staleUpdate));
    expect(result.current[0]).toBe(0);
    expect(staleUpdate).not.toHaveBeenCalled();
  });

  it("uses Object.is for NaN and signed zero keys", () => {
    const { result, rerender } = renderHook(
      ({ key }) => useStateForKey(key, () => "initial"),
      { initialProps: { key: Number.NaN } },
    );
    act(() => result.current[1]("draft"));
    rerender({ key: Number.NaN });
    expect(result.current[0]).toBe("draft");

    rerender({ key: 0 });
    expect(result.current[0]).toBe("initial");
    act(() => result.current[1]("draft"));
    rerender({ key: -0 });
    expect(result.current[0]).toBe("initial");
  });

  it("stores function values without invoking them", () => {
    const initial = vi.fn();
    const changed = vi.fn();
    const { result, rerender } = renderHook(
      ({ key, value }) => useStateForKey(key, () => value),
      { initialProps: { key: "first", value: initial } },
    );
    expect(result.current[0]).toBe(initial);
    act(() => result.current[1](() => changed));
    expect(result.current[0]).toBe(changed);
    rerender({ key: "second", value: initial });
    expect(result.current[0]).toBe(initial);
    expect(initial).not.toHaveBeenCalled();
    expect(changed).not.toHaveBeenCalled();
  });
});
