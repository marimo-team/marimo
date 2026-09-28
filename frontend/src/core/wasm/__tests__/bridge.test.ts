/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { Deferred } from "@/utils/Deferred";

const {
  mockBridge,
  mockLoadPackages,
  mockNotebookReadFile,
  mockReadNotebook,
  mockSaveNotebook,
  mockBootstrap,
  rpcListeners,
} = vi.hoisted(() => ({
  mockBridge: vi.fn(),
  mockLoadPackages: vi.fn(),
  mockNotebookReadFile: vi.fn(),
  mockReadNotebook: vi.fn(),
  mockSaveNotebook: vi.fn(),
  mockBootstrap: vi.fn(),
  rpcListeners: {} as Record<string, () => void>,
}));

// Mock browser globals before any imports
vi.stubGlobal("crossOriginIsolated", false);
vi.stubGlobal(
  "Worker",
  // vitest 4 requires a `function` (not an arrow) for mocks called with `new`
  vi.fn(function () {
    return {
      addEventListener: vi.fn(),
      postMessage: vi.fn(),
      terminate: vi.fn(),
    };
  }),
);

class MockURL extends URL {
  static override createObjectURL = vi.fn(() => "blob:mock-url");
  static override revokeObjectURL = vi.fn();
}
vi.stubGlobal("URL", MockURL);

vi.mock("@/core/wasm/rpc", () => ({
  getWorkerRPC: () => ({
    send: { bootstrap: mockBootstrap },
    proxy: {
      request: {
        bridge: mockBridge,
        loadPackages: mockLoadPackages,
        startSession: vi.fn(),
        readFile: vi.fn(),
        readNotebook: mockReadNotebook,
        saveNotebook: mockSaveNotebook,
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
  fallbackFileStore: { readFile: vi.fn(), saveFile: vi.fn() },
  notebookFileStore: { readFile: mockNotebookReadFile, saveFile: vi.fn() },
}));

// Import after all mocks are set up
import { store } from "@/core/state/jotai";
import { initialModeAtom } from "@/core/mode";
import { appConfigAtom } from "@/core/config/config";
import { parseAppConfig } from "@/core/config/config-schema";
import { getWasmWorkerName, PyodideBridge } from "../bridge";

// Access INSTANCE once at module level so the constructor runs (and
// addMessageListener populates rpcListeners) before any test executes.
void PyodideBridge.INSTANCE;

describe("PyodideBridge.readCode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    store.set(initialModeAtom, undefined);
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

    expect(mockBootstrap).toHaveBeenCalledWith({
      version: "0.0.0-test",
      pyodideIndexUrl: undefined,
      pyodideLockfileUrl: undefined,
      pypiIndexUrl: undefined,
    });
    expect(mockNotebookReadFile).not.toHaveBeenCalled();
  });
});

describe("PyodideBridge.exportAsScript", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the script export from the Python bridge", async () => {
    const exportedFile = {
      contents: '# %%\nprint("hello")',
      filename: "notebook.script.py",
      mediaType: "text/plain; charset=utf-8",
    };
    mockBridge.mockResolvedValue(exportedFile);

    const result = await PyodideBridge.INSTANCE.exportAsScript({
      download: false,
    });

    expect(mockBridge).toHaveBeenCalledWith({
      functionName: "export_script",
      payload: { download: false },
    });
    expect(result).toEqual(exportedFile);
  });
});

describe("PyodideBridge.sendSave", () => {
  const request = {
    cellIds: [cellId("cell-1")],
    codes: ['value = "NEW"'],
    names: ["_"],
    filename: "notebook.py",
    configs: [{}],
    layout: null,
    persist: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    store.set(initialModeAtom, "edit");
    rpcListeners.initialized();
    mockSaveNotebook.mockResolvedValue(null);
    mockReadNotebook.mockResolvedValue(
      "import marimo\napp = marimo.App()\n# NEW",
    );
  });

  afterEach(() => {
    store.set(initialModeAtom, undefined);
  });

  it("waits for the session save before generating exports", async () => {
    const mainSave = new Deferred<void>();
    mockSaveNotebook
      .mockResolvedValueOnce(null)
      .mockReturnValueOnce(mainSave.promise);

    await PyodideBridge.INSTANCE.sendSave(request);
    expect(mockSaveNotebook).toHaveBeenCalledTimes(2);
    expect(mockSaveNotebook).toHaveBeenNthCalledWith(1, request);
    expect(mockSaveNotebook).toHaveBeenNthCalledWith(2, request);

    const markdown = PyodideBridge.INSTANCE.exportAsMarkdown({
      download: false,
    });
    const script = PyodideBridge.INSTANCE.exportAsScript({
      download: false,
    });
    await Promise.resolve();
    expect(mockBridge).not.toHaveBeenCalled();

    mainSave.resolve();
    await Promise.all([markdown, script]);
    expect(mockBridge).toHaveBeenCalledWith({
      functionName: "export_markdown",
      payload: { download: false },
    });
    expect(mockBridge).toHaveBeenCalledWith({
      functionName: "export_script",
      payload: { download: false },
    });
  });
});

describe("PyodideBridge.sendRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoadPackages.mockResolvedValue(undefined);
  });

  afterEach(() => {
    store.set(appConfigAtom, parseAppConfig({}));
  });

  it("passes the current SQL output to dependency loading", async () => {
    store.set(appConfigAtom, parseAppConfig({ sql_output: "pandas" }));

    await PyodideBridge.INSTANCE.sendRun({
      cellIds: [cellId("cell-1")],
      codes: ['result = mo.sql("SELECT 1", engine="polars")'],
    });

    expect(mockLoadPackages).toHaveBeenCalledWith({
      code: 'result = mo.sql("SELECT 1", engine="polars")',
      sqlOutput: "pandas",
    });
  });
});

describe("getWasmWorkerName", () => {
  afterEach(() => {
    delete (window as unknown as { __MARIMO_HAS_WASM_CONTROLLER__?: boolean })
      .__MARIMO_HAS_WASM_CONTROLLER__;
  });

  it("returns the default worker name without suffix", () => {
    expect(getWasmWorkerName()).toBe("marimo");
  });

  it("appends ::controller when the host opts in", () => {
    (
      window as unknown as { __MARIMO_HAS_WASM_CONTROLLER__?: boolean }
    ).__MARIMO_HAS_WASM_CONTROLLER__ = true;
    expect(getWasmWorkerName()).toBe("marimo::controller");
  });

  it("does not append the suffix for non-true values", () => {
    (
      window as unknown as { __MARIMO_HAS_WASM_CONTROLLER__?: unknown }
    ).__MARIMO_HAS_WASM_CONTROLLER__ = "true";
    expect(getWasmWorkerName()).toBe("marimo");
  });
});
