/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { beforeAll, afterAll, expect, describe, it, vi } from "vitest";
import { createWsUrl } from "../client";

vi.mock("@/core/config/config", () => ({
  parseAppConfig: () => ({}),
  parseUserConfig: () => ({}),
}));

describe("createWsUrl", () => {
  let originalWindow: Window & typeof globalThis;

  beforeAll(() => {
    // Save the original window object
    originalWindow = global.window;
  });

  afterAll(() => {
    // Restore the original window object after tests
    global.window = originalWindow;
  });

  it("should create a WebSocket URL based on the window location", () => {
    // Mock the window object
    global.window = {
      location: {
        protocol: "http:",
        hostname: "localhost",
        port: "3000",
      },
    } as any;

    const expectedUrl = "ws://localhost:30000/copilot";
    expect(createWsUrl()).toBe(expectedUrl);
  });

  it("should use wss protocol when window location protocol is https", () => {
    // Mock the window object
    global.window = {
      location: {
        protocol: "https:",
        hostname: "localhost",
        port: "3000",
      },
    } as any;

    const expectedUrl = "wss://localhost:30000/copilot";
    expect(createWsUrl()).toBe(expectedUrl);
  });
});
