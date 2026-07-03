/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  mockFallbackReadFile,
  mockNotebookReadFile,
  mockStartSession,
  rpcListeners,
} = vi.hoisted(() => ({
  mockFallbackReadFile: vi.fn(),
  mockNotebookReadFile: vi.fn(),
  mockStartSession: vi.fn(),
  rpcListeners: {} as Record<string, () => void>,
}));

// Mock browser globals before any imports
vi.stubGlobal("crossOriginIsolated", false);
vi.stubGlobal(
  "Worker",
  vi.fn(() => ({
    addEventListener: vi.fn(),
    postMessage: vi.fn(),
    terminate: vi.fn(),
  })),
);

class MockURL extends URL {
  static override createObjectURL = vi.fn(() => "blob:mock-url");
  static override revokeObjectURL = vi.fn();
}
vi.stubGlobal("URL", MockURL);

vi.mock("@/core/wasm/rpc", () => ({
  getWorkerRPC: () => ({
    proxy: {
      request: {
        bridge: vi.fn(),
        startSession: mockStartSession,
        readFile: vi.fn(),
        readNotebook: vi.fn(),
        saveNotebook: vi.fn(),
      },
      send: { consumerReady: vi.fn() },
    },
    addMessageListener: (event: string, cb: () => void) => {
      rpcListeners[event] = cb;
    },
  }),
}));

vi.mock("@/core/meta/globals", () => ({
  getMarimoVersion: () => "0.0.0-test",
}));

vi.mock("@/core/wasm/utils", () => ({
  isWasm: () => true,
}));

vi.mock("@/core/wasm/store", () => ({
  fallbackFileStore: { readFile: mockFallbackReadFile, saveFile: vi.fn() },
  notebookFileStore: { readFile: mockNotebookReadFile, saveFile: vi.fn() },
}));

// Import after all mocks are set up
import { defaultUserConfig } from "@/core/config/config-schema";
import { userConfigAtom } from "@/core/config/config";
import { store } from "@/core/state/jotai";
import { initialModeAtom } from "@/core/mode";
import { filenameAtom } from "@/core/saving/file-state";
import { Logger } from "@/utils/Logger";
import { getWasmWorkerName, PyodideBridge } from "../bridge";
import { wasmWheelUrlsAtom } from "../state";

// Access INSTANCE once at module level so the constructor runs (and
// addMessageListener populates rpcListeners) before any test executes.
void PyodideBridge.INSTANCE;

describe("PyodideBridge.readCode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFallbackReadFile.mockResolvedValue("");
    mockNotebookReadFile.mockResolvedValue("");
    mockStartSession.mockResolvedValue(undefined);
    store.set(filenameAtom, "notebook.py");
    store.set(initialModeAtom, "read");
    store.set(userConfigAtom, defaultUserConfig());
    store.set(wasmWheelUrlsAtom, []);
  });

  afterEach(() => {
    store.set(filenameAtom, null);
    store.set(initialModeAtom, undefined);
    store.set(userConfigAtom, defaultUserConfig());
    store.set(wasmWheelUrlsAtom, []);
  });

  it("passes same-origin included wheel URLs to the worker", async () => {
    mockNotebookReadFile.mockResolvedValue("import demo_pkg");
    store.set(wasmWheelUrlsAtom, [
      "public/wheels/demo_pkg-0.1.0-py3-none-any.whl",
      "",
      "http://[::1",
      "https://cdn.example.com/extra_pkg-0.1.0-py3-none-any.whl",
    ]);
    const warn = vi.spyOn(Logger, "warn").mockImplementation(() => undefined);

    rpcListeners.ready();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockStartSession).toHaveBeenCalledWith(
      expect.objectContaining({
        code: "import demo_pkg",
        filename: "notebook.py",
        wheelUrls: [
          new URL(
            "public/wheels/demo_pkg-0.1.0-py3-none-any.whl",
            document.baseURI,
          ).toString(),
        ],
      }),
    );
    expect(warn).toHaveBeenCalledTimes(3);
    warn.mockRestore();
  });

  it("reads from notebookFileStore in read mode", async () => {
    store.set(initialModeAtom, "read");
    // Trigger getSaveWorker — it reads the current mode and returns a stub
    // whose readNotebook delegates to notebookFileStore.
    rpcListeners.initialized();
    mockNotebookReadFile.mockResolvedValue(
      "import numpy as np\nprint(np.__version__)",
    );

    const result = await PyodideBridge.INSTANCE.readCode();

    expect(result).toEqual({
      contents: "import numpy as np\nprint(np.__version__)",
    });
    expect(mockNotebookReadFile).toHaveBeenCalledTimes(1);
  });

  it("returns empty string when notebookFileStore has no code in read mode", async () => {
    store.set(initialModeAtom, "read");
    rpcListeners.initialized();
    mockNotebookReadFile.mockResolvedValue(null);

    const result = await PyodideBridge.INSTANCE.readCode();

    expect(result).toEqual({ contents: "" });
  });

  it("does not call notebookFileStore in edit mode", async () => {
    store.set(initialModeAtom, "edit");
    // getSaveWorker in edit mode creates a real worker (mocked); readNotebook
    // goes to the RPC proxy, not notebookFileStore.
    rpcListeners.initialized();

    await PyodideBridge.INSTANCE.readCode();

    expect(mockNotebookReadFile).not.toHaveBeenCalled();
  });
});

describe("getWasmWorkerName", () => {
  afterEach(() => {
    delete (window as unknown as { __MARIMO_HAS_WASM_CONTROLLER__?: boolean })
      .__MARIMO_HAS_WASM_CONTROLLER__;
  });

  it("returns the version without suffix by default", () => {
    expect(getWasmWorkerName()).toBe("0.0.0-test");
  });

  it("appends ::controller when the host opts in", () => {
    (
      window as unknown as { __MARIMO_HAS_WASM_CONTROLLER__?: boolean }
    ).__MARIMO_HAS_WASM_CONTROLLER__ = true;
    expect(getWasmWorkerName()).toBe("0.0.0-test::controller");
  });

  it("does not append the suffix for non-true values", () => {
    (
      window as unknown as { __MARIMO_HAS_WASM_CONTROLLER__?: unknown }
    ).__MARIMO_HAS_WASM_CONTROLLER__ = "true";
    expect(getWasmWorkerName()).toBe("0.0.0-test");
  });
});
