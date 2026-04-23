/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  cellId,
  requestId,
  uiElementId,
  widgetModelId,
} from "@/__tests__/branded";

type Base64String = components["schemas"]["Base64String"];
interface TestIslandApp {
  id: string;
  cells: { code: string; idx: number; output: string }[];
}
interface TestExportContext {
  trusted: true;
  notebookCode?: string;
}

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
const {
  mockBridge,
  mockLoadPackages,
  mockStartSessionRequest,
  mockParseMarimoIslandApps,
  mockCreateMarimoFile,
  mockGetMarimoExportContext,
} = vi.hoisted(() => ({
  mockBridge: vi.fn(),
  mockLoadPackages: vi.fn(),
  mockStartSessionRequest: vi.fn(),
  mockParseMarimoIslandApps: vi.fn<() => TestIslandApp[]>(() => []),
  mockCreateMarimoFile: vi.fn(),
  mockGetMarimoExportContext: vi.fn<() => TestExportContext | undefined>(
    () => undefined,
  ),
}));

vi.mock("@/core/wasm/rpc", () => ({
  getWorkerRPC: () => ({
    proxy: {
      request: {
        bridge: mockBridge,
        loadPackages: mockLoadPackages,
        startSession: mockStartSessionRequest,
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
  parseMarimoIslandApps: mockParseMarimoIslandApps,
  createMarimoFile: mockCreateMarimoFile,
}));

// Mock uuid to have predictable tokens
vi.mock("@/utils/uuid", () => ({
  generateUUID: () => "test-uuid-12345",
}));

vi.mock("@/core/static/export-context", () => ({
  getMarimoExportContext: mockGetMarimoExportContext,
}));

// Mock getMarimoVersion
vi.mock("@/core/meta/globals", () => ({
  getMarimoVersion: () => "0.0.0-test",
}));

// Mock the jotai store
vi.mock("@/core/state/jotai", () => ({
  store: {
    get: vi.fn(),
    set: vi.fn(),
  },
}));

// Now import the bridge class
import { IslandsPyodideBridge } from "../bridge";

describe("IslandsPyodideBridge", () => {
  let bridge: IslandsPyodideBridge;

  beforeEach(() => {
    vi.clearAllMocks();
    mockParseMarimoIslandApps.mockReturnValue([]);
    mockCreateMarimoFile.mockReset();
    mockGetMarimoExportContext.mockReturnValue(undefined);
    bridge = new IslandsPyodideBridge({ autoStartSessions: false });
  });

  describe("startSessionsForAllApps", () => {
    it("should prefer trusted export notebook code when there is exactly one reactive app", async () => {
      mockParseMarimoIslandApps.mockReturnValue([
        {
          id: "app-1",
          cells: [{ code: "x = 1", idx: 0, output: "<div>1</div>" }],
        },
      ]);
      mockGetMarimoExportContext.mockReturnValue({
        trusted: true,
        notebookCode:
          "import marimo\napp = marimo.App()\n@app.cell\ndef __():\n    x = 1\n    return",
      });

      await (
        bridge as unknown as { startSessionsForAllApps(): Promise<void> }
      ).startSessionsForAllApps();

      expect(mockCreateMarimoFile).not.toHaveBeenCalled();
      expect(mockStartSessionRequest).toHaveBeenCalledWith({
        appId: "app-1",
        code: "import marimo\napp = marimo.App()\n@app.cell\ndef __():\n    x = 1\n    return",
      });
    });

    it("should keep synthesized per-app files for multiple reactive apps even when export context exists", async () => {
      mockParseMarimoIslandApps.mockReturnValue([
        {
          id: "app-1",
          cells: [{ code: "x = 1", idx: 0, output: "<div>1</div>" }],
        },
        {
          id: "app-2",
          cells: [{ code: "y = 2", idx: 0, output: "<div>2</div>" }],
        },
      ]);
      mockGetMarimoExportContext.mockReturnValue({
        trusted: true,
        notebookCode: "full notebook should be ignored",
      });
      mockCreateMarimoFile
        .mockReturnValueOnce("generated app 1")
        .mockReturnValueOnce("generated app 2");

      await (
        bridge as unknown as { startSessionsForAllApps(): Promise<void> }
      ).startSessionsForAllApps();

      expect(mockCreateMarimoFile).toHaveBeenCalledTimes(2);
      expect(mockStartSessionRequest).toHaveBeenNthCalledWith(1, {
        appId: "app-1",
        code: "generated app 1",
      });
      expect(mockStartSessionRequest).toHaveBeenNthCalledWith(2, {
        appId: "app-2",
        code: "generated app 2",
      });
    });

    it("should synthesize a file for a single app when no trusted export context is present", async () => {
      mockParseMarimoIslandApps.mockReturnValue([
        {
          id: "app-1",
          cells: [{ code: "x = 1", idx: 0, output: "<div>1</div>" }],
        },
      ]);
      mockCreateMarimoFile.mockReturnValue("generated app 1");

      await (
        bridge as unknown as { startSessionsForAllApps(): Promise<void> }
      ).startSessionsForAllApps();

      expect(mockCreateMarimoFile).toHaveBeenCalledTimes(1);
      expect(mockStartSessionRequest).toHaveBeenCalledWith({
        appId: "app-1",
        code: "generated app 1",
      });
    });
  });

  describe("sendComponentValues", () => {
    it("should include type field and token in control request", async () => {
      const request = {
        objectIds: [uiElementId("Hbol-0")],
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
        objectIds: [uiElementId("slider-1"), uiElementId("slider-2")],
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
        functionCallId: requestId("call-123"),
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
        cellIds: [cellId("cell-1"), cellId("cell-2")],
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
        cellIds: [cellId("cell-1")],
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
        modelId: widgetModelId("widget-1"),
        message: {
          method: "update" as const,
          state: { value: 42 },
          bufferPaths: [],
        },
        buffers: [] as Base64String[],
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
        functionCallId: requestId(""),
        namespace: "",
        functionName: "",
        args: {},
      });
      await bridge.sendRun({ cellIds: [], codes: [] });
      await bridge.sendModelValue({
        modelId: widgetModelId(""),
        message: { method: "update", state: {}, bufferPaths: [] },
        buffers: [] as Base64String[],
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
