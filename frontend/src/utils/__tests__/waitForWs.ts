/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { beforeAll, afterAll, expect, describe, it, vi } from "vitest";
import { waitForWs } from "../waitForWs";

describe("waitForWs", () => {
  let originalWebSocket: any;

  beforeAll(() => {
    // Save the original WebSocket object
    originalWebSocket = global.WebSocket;
  });

  afterAll(() => {
    // Restore the original WebSocket object after tests
    global.WebSocket = originalWebSocket;
  });

  it("should resolve when the WebSocket connection is successful", async () => {
    // Mock the WebSocket object
    global.WebSocket = vi.fn().mockImplementation((url) => ({
      onopen: null,
      onerror: null,
      close: vi.fn(),
    })) as any;

    const url = "ws://localhost:3000";
    await expect(waitForWs(url)).resolves.toBe(url);

    // Verify that WebSocket was called with the correct URL
    expect(global.WebSocket).toHaveBeenCalledWith(url);
  });

  it("should reject when the WebSocket connection fails", async () => {
    // Mock the WebSocket object
    global.WebSocket = vi.fn().mockImplementation((url) => ({
      onopen: null,
      onerror: null,
      close: vi.fn(),
      // Simulate a connection error
      simulateError: function () {
        if (this.onerror) {
          this.onerror(new Error("Connection error"));
        }
      },
    })) as any;

    const url = "ws://localhost:3000";
    const ws = new global.WebSocket(url);
    (ws as any).simulateError();

    await expect(waitForWs(url)).rejects.toThrow(`Failed to connect to ${url}`);

    // Verify that WebSocket was called with the correct URL
    expect(global.WebSocket).toHaveBeenCalledWith(url);
  });
});
