/* Copyright 2024 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useInternalStateWithSync } from "../useInternalStateWithSync";

describe("useInternalStateWithSync", () => {
  it("should initialize with the given initial value", () => {
    const { result } = renderHook(() => useInternalStateWithSync("initial"));
    expect(result.current[0]).toBe("initial");
  });

  it("should update internal state when setState is called", () => {
    const { result } = renderHook(() => useInternalStateWithSync("initial"));

    act(() => {
      result.current[1]("updated");
    });

    expect(result.current[0]).toBe("updated");
  });

  it("should update internal state when initial value changes", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useInternalStateWithSync(value),
      { initialProps: { value: "initial" } },
    );

    expect(result.current[0]).toBe("initial");

    rerender({ value: "new value" });

    expect(result.current[0]).toBe("new value");
  });

  it("should not update internal state if initial value remains the same", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useInternalStateWithSync(value),
      { initialProps: { value: "initial" } },
    );

    act(() => {
      result.current[1]("internal update");
    });

    expect(result.current[0]).toBe("internal update");

    rerender({ value: "initial" });

    expect(result.current[0]).toBe("internal update");
  });

  it("should use custom equality function when provided", () => {
    const customEqualityFn = vi.fn(
      (a, b) => JSON.stringify(a) === JSON.stringify(b),
    );
    const initialValue = { key: "value" };

    const { result, rerender } = renderHook(
      ({ value }) => useInternalStateWithSync(value, customEqualityFn),
      { initialProps: { value: initialValue } },
    );

    expect(result.current[0]).toEqual(initialValue);

    // Rerender with a new object that has the same content
    rerender({ value: { key: "value" } });

    expect(customEqualityFn).toHaveBeenCalled();
    expect(result.current[0]).toEqual(initialValue);

    // Rerender with a new object that has different content
    rerender({ value: { key: "new value" } });

    expect(result.current[0]).toEqual({ key: "new value" });
  });
});
