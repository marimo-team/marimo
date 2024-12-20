/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce, useDebounceControlledState } from "../useDebounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("should update value after delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 1000),
      { initialProps: { value: "initial" } },
    );

    expect(result.current).toBe("initial");

    rerender({ value: "updated" });

    act(() => {
      vi.runAllTimers();
    });

    act(() => {
      vi.runAllTimers();
    });

    expect(result.current).toBe("updated");
  });

  it("should cleanup on unmount", () => {
    const { result, rerender, unmount } = renderHook(
      ({ value }) => useDebounce(value, 1000),
      { initialProps: { value: "initial" } },
    );

    expect(result.current).toBe("initial");

    rerender({ value: "updated" });
    unmount();

    act(() => {
      vi.runAllTimers();
    });

    expect(result.current).toBe("initial");
  });
});

describe("useDebounceControlledState", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("should call onChange with initial value immediately", () => {
    const onChange = vi.fn();
    renderHook(() =>
      useDebounceControlledState({
        initialValue: "initial",
        onChange,
        delay: 1000,
      }),
    );

    expect(onChange).toHaveBeenCalledWith("initial");
  });

  it("should debounce subsequent onChange calls", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() =>
      useDebounceControlledState({
        initialValue: "initial",
        onChange,
        delay: 1000,
      }),
    );

    onChange.mockClear();

    act(() => {
      result.current.onChange("updated");
    });

    act(() => {
      vi.runAllTimers();
    });

    act(() => {
      vi.runAllTimers();
    });

    expect(onChange).toHaveBeenCalledWith("updated");
  });

  it("should not call onChange if disabled", () => {
    const onChange = vi.fn();
    renderHook(() =>
      useDebounceControlledState({
        initialValue: "initial",
        onChange,
        delay: 1000,
        disabled: true,
      }),
    );

    expect(onChange).not.toHaveBeenCalled();
  });
});
