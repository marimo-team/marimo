/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useShouldShowInterrupt } from "../useShouldShowInterrupt";

describe("useShouldShowInterrupt", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("waits for each run and hides immediately when it stops", () => {
    const { result, rerender } = renderHook(useShouldShowInterrupt, {
      initialProps: false,
    });
    expect(result.current).toBe(false);
    rerender(true);
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe(true);
    rerender(false);
    expect(result.current).toBe(false);
    rerender(true);
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(199));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });

  it("cancels the delay for a short run", () => {
    const { result, rerender } = renderHook(useShouldShowInterrupt, {
      initialProps: true,
    });
    act(() => vi.advanceTimersByTime(100));
    rerender(false);
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe(false);
  });
});
