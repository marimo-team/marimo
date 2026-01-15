/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useInterval } from "../useInterval";

describe("useInterval", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should call callback after delay", () => {
    const callback = vi.fn();
    renderHook(() =>
      useInterval(callback, { delayMs: 1000, whenVisible: false }),
    );

    expect(callback).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("should not call callback when disabled", () => {
    const callback = vi.fn();
    renderHook(() =>
      useInterval(callback, {
        delayMs: 1000,
        whenVisible: false,
        disabled: true,
      }),
    );

    vi.advanceTimersByTime(1000);
    expect(callback).not.toHaveBeenCalled();
  });

  it("should respect visibility when whenVisible is true", () => {
    const callback = vi.fn();
    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      writable: true,
    });

    renderHook(() =>
      useInterval(callback, { delayMs: 1000, whenVisible: true }),
    );

    vi.advanceTimersByTime(1000);
    expect(callback).not.toHaveBeenCalled();

    Object.defineProperty(document, "visibilityState", { value: "visible" });
    vi.advanceTimersByTime(1000);
    expect(callback).toHaveBeenCalled();
  });

  it("should cleanup on unmount", () => {
    const callback = vi.fn();
    const { unmount } = renderHook(() =>
      useInterval(callback, { delayMs: 1000, whenVisible: false }),
    );

    unmount();
    vi.advanceTimersByTime(1000);
    expect(callback).not.toHaveBeenCalled();
  });

  describe("skipIfRunning", () => {
    it("should allow overlapping async calls by default", async () => {
      let concurrentCalls = 0;
      let maxConcurrentCalls = 0;

      const callback = vi.fn(async () => {
        concurrentCalls++;
        maxConcurrentCalls = Math.max(maxConcurrentCalls, concurrentCalls);
        // Simulate slow async work
        await new Promise((resolve) => setTimeout(resolve, 2000));
        concurrentCalls--;
      });

      renderHook(() =>
        useInterval(callback, { delayMs: 500, whenVisible: false }),
      );

      // First call at 500ms
      vi.advanceTimersByTime(500);
      expect(callback).toHaveBeenCalledTimes(1);

      // Second call at 1000ms (while first is still running)
      vi.advanceTimersByTime(500);
      expect(callback).toHaveBeenCalledTimes(2);

      // Third call at 1500ms
      vi.advanceTimersByTime(500);
      expect(callback).toHaveBeenCalledTimes(3);

      // Multiple concurrent calls should have occurred
      expect(maxConcurrentCalls).toBeGreaterThan(1);
    });

    it("should skip calls when skipIfRunning is true", async () => {
      let concurrentCalls = 0;
      let maxConcurrentCalls = 0;

      const callback = vi.fn(async () => {
        concurrentCalls++;
        maxConcurrentCalls = Math.max(maxConcurrentCalls, concurrentCalls);
        // Simulate slow async work (3 seconds)
        await new Promise<void>((resolve) => setTimeout(resolve, 3000));
        concurrentCalls--;
      });

      renderHook(() =>
        useInterval(callback, {
          delayMs: 500,
          whenVisible: false,
          skipIfRunning: true,
        }),
      );

      // First call at 500ms
      await vi.advanceTimersByTimeAsync(500);
      expect(callback).toHaveBeenCalledTimes(1);

      // Second interval tick at 1000ms - should be skipped since first is still running
      await vi.advanceTimersByTimeAsync(500);
      expect(callback).toHaveBeenCalledTimes(1); // Still 1, not 2

      // Third interval tick at 1500ms - should still be skipped
      await vi.advanceTimersByTimeAsync(500);
      expect(callback).toHaveBeenCalledTimes(1); // Still 1

      // Only one concurrent call should have occurred
      expect(maxConcurrentCalls).toBe(1);

      // Advance past the 3 second timeout to complete first callback
      await vi.advanceTimersByTimeAsync(2000);

      // Next interval tick should now be able to run
      await vi.advanceTimersByTimeAsync(500);
      expect(callback).toHaveBeenCalledTimes(2);
    });

    it("should allow next call after previous async call completes with skipIfRunning true", async () => {
      const callback = vi.fn(async () => {
        // Quick async operation
        await Promise.resolve();
      });

      renderHook(() =>
        useInterval(callback, {
          delayMs: 1000,
          whenVisible: false,
          skipIfRunning: true,
        }),
      );

      // First call
      await vi.advanceTimersByTimeAsync(1000);
      expect(callback).toHaveBeenCalledTimes(1);

      // Second call - should proceed since first completed
      await vi.advanceTimersByTimeAsync(1000);
      expect(callback).toHaveBeenCalledTimes(2);

      // Third call
      await vi.advanceTimersByTimeAsync(1000);
      expect(callback).toHaveBeenCalledTimes(3);
    });
  });
});
