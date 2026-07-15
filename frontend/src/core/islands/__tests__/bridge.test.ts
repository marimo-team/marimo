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
  payloadBacked?: boolean;
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
  mockReplaceSessionRequest,
  mockStopSessionRequest,
  mockStartSessionRequest,
  mockParseMarimoIslandApps,
  mockCreateMarimoFile,
  mockGetMarimoExportContext,
} = vi.hoisted(() => ({
  mockBridge: vi.fn(),
  mockLoadPackages: vi.fn(),
  mockReplaceSessionRequest: vi.fn(),
  mockStopSessionRequest: vi.fn(),
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
        replaceSession: mockReplaceSessionRequest,
        startSession: mockStartSessionRequest,
        stopSession: mockStopSessionRequest,
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

  function mockSingleApp(file = "generated app 1") {
    mockParseMarimoIslandApps.mockReturnValue([
      {
        id: "app-1",
        cells: [{ code: "x = 1", idx: 0, output: "<div>1</div>" }],
      },
    ]);
    mockCreateMarimoFile.mockReturnValue(file);
    bridge.workerReady.resolve();
  }

  async function initializeSingleApp() {
    mockSingleApp();
    await bridge.initializeApps();
  }

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
        sessionGeneration: 1,
      });
    });

    it("should ignore trusted export notebook code for a payload-backed app", async () => {
      const payloadApp = {
        id: "app-1",
        payloadBacked: true,
        cells: [{ code: "x = 1", idx: 0, output: "<div>1</div>" }],
      };
      mockParseMarimoIslandApps.mockReturnValue([payloadApp]);
      mockGetMarimoExportContext.mockReturnValue({
        trusted: true,
        notebookCode: "full notebook should be ignored",
      });
      mockCreateMarimoFile.mockReturnValue("generated payload app");

      await (
        bridge as unknown as { startSessionsForAllApps(): Promise<void> }
      ).startSessionsForAllApps();

      expect(mockCreateMarimoFile).toHaveBeenCalledWith(payloadApp);
      expect(mockStartSessionRequest).toHaveBeenCalledWith({
        appId: "app-1",
        code: "generated payload app",
        sessionGeneration: 1,
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
        sessionGeneration: 1,
      });
      expect(mockStartSessionRequest).toHaveBeenNthCalledWith(2, {
        appId: "app-2",
        code: "generated app 2",
        sessionGeneration: 2,
      });

      await bridge.sendComponentValues({
        objectIds: [uiElementId("slider-1")],
        values: [2],
      });
      await bridge.stopSession();

      expect(mockReplaceSessionRequest).not.toHaveBeenCalled();
      expect(mockStopSessionRequest).not.toHaveBeenCalled();
      expect(mockBridge).toHaveBeenCalledWith({
        appId: "app-1",
        functionName: "put_control_request",
        payload: {
          objectIds: ["slider-1"],
          token: "test-uuid-12345",
          type: "update-ui-element",
          values: [2],
        },
        sessionGeneration: 1,
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
        sessionGeneration: 1,
      });
    });
  });

  describe("app lifecycle", () => {
    it("holds controls until the first app session is ready", async () => {
      mockParseMarimoIslandApps.mockReturnValue([
        {
          id: "app-1",
          cells: [{ code: "x = 1", idx: 0, output: "<div>1</div>" }],
        },
      ]);
      mockCreateMarimoFile.mockReturnValue("generated app 1");

      const initialization = bridge.initializeApps();
      const control = bridge.sendComponentValues({
        objectIds: [uiElementId("slider-1")],
        values: [2],
      });
      await Promise.resolve();

      expect(mockBridge).not.toHaveBeenCalled();

      bridge.workerReady.resolve();
      await Promise.all([initialization, control]);
      expect(mockBridge).toHaveBeenCalledWith(
        expect.objectContaining({
          appId: "app-1",
          sessionGeneration: 1,
        }),
      );
    });

    it("starts the first app, skips duplicates, and replaces changed source", async () => {
      mockSingleApp();

      await bridge.initializeApps();
      await bridge.initializeApps();
      await bridge.sendComponentValues({
        objectIds: [uiElementId("slider-1")],
        values: [2],
      });

      expect(mockStartSessionRequest).toHaveBeenCalledOnce();
      expect(mockStartSessionRequest).toHaveBeenCalledWith({
        appId: "app-1",
        code: "generated app 1",
        sessionGeneration: 1,
      });
      expect(mockReplaceSessionRequest).not.toHaveBeenCalled();
      expect(mockBridge).toHaveBeenCalledWith(
        expect.objectContaining({
          appId: "app-1",
          sessionGeneration: 1,
        }),
      );
      mockCreateMarimoFile.mockReturnValue("generated app 2");
      await bridge.initializeApps();

      expect(mockReplaceSessionRequest).toHaveBeenCalledOnce();
      expect(mockReplaceSessionRequest).toHaveBeenCalledWith({
        appId: "app-1",
        code: "generated app 2",
        sessionGeneration: 2,
      });
    });

    it("stops the matching active app", async () => {
      mockSingleApp();
      await bridge.initializeApps();

      await bridge.stopSession("other-app");
      await bridge.stopSession("app-1");

      expect(mockStopSessionRequest).toHaveBeenCalledOnce();
      expect(mockStopSessionRequest).toHaveBeenCalledWith({
        appId: "app-1",
        sessionGeneration: 1,
      });
    });

    it("keeps controls sent during stop scoped to the stopped app", async () => {
      mockSingleApp();
      await bridge.initializeApps();
      mockBridge.mockClear();
      let finishStop!: () => void;
      mockStopSessionRequest.mockReturnValueOnce(
        new Promise<void>((resolve) => {
          finishStop = resolve;
        }),
      );

      const stop = bridge.stopSession("app-1");
      await vi.waitFor(() =>
        expect(mockStopSessionRequest).toHaveBeenCalledOnce(),
      );
      const control = bridge.sendComponentValues({
        objectIds: [uiElementId("slider-1")],
        values: [2],
      });
      mockParseMarimoIslandApps.mockReturnValue([
        {
          id: "app-2",
          cells: [{ code: "x = 2", idx: 0, output: "<div>2</div>" }],
        },
      ]);
      mockCreateMarimoFile.mockReturnValue("generated app 2");
      const nextInitialization = bridge.initializeApps();

      finishStop();
      await Promise.all([stop, control, nextInitialization]);

      expect(mockBridge).toHaveBeenCalledWith(
        expect.objectContaining({
          appId: "app-1",
          sessionGeneration: 1,
        }),
      );
    });

    it("allows initialization to retry after replacement fails", async () => {
      mockSingleApp();
      await bridge.initializeApps();
      mockCreateMarimoFile.mockReturnValue("generated app 2");
      mockReplaceSessionRequest.mockRejectedValueOnce(
        new Error("replacement failed"),
      );

      await expect(bridge.initializeApps()).rejects.toThrow(
        "replacement failed",
      );
      await bridge.initializeApps();

      expect(mockReplaceSessionRequest).toHaveBeenCalledOnce();
      expect(mockStartSessionRequest).toHaveBeenCalledTimes(2);
      expect(mockStartSessionRequest).toHaveBeenLastCalledWith({
        appId: "app-1",
        code: "generated app 2",
        sessionGeneration: 3,
      });
    });

    it("scopes controls to the replacement active when they were sent", async () => {
      mockSingleApp();
      await bridge.initializeApps();
      mockBridge.mockClear();
      mockCreateMarimoFile.mockReturnValue("generated app 2");
      let finishSecondApp!: () => void;
      let finishThirdApp!: () => void;
      mockReplaceSessionRequest
        .mockReturnValueOnce(
          new Promise<void>((resolve) => {
            finishSecondApp = resolve;
          }),
        )
        .mockReturnValueOnce(
          new Promise<void>((resolve) => {
            finishThirdApp = resolve;
          }),
        );

      const secondInitialization = bridge.initializeApps();
      await vi.waitFor(() =>
        expect(mockReplaceSessionRequest).toHaveBeenCalledOnce(),
      );
      const control = bridge.sendComponentValues({
        objectIds: [uiElementId("slider-1")],
        values: [2],
      });
      mockParseMarimoIslandApps.mockReturnValue([
        {
          id: "app-2",
          cells: [{ code: "x = 3", idx: 0, output: "<div>3</div>" }],
        },
      ]);
      mockCreateMarimoFile.mockReturnValue("generated app 3");
      const thirdInitialization = bridge.initializeApps();

      expect(mockBridge).not.toHaveBeenCalled();

      finishSecondApp();
      await vi.waitFor(() => expect(mockBridge).toHaveBeenCalledOnce());
      expect(mockBridge).toHaveBeenCalledWith(
        expect.objectContaining({
          appId: "app-1",
          sessionGeneration: 2,
        }),
      );

      finishThirdApp();
      await Promise.all([secondInitialization, thirdInitialization, control]);
    });

    it("keeps controls from a failed replacement out of the next app", async () => {
      mockSingleApp();
      await bridge.initializeApps();
      mockBridge.mockClear();
      mockCreateMarimoFile.mockReturnValue("generated app 2");
      let failReplacement!: (error: Error) => void;
      mockReplaceSessionRequest.mockReturnValueOnce(
        new Promise<void>((_resolve, reject) => {
          failReplacement = reject;
        }),
      );

      const failedInitialization = bridge.initializeApps();
      await vi.waitFor(() =>
        expect(mockReplaceSessionRequest).toHaveBeenCalledOnce(),
      );
      const control = bridge.sendComponentValues({
        objectIds: [uiElementId("slider-1")],
        values: [2],
      });
      failReplacement(new Error("replacement failed"));
      await expect(failedInitialization).rejects.toThrow("replacement failed");

      mockParseMarimoIslandApps.mockReturnValue([
        {
          id: "app-2",
          cells: [{ code: "x = 3", idx: 0, output: "<div>3</div>" }],
        },
      ]);
      mockCreateMarimoFile.mockReturnValue("generated app 3");
      await Promise.all([bridge.initializeApps(), control]);

      expect(mockBridge).toHaveBeenCalledWith(
        expect.objectContaining({
          appId: "app-1",
          sessionGeneration: 2,
        }),
      );
    });
  });

  describe("sendComponentValues", () => {
    beforeEach(initializeSingleApp);

    it("should include type field and token in control request", async () => {
      const request = {
        objectIds: [uiElementId("Hbol-0")],
        values: [58],
      };

      await bridge.sendComponentValues(request);

      expect(mockBridge).toHaveBeenCalledWith({
        appId: "app-1",
        functionName: "put_control_request",
        payload: {
          type: "update-ui-element",
          objectIds: ["Hbol-0"],
          values: [58],
          token: "test-uuid-12345",
        },
        sessionGeneration: 1,
      });
    });

    it("should preserve all request properties", async () => {
      const request = {
        objectIds: [uiElementId("slider-1"), uiElementId("slider-2")],
        values: [10, 20],
      };

      await bridge.sendComponentValues(request);

      expect(mockBridge).toHaveBeenCalledWith({
        appId: "app-1",
        functionName: "put_control_request",
        payload: expect.objectContaining({
          type: "update-ui-element",
          objectIds: ["slider-1", "slider-2"],
          values: [10, 20],
        }),
        sessionGeneration: 1,
      });
    });
  });

  describe("sendFunctionRequest", () => {
    beforeEach(initializeSingleApp);

    it("should include type field in control request", async () => {
      const request = {
        functionCallId: requestId("call-123"),
        namespace: "test_namespace",
        functionName: "my_function",
        args: { x: 1, y: 2 },
      };

      await bridge.sendFunctionRequest(request);

      expect(mockBridge).toHaveBeenCalledWith({
        appId: "app-1",
        functionName: "put_control_request",
        payload: {
          type: "invoke-function",
          functionCallId: "call-123",
          namespace: "test_namespace",
          functionName: "my_function",
          args: { x: 1, y: 2 },
        },
        sessionGeneration: 1,
      });
    });
  });

  describe("sendRun", () => {
    beforeEach(initializeSingleApp);

    it("should include type field in control request", async () => {
      const request = {
        cellIds: [cellId("cell-1"), cellId("cell-2")],
        codes: ["print('hello')", "print('world')"],
      };

      await bridge.sendRun(request);

      expect(mockBridge).toHaveBeenCalledWith({
        appId: "app-1",
        functionName: "put_control_request",
        payload: {
          type: "execute-cells",
          cellIds: ["cell-1", "cell-2"],
          codes: ["print('hello')", "print('world')"],
        },
        sessionGeneration: 1,
      });
    });

    it("should call loadPackages before putControlRequest", async () => {
      const request = {
        cellIds: [cellId("cell-1")],
        codes: ["import pandas"],
      };

      await bridge.sendRun(request);

      // Verify loadPackages was called with joined codes
      expect(mockLoadPackages).toHaveBeenCalledWith({
        appId: "app-1",
        code: "import pandas",
        sessionGeneration: 1,
      });

      // Verify order: loadPackages should be called before bridge
      const loadPackagesCallOrder =
        mockLoadPackages.mock.invocationCallOrder[0];
      const bridgeCallOrder = mockBridge.mock.invocationCallOrder[0];
      expect(loadPackagesCallOrder).toBeLessThan(bridgeCallOrder);
    });
  });

  describe("sendModelValue", () => {
    beforeEach(initializeSingleApp);

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
        appId: "app-1",
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
        sessionGeneration: 1,
      });
    });
  });

  describe("control request message format", () => {
    beforeEach(initializeSingleApp);

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
