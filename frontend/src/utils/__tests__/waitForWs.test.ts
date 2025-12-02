/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { waitForWs } from "../waitForWs";

describe("waitForWs", () => {
  let originalWebSocket: typeof WebSocket;
  let mockInstances: {
    close: ReturnType<typeof vi.fn>;
    onopen: (() => void) | null;
    onerror: ((event: Event) => void) | null;
  }[];

  beforeEach(() => {
    vi.useFakeTimers();
    originalWebSocket = global.WebSocket;
    mockInstances = [];

    // Create a mock WebSocket class that tracks all instances
    class MockWebSocket {
      close = vi.fn();
      onopen: (() => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(_url: string) {
        mockInstances.push(this);
      }
    }

    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("resolves immediately on successful connection", async () => {
    const url = "ws://test.com";
    const promise = waitForWs(url);

    // Allow the promise to start - need to flush microtasks
    await vi.advanceTimersByTimeAsync(0);

    // Simulate successful connection on the first instance
    expect(mockInstances).toHaveLength(1);
    mockInstances[0].onopen?.();

    await expect(promise).resolves.toBe(url);
    expect(mockInstances[0].close).toHaveBeenCalled();
  });

  it("retries on failure with linear backoff", async () => {
    const url = "ws://test.com";
    const promise = waitForWs(url, 3);

    // Allow the first WebSocket to be created
    await vi.advanceTimersByTimeAsync(0);

    // First attempt fails
    expect(mockInstances).toHaveLength(1);
    mockInstances[0].onerror?.(new Event("error"));
    await vi.advanceTimersByTimeAsync(1000);

    // Second attempt fails
    expect(mockInstances).toHaveLength(2);
    mockInstances[1].onerror?.(new Event("error"));
    await vi.advanceTimersByTimeAsync(2000);

    // Third attempt succeeds
    expect(mockInstances).toHaveLength(3);
    mockInstances[2].onopen?.();

    await expect(promise).resolves.toBe(url);
    expect(mockInstances).toHaveLength(3);
    expect(mockInstances[0].close).toHaveBeenCalledTimes(1);
    expect(mockInstances[1].close).toHaveBeenCalledTimes(1);
    expect(mockInstances[2].close).toHaveBeenCalledTimes(1);
  });

  it("throws after max retries", async () => {
    const url = "ws://test.com";
    const promise = waitForWs(url, 2).catch((error) => error);

    // Allow the first WebSocket to be created
    await vi.advanceTimersByTimeAsync(0);

    // First attempt fails
    expect(mockInstances).toHaveLength(1);
    mockInstances[0].onerror?.(new Event("error"));
    await vi.advanceTimersByTimeAsync(1000);

    // Second attempt fails
    expect(mockInstances).toHaveLength(2);
    mockInstances[1].onerror?.(new Event("error"));
    await vi.advanceTimersByTimeAsync(2000);

    expect((await promise).message).toBe(`Failed to connect to ${url}`);
    expect(mockInstances).toHaveLength(2);
    expect(mockInstances[0].close).toHaveBeenCalledTimes(1);
    expect(mockInstances[1].close).toHaveBeenCalledTimes(1);
  });
});
