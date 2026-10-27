/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { Deferred } from "@/utils/Deferred";

const {
  mockBridge,
  mockNotebookReadFile,
  mockReadNotebook,
  mockWriteNotebook,
  mockNotebookCall,
  mockSetNotebookLayout,
  mockFlush,
  parentRequests,
  mockBootstrap,
  rpcListeners,
  mockNotebookInfo,
  mockNotebookSubscribe,
  mockNotebookUnsubscribe,
} = vi.hoisted(() => ({
  mockBridge: vi.fn(),
  mockNotebookReadFile: vi.fn(),
  mockReadNotebook: vi.fn(),
  mockWriteNotebook: vi.fn(),
  mockNotebookCall: vi.fn(),
  mockSetNotebookLayout: vi.fn(),
  mockFlush: vi.fn(),
  parentRequests: {} as {
    persistNotebook?: (snapshot: {
      filename: string;
      contents: string;
    }) => Promise<void>;
  },
  mockBootstrap: vi.fn(),
  rpcListeners: {} as Record<string, () => void>,
  mockNotebookInfo: vi.fn(),
  mockNotebookSubscribe: vi.fn(),
  mockNotebookUnsubscribe: vi.fn(),
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
  public static override createObjectURL = vi.fn(() => "blob:mock-url");
  public static override revokeObjectURL = vi.fn();
}
vi.stubGlobal("URL", MockURL);

vi.mock("@/core/wasm/rpc", () => ({
  getWorkerRPC: (_worker: Worker, handlers?: typeof parentRequests) => {
    Object.assign(parentRequests, handlers);
    return {
      send: { bootstrap: mockBootstrap },
      proxy: {
        request: {
          bridge: mockBridge,
          startSession: vi.fn(),
          readFile: vi.fn(),
          readNotebook: mockReadNotebook,
          writeNotebook: mockWriteNotebook,
          notebookInfo: mockNotebookInfo,
          notebookSubscribe: mockNotebookSubscribe,
          notebookUnsubscribe: mockNotebookUnsubscribe,
          notebookCall: mockNotebookCall,
          setNotebookLayout: mockSetNotebookLayout,
        },
      },
      addMessageListener: (event: string, cb: () => void) => {
        rpcListeners[event] = cb;
      },
    };
  },
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

vi.mock("@/core/cells/document-changes", () => ({
  flushDocumentChanges: mockFlush,
  documentTransactionMiddleware: vi.fn(),
}));

// Import after all mocks are set up
import { store } from "@/core/state/jotai";
import { initialModeAtom } from "@/core/mode";
import { fixtureEvents } from "@/core/host/__tests__/fixtures";
import { fallbackFileStore, notebookFileStore } from "../store";
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
    mockNotebookInfo.mockResolvedValue({ id: "n1" });
    mockFlush.mockResolvedValue(undefined);
    mockWriteNotebook.mockResolvedValue(undefined);
    const document = fixtureEvents("notebook-events.sse").find(
      (event) => event.event === "document",
    )?.data.document;
    mockNotebookCall.mockResolvedValue({
      status: 200,
      body: { document, cells: {} },
    });
  });

  afterEach(() => {
    store.set(initialModeAtom, undefined);
  });

  it("flushes edits before asking the host to save without an editor snapshot", async () => {
    const flushed = new Deferred<void>();
    mockFlush.mockReturnValueOnce(flushed.promise);
    const saving = PyodideBridge.INSTANCE.sendSave(request);
    await Promise.resolve();
    expect(mockNotebookCall).not.toHaveBeenCalled();
    flushed.resolve();
    await saving;
    expect(mockSetNotebookLayout).toHaveBeenCalledWith(null);
    expect(mockNotebookCall).toHaveBeenCalledWith(
      expect.objectContaining({ operation: "notebook.save", body: {} }),
    );
    expect(mockWriteNotebook).not.toHaveBeenCalled();
  });

  it("does not save when flushing fails", async () => {
    mockFlush.mockRejectedValueOnce(new Error("unsynchronized edit"));
    await expect(PyodideBridge.INSTANCE.sendSave(request)).rejects.toThrow(
      "unsynchronized edit",
    );
    expect(mockNotebookCall).not.toHaveBeenCalled();
  });

  it("reports host persistence failures", async () => {
    mockNotebookCall.mockResolvedValueOnce({
      status: 409,
      body: {
        type: "tag:marimo.io,2026:host/conflict",
        title: "Conflict",
        status: 409,
        detail: "storage full",
      },
    });
    await expect(PyodideBridge.INSTANCE.sendSave(request)).rejects.toThrow(
      "storage full",
    );
  });

  it("persists exactly the host's content before acknowledging storage", async () => {
    const durable = new Deferred<void>();
    const snapshot = { filename: "notebook.py", contents: "# host revision" };
    mockWriteNotebook.mockReturnValueOnce(durable.promise);
    const writing = parentRequests.persistNotebook!(snapshot);
    await Promise.resolve();
    expect(mockWriteNotebook).toHaveBeenCalledWith(snapshot);
    expect(notebookFileStore.saveFile).not.toHaveBeenCalled();
    durable.resolve();
    await writing;
    expect(notebookFileStore.saveFile).toHaveBeenCalledWith(snapshot.contents);
    expect(fallbackFileStore.saveFile).toHaveBeenCalledWith(snapshot.contents);
  });

  it("propagates storage failure without updating the URL", async () => {
    mockWriteNotebook.mockRejectedValueOnce(new Error("IndexedDB failed"));
    await expect(
      parentRequests.persistNotebook!({
        filename: "notebook.py",
        contents: "# host",
      }),
    ).rejects.toThrow("IndexedDB failed");
    expect(notebookFileStore.saveFile).not.toHaveBeenCalled();
  });
});

it("cancels a pending notebook subscription before its RPC response", async () => {
  vi.clearAllMocks();
  store.set(initialModeAtom, "read");
  rpcListeners.initialized();
  const pending = new Deferred<void>();
  mockNotebookInfo.mockResolvedValue({ id: "n1" });
  mockNotebookSubscribe.mockReturnValue(pending.promise);
  mockNotebookUnsubscribe.mockResolvedValue(undefined);
  const controller = new AbortController();
  try {
    const backend = await PyodideBridge.INSTANCE.createNotebookBackend();
    const following = backend.transport(
      { cursor: null, signal: controller.signal },
      { open: vi.fn(), message: vi.fn() },
    );
    await vi.waitFor(() =>
      expect(mockNotebookSubscribe).toHaveBeenCalledOnce(),
    );
    const [{ id }] = mockNotebookSubscribe.mock.calls[0];
    controller.abort();
    await following;
    expect(mockNotebookUnsubscribe.mock.calls).toEqual([[id]]);

    pending.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mockNotebookUnsubscribe.mock.calls).toEqual([[id]]);
  } finally {
    controller.abort();
    pending.resolve();
    store.set(initialModeAtom, undefined);
  }
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
