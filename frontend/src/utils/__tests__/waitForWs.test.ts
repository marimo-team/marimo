/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { waitForWs } from "../waitForWs";

describe("waitForWs", () => {
  let originalWebSocket: typeof WebSocket;
  let mockWs: any;

  beforeEach(() => {
    vi.useFakeTimers();
    originalWebSocket = global.WebSocket;
    mockWs = {
      close: vi.fn(),
      onopen: null,
      onerror: null,
    };
    global.WebSocket = vi.fn(() => mockWs) as any;
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("resolves immediately on successful connection", async () => {
    const url = "ws://test.com";
    const promise = waitForWs(url);

    // Simulate successful connection
    mockWs.onopen();

    await expect(promise).resolves.toBe(url);
    expect(mockWs.close).toHaveBeenCalled();
    expect(global.WebSocket).toHaveBeenCalledTimes(1);
    expect(global.WebSocket).toHaveBeenCalledWith(url);
  });

  it("retries on failure with linear backoff", async () => {
    const url = "ws://test.com";
    const promise = waitForWs(url, 3);

    // First attempt fails
    mockWs.onerror(new Event("error"));
    await vi.advanceTimersByTimeAsync(1000);

    // Second attempt fails
    mockWs.onerror(new Event("error"));
    await vi.advanceTimersByTimeAsync(2000);

    // Third attempt succeeds
    mockWs.onopen();

    await expect(promise).resolves.toBe(url);
    expect(global.WebSocket).toHaveBeenCalledTimes(3);
    expect(mockWs.close).toHaveBeenCalledTimes(3);
  });

  it("throws after max retries", async () => {
    const url = "ws://test.com";
    const promise = waitForWs(url, 2).catch((error) => error);

    // First attempt fails
    mockWs.onerror(new Event("error"));
    await vi.advanceTimersByTimeAsync(1000);

    // Second attempt fails
    mockWs.onerror(new Event("error"));
    await vi.advanceTimersByTimeAsync(2000);

    expect((await promise).message).toBe(`Failed to connect to ${url}`);
    expect(global.WebSocket).toHaveBeenCalledTimes(2);
    expect(mockWs.close).toHaveBeenCalledTimes(2);
  });
});
