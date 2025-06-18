/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDelayVisibility } from "../useDelayVisibility";

describe("useDelayVisibility", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should start with invisible state", () => {
    const { result } = renderHook(() => useDelayVisibility(5, "read"));
    expect(result.current.invisible).toBe(true);
  });

  it("should become visible after delay in read mode", () => {
    const { result } = renderHook(() => useDelayVisibility(5, "read"));

    expect(result.current.invisible).toBe(true);

    // Advance timers by the calculated delay (5-1)*15 = 60ms
    act(() => {
      vi.advanceTimersByTime(60);
    });

    expect(result.current.invisible).toBe(false);
  });

  it("should cap delay at 100ms for large number of cells", () => {
    const { result } = renderHook(() => useDelayVisibility(20, "read"));

    expect(result.current.invisible).toBe(true);

    // Advance timers by 99ms (not enough)
    act(() => {
      vi.advanceTimersByTime(99);
    });
    expect(result.current.invisible).toBe(true);

    // Advance remaining 1ms to reach 100ms cap
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.invisible).toBe(false);
  });

  it("should not apply delay in edit mode", () => {
    const { result } = renderHook(() => useDelayVisibility(5, "edit"));

    // In edit mode, the delay should not be applied, so it should immediately be visible
    expect(result.current.invisible).toBe(true);

    // Even after advancing timers, it should remain invisible since no timeout was set
    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(result.current.invisible).toBe(true);
  });

  it("should not apply delay in present mode", () => {
    const { result } = renderHook(() => useDelayVisibility(5, "present"));

    // In present mode, the delay should not be applied
    expect(result.current.invisible).toBe(true);

    // Even after advancing timers, it should remain invisible since no timeout was set
    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(result.current.invisible).toBe(true);
  });
});
