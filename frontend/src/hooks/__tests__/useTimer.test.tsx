/* Copyright 2024 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTimer } from "../useTimer";

describe("useTimer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("should start at 0", () => {
    const { result } = renderHook(() => useTimer());
    expect(result.current.time).toBe("0.0");
  });

  it("should increment time when started", () => {
    const { result } = renderHook(() => useTimer());

    act(() => {
      result.current.start();
      vi.runOnlyPendingTimers();
    });

    expect(result.current.time).toBe("0.1");
  });

  it("should stop incrementing when stopped", () => {
    const { result } = renderHook(() => useTimer());

    act(() => {
      result.current.start();
      vi.runOnlyPendingTimers();
    });

    act(() => {
      result.current.stop();
      vi.runOnlyPendingTimers();
    });

    expect(result.current.time).toBe("0.1");
  });

  it("should reset to 0 when cleared", () => {
    const { result } = renderHook(() => useTimer());
    act(() => result.current.clear());
    expect(result.current.time).toBe("0.0");
  });

  it("should cleanup interval on unmount", () => {
    const { result, unmount } = renderHook(() => useTimer());
    act(() => result.current.start());
    unmount();
    vi.advanceTimersByTime(100);
    expect(result.current.time).toBe("0.0");
  });
});
