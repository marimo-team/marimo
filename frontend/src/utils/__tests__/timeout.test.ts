/* Copyright 2024 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { retryWithTimeout } from "../timeout";

describe("retryWithTimeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("should be called immediately when function returns true on first call and no initial delay", async () => {
    const mockFn = vi.fn().mockReturnValue(true);
    retryWithTimeout(mockFn, { retries: 3, delay: 1000 });
    expect(mockFn).toHaveBeenCalledTimes(1);

    // Should not call again after success
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  it("should be called with initial delay", async () => {
    const mockFn = vi.fn().mockReturnValue(true);
    retryWithTimeout(mockFn, { retries: 3, delay: 1000, initialDelay: 1000 });

    // Function should not be called immediately
    expect(mockFn).toHaveBeenCalledTimes(0);

    // After first delay, function should be called and succeed
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(1);

    // Should not call again after success
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  it("should retry when function returns false initially", async () => {
    const mockFn = vi
      .fn()
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);

    retryWithTimeout(mockFn, {
      retries: 3,
      delay: 1000,
      initialDelay: 1000,
    });

    // Function should not be called immediately
    expect(mockFn).toHaveBeenCalledTimes(0);

    // After first delay
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(1);

    // After second delay
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(2);

    // After third delay - should succeed and stop
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(3);

    // Should not call again after success
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(3);
  });

  it("should stop retrying after max retries reached", async () => {
    const mockFn = vi.fn().mockReturnValue(false);

    retryWithTimeout(mockFn, {
      retries: 2,
      delay: 1000,
      initialDelay: 1000,
    });

    // Function should not be called immediately
    expect(mockFn).toHaveBeenCalledTimes(0);

    // After first delay
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(1);

    // After second delay
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(2);

    // Should not call again after max retries
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(2);
  });

  it("should handle zero retries", async () => {
    const mockFn = vi.fn().mockReturnValue(false);

    retryWithTimeout(mockFn, { retries: 0, delay: 1000 });

    // Function should not be called immediately
    expect(mockFn).toHaveBeenCalledTimes(0);

    // Should not call again
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(0);
  });

  it("should handle zero delay", async () => {
    const mockFn = vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true);

    retryWithTimeout(mockFn, { retries: 3, delay: 0 });

    // Called immediately
    expect(mockFn).toHaveBeenCalledTimes(1);

    // After zero delay - should call and succeed
    await vi.advanceTimersByTimeAsync(0);
    expect(mockFn).toHaveBeenCalledTimes(2);

    // Should not call again after success
    await vi.advanceTimersByTimeAsync(0);
    expect(mockFn).toHaveBeenCalledTimes(2);
  });

  it("should handle function that throws an error", async () => {
    const mockFn = vi
      .fn()
      .mockImplementationOnce(() => {
        throw new Error("Test error");
      })
      .mockReturnValueOnce(true);

    // Should not throw - the function handles errors gracefully
    expect(() => {
      retryWithTimeout(mockFn, { retries: 3, delay: 1000 });
    }).not.toThrow();

    // Function should be called but does not throw an error
    expect(mockFn).toHaveBeenCalledTimes(1);

    // After first delay - should call and succeed
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(2);

    // Should not call again after success
    await vi.advanceTimersByTimeAsync(1000);
    expect(mockFn).toHaveBeenCalledTimes(2);
  });
});
