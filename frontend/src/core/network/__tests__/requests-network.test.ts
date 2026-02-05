/* Copyright 2026 Marimo. All rights reserved. */

/* eslint-disable @typescript-eslint/no-explicit-any */

import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiModule from "../api";
import { visibleForTesting } from "../requests-lazy";
import { createNetworkRequests } from "../requests-network";

const { ACTIONS } = visibleForTesting;

// Mock dependencies
vi.mock("../../runtime/config", () => ({
  getRuntimeManager: vi.fn(() => ({
    sessionHeaders: vi.fn(() => ({ "X-Test-Header": "test" })),
    isLazy: true,
  })),
}));

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof apiModule>("../api");
  return {
    ...actual,
    API: {
      handleResponse: vi.fn((response) => response.data),
      handleResponseReturnNull: vi.fn(() => null),
    },
    createClientWithRuntimeManager: vi.fn(),
  };
});

vi.mock("../connection", () => ({
  isConnectedAtom: { read: vi.fn(() => true) },
  waitForConnectionOpen: vi.fn().mockResolvedValue(undefined),
}));

describe("createNetworkRequests", () => {
  let mockClient: any;
  let capturedCalls: Map<string, { hasParams: boolean; endpoint: string }>;

  beforeEach(() => {
    vi.clearAllMocks();
    capturedCalls = new Map();

    // Create mock client that captures all calls
    const createMockMethod = (endpoint: string) => {
      return vi.fn((_route: string, options?: any) => {
        const hasParams = options?.params !== undefined;
        capturedCalls.set(endpoint, { hasParams, endpoint });
        return Promise.resolve({ data: null, error: undefined });
      });
    };

    mockClient = {
      POST: createMockMethod("POST"),
      GET: createMockMethod("GET"),
    };

    // Mock createClientWithRuntimeManager to return our mock client
    vi.mocked(apiModule.createClientWithRuntimeManager).mockReturnValue(
      mockClient,
    );
  });

  it("all request methods have an action defined", () => {
    const requests = createNetworkRequests();
    const methodNames = Object.keys(requests);

    for (const methodName of methodNames) {
      if (!ACTIONS[methodName as keyof typeof ACTIONS]) {
        expect.fail(`Method ${methodName} has no action defined`);
      }
    }
  });

  describe("special behavior", () => {
    it("exportAsHTML should set assetUrl in dev/test mode", async () => {
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = "development";

      const requests = createNetworkRequests();
      await requests.exportAsHTML({} as any);

      expect(mockClient.POST).toHaveBeenCalledWith(
        "/api/export/html",
        expect.objectContaining({
          body: expect.objectContaining({
            assetUrl: window.location.origin,
          }),
        }),
      );

      process.env.NODE_ENV = originalEnv;
    });
  });
});
