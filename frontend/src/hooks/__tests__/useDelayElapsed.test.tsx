/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDelayElapsed } from "../useDelayElapsed";

describe("useDelayElapsed", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves true immediately when delay <= 0", () => {
    const { result } = renderHook(() => useDelayElapsed(0));
    expect(result.current).toBe(true);
  });

  it("stays false until the delay elapses, then flips true", () => {
    const { result } = renderHook(() => useDelayElapsed(2000));
    expect(result.current).toBe(false);

    act(() => vi.advanceTimersByTime(1999));
    expect(result.current).toBe(false);

    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });

  it("restarts the timer when the delay changes", () => {
    const { result, rerender } = renderHook(
      ({ delay }) => useDelayElapsed(delay),
      { initialProps: { delay: 1000 } },
    );

    act(() => vi.advanceTimersByTime(1000));
    expect(result.current).toBe(true);

    rerender({ delay: 500 });
    expect(result.current).toBe(false);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current).toBe(true);
  });

  it("clears the timer on unmount", () => {
    const { unmount } = renderHook(() => useDelayElapsed(1000));
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    // The pending timeout must be cleared, not left dangling.
    expect(vi.getTimerCount()).toBe(0);
  });
});
