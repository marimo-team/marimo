/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { Objects } from "@/utils/objects";
import * as apiModule from "../api";
import { visibleForTesting } from "../requests-lazy";
import { createNetworkRequests } from "../requests-network";

const { ACTIONS } = visibleForTesting;

// Mock dependencies
vi.mock("../../runtime/config", () => ({
  getRuntimeManager: vi.fn(() => ({
    sessionHeaders: vi.fn(() => ({ "X-Test-Header": "test" })),
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

vi.mock("../../state/jotai", () => ({
  store: {
    get: vi.fn(() => true),
  },
}));

describe("createNetworkRequests", () => {
  let mockClient: any; // eslint-disable-line @typescript-eslint/no-explicit-any
  let capturedCalls: Map<string, { hasParams: boolean; endpoint: string }>;

  beforeEach(() => {
    vi.clearAllMocks();
    capturedCalls = new Map();

    // Create mock client that captures all calls
    const createMockMethod = (endpoint: string) => {
      // eslint-disable-line @typescript-eslint/no-explicit-any
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
      expect(
        ACTIONS[methodName as keyof typeof ACTIONS],
        `${methodName} should have an action defined in ACTIONS`,
      ).toBeDefined();
    }
  });

  it("verifies consistency between action types and params usage", async () => {
    const requests = createNetworkRequests();
    const methods = Objects.entries(requests);

    // Methods that should pass session params (session-based operations)
    const sessionBasedActions = new Set([
      "startConnection",
      "waitForConnectionOpen",
    ]);

    for (const [name, call] of methods) {
      capturedCalls.clear();
      try {
        // @ts-expect-error can be anything
        await call({});
      } catch {
        // Ignore errors from throwError actions or connection issues
      }

      const action = ACTIONS[name as keyof typeof ACTIONS];
      const captured = Array.from(capturedCalls.values())[0];

      // Format operations don't pass params
      if (name === "sendFormat") {
        expect(
          captured?.hasParams,
          `${name} (${action}) should not pass params`,
        ).toBe(false);
        continue;
      }

      // Session-based operations should pass params (except special cases)
      if (sessionBasedActions.has(action)) {
        if (captured) {
          expect(
            captured.hasParams,
            `${name} (${action}) should pass session params`,
          ).toBe(true);
        }
      }
    }
  });

  describe("special behavior", () => {
    it("sendRun should drop requests if not connected", async () => {
      const { store } = await import("../../state/jotai");

      vi.mocked(store.get).mockReturnValue(false);

      const requests = createNetworkRequests();
      const result = await requests.sendRun({} as any); // eslint-disable-line @typescript-eslint/no-explicit-any

      expect(result).toBe(null);
      expect(mockClient.POST).not.toHaveBeenCalled();
    });

    it("exportAsHTML should set assetUrl in dev/test mode", async () => {
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = "development";

      const requests = createNetworkRequests();
      await requests.exportAsHTML({} as any); // eslint-disable-line @typescript-eslint/no-explicit-any

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
