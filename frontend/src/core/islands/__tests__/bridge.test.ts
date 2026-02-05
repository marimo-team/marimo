/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock browser APIs before any imports
vi.stubGlobal(
  "Worker",
  vi.fn(() => ({
    addEventListener: vi.fn(),
    postMessage: vi.fn(),
    terminate: vi.fn(),
  })),
);

// Create a mock URL class that works as a constructor
class MockURL {
  href: string;
  constructor(url: string, base?: string | URL) {
    this.href = base ? `${base}/${url}` : url;
  }
  static createObjectURL = vi.fn(() => "blob:mock-url");
  static revokeObjectURL = vi.fn();
}
vi.stubGlobal("URL", MockURL);

// Mock the worker RPC before importing the bridge
const mockBridge = vi.fn();
const mockLoadPackages = vi.fn();

vi.mock("@/core/wasm/rpc", () => ({
  getWorkerRPC: () => ({
    proxy: {
      request: {
        bridge: mockBridge,
        loadPackages: mockLoadPackages,
        startSession: vi.fn(),
      },
      send: {
        consumerReady: vi.fn(),
      },
    },
    addMessageListener: vi.fn(),
  }),
}));

// Mock the parse module to avoid DOM dependencies
vi.mock("../parse", () => ({
  parseMarimoIslandApps: () => [],
  createMarimoFile: vi.fn(),
}));

// Mock uuid to have predictable tokens
vi.mock("@/utils/uuid", () => ({
  generateUUID: () => "test-uuid-12345",
}));

// Mock getMarimoVersion
vi.mock("@/core/meta/globals", () => ({
  getMarimoVersion: () => "0.0.0-test",
}));

// Mock the jotai store
vi.mock("@/core/state/jotai", () => ({
  store: {
    set: vi.fn(),
  },
}));

// Now import the bridge class
import { IslandsPyodideBridge } from "../bridge";

describe("IslandsPyodideBridge", () => {
  let bridge: IslandsPyodideBridge;

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the singleton by clearing the window property
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (window as any)._marimo_private_IslandsPyodideBridge;
    // Access the singleton - creates a fresh instance
    bridge = IslandsPyodideBridge.INSTANCE;
  });

  afterEach(() => {
    // Clean up singleton
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (window as any)._marimo_private_IslandsPyodideBridge;
  });

  describe("sendComponentValues", () => {
    it("should include type field and token in control request", async () => {
      const request = {
        objectIds: ["Hbol-0"],
        values: [58],
      };

      await bridge.sendComponentValues(request);

      expect(mockBridge).toHaveBeenCalledWith({
        functionName: "put_control_request",
        payload: {
          type: "update-ui-element",
          objectIds: ["Hbol-0"],
          values: [58],
          token: "test-uuid-12345",
        },
      });
    });

    it("should preserve all request properties", async () => {
      const request = {
        objectIds: ["slider-1", "slider-2"],
        values: [10, 20],
      };

      await bridge.sendComponentValues(request);

      expect(mockBridge).toHaveBeenCalledWith({
        functionName: "put_control_request",
        payload: expect.objectContaining({
          type: "update-ui-element",
          objectIds: ["slider-1", "slider-2"],
          values: [10, 20],
        }),
      });
    });
  });

  describe("sendFunctionRequest", () => {
    it("should include type field in control request", async () => {
      const request = {
        functionCallId: "call-123",
        namespace: "test_namespace",
        functionName: "my_function",
        args: { x: 1, y: 2 },
      };

      await bridge.sendFunctionRequest(request);

      expect(mockBridge).toHaveBeenCalledWith({
        functionName: "put_control_request",
        payload: {
          type: "invoke-function",
          functionCallId: "call-123",
          namespace: "test_namespace",
          functionName: "my_function",
          args: { x: 1, y: 2 },
        },
      });
    });
  });

  describe("sendRun", () => {
    it("should include type field in control request", async () => {
      const request = {
        cellIds: ["cell-1", "cell-2"],
        codes: ["print('hello')", "print('world')"],
      };

      await bridge.sendRun(request);

      expect(mockBridge).toHaveBeenCalledWith({
        functionName: "put_control_request",
        payload: {
          type: "execute-cells",
          cellIds: ["cell-1", "cell-2"],
          codes: ["print('hello')", "print('world')"],
        },
      });
    });

    it("should call loadPackages before putControlRequest", async () => {
      const request = {
        cellIds: ["cell-1"],
        codes: ["import pandas"],
      };

      await bridge.sendRun(request);

      // Verify loadPackages was called with joined codes
      expect(mockLoadPackages).toHaveBeenCalledWith("import pandas");

      // Verify order: loadPackages should be called before bridge
      const loadPackagesCallOrder =
        mockLoadPackages.mock.invocationCallOrder[0];
      const bridgeCallOrder = mockBridge.mock.invocationCallOrder[0];
      expect(loadPackagesCallOrder).toBeLessThan(bridgeCallOrder);
    });
  });

  describe("sendModelValue", () => {
    it("should include type field in control request", async () => {
      const request = {
        modelId: "widget-1",
        message: {
          method: "update" as const,
          state: { value: 42 },
          bufferPaths: [],
        },
        buffers: [],
      };

      await bridge.sendModelValue(request);

      expect(mockBridge).toHaveBeenCalledWith({
        functionName: "put_control_request",
        payload: {
          type: "model",
          modelId: "widget-1",
          message: {
            method: "update",
            state: { value: 42 },
            bufferPaths: [],
          },
          buffers: [],
        },
      });
    });
  });

  describe("control request message format", () => {
    it("should always include the type field required by msgspec", async () => {
      // Test all methods to ensure they include the type field
      await bridge.sendComponentValues({ objectIds: [], values: [] });
      await bridge.sendFunctionRequest({
        functionCallId: "",
        namespace: "",
        functionName: "",
        args: {},
      });
      await bridge.sendRun({ cellIds: [], codes: [] });
      await bridge.sendModelValue({
        modelId: "",
        message: { method: "update", state: {}, bufferPaths: [] },
        buffers: [],
      });

      // All calls should have the type field
      const allCalls = mockBridge.mock.calls;
      for (const call of allCalls) {
        const payload = call[0].payload;
        expect(payload).toHaveProperty("type");
        expect(typeof payload.type).toBe("string");
      }
    });
  });
});
