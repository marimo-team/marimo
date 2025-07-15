/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  useDebounce,
  useDebounceControlledState,
  useDebouncedCallback,
} from "../useDebounce";

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

describe("useDebouncedCallback", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("should debounce the callback", () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(callback, 1000));

    act(() => {
      result.current("test");
      result.current("test2");
      result.current("test3");
    });

    expect(callback).not.toHaveBeenCalled();

    act(() => {
      vi.runAllTimers();
    });

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith("test3");
  });

  it("should maintain the same reference when deps don't change", () => {
    const callback = vi.fn();
    const { result, rerender } = renderHook(() =>
      useDebouncedCallback(callback, 1000),
    );

    const firstRef = result.current;
    rerender();
    const secondRef = result.current;

    expect(firstRef).toBe(secondRef);
  });

  it("should create new debounced function when delay changes", () => {
    const callback = vi.fn();
    const { result, rerender } = renderHook(
      ({ delay }) => useDebouncedCallback(callback, delay),
      { initialProps: { delay: 1000 } },
    );

    const firstRef = result.current;
    rerender({ delay: 2000 });
    const secondRef = result.current;

    expect(firstRef).not.toBe(secondRef);
  });
});
