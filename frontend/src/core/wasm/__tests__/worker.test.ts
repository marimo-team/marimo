/* Copyright 2026 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import { loadPyodide } from "pyodide";
import { afterEach, expect, it, vi } from "vitest";
import { defaultUserConfig } from "@/core/config/config-schema";
import { Deferred } from "@/utils/Deferred";
import { DefaultWasmController } from "../worker/bootstrap";
import { getController } from "../worker/getController";
import type { WasmRuntimeConfig } from "../runtime-config";

interface WorkerRequests {
  startSession(opts: {
    queryParameters: Record<string, string | string[]>;
    code: string;
    filename: string;
    userConfig: ReturnType<typeof defaultUserConfig>;
  }): Promise<void>;
  notebookSubscribe(opts: { id: string; cursor: string | null }): Promise<void>;
  notebookUnsubscribe(id: string): Promise<void>;
}

const { rpc, handlers } = vi.hoisted(() => ({
  handlers: {} as {
    requests: WorkerRequests;
    bootstrap: (config: WasmRuntimeConfig) => void;
  },
  rpc: {
    send: Object.assign(vi.fn(), {
      initialized: vi.fn(),
      initializedError: vi.fn(),
      initializingMessage: vi.fn(),
      notebookEvent: vi.fn(),
    }),
  },
}));

vi.mock("rpc-anywhere", () => ({
  createRPCRequestHandler: (requests: WorkerRequests) => {
    handlers.requests = requests;
    return requests;
  },
  createWorkerParentTransport: vi.fn(),
  createRPC: () => ({
    ...rpc,
    addMessageListener: (
      _name: string,
      listener: (config: WasmRuntimeConfig) => void,
    ) => {
      handlers.bootstrap = listener;
    },
  }),
}));
vi.mock("pyodide", () => ({ loadPyodide: vi.fn(), version: "314.0.0" }));
vi.mock("../worker/getController", () => ({ getController: vi.fn() }));
vi.mock("../worker/getMarimoWheel", () => ({
  getMarimoWheel: () => "marimo-base",
}));

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
  vi.resetModules();
});

async function startWorker(subscribing = Promise.resolve()) {
  const subscribers = new Map<string, (event: string) => void>();
  const event = JSON.stringify({
    event: "marimo",
    data: { marimo: { op: "query-params-set", key: "startup", value: "ran" } },
  });
  const notebook = {
    subscribe: vi.fn(
      async (id: string, _cursor: unknown, emit: (event: string) => void) => {
        await subscribing;
        subscribers.set(id, emit);
      },
    ),
    unsubscribe: (id: string) => subscribers.delete(id),
    set_persistence: vi.fn(),
    destroy: vi.fn(),
  };
  const bridge = { notebook, destroy: vi.fn() };
  const init = Object.assign(
    vi.fn(() => subscribers.forEach((emit) => emit(event))),
    { destroy: vi.fn() },
  );
  const stop = Object.assign(
    vi.fn(async () => subscribers.clear()),
    {
      destroy: vi.fn(),
    },
  );
  const packages = { toJs: () => [], destroy: vi.fn() };
  const resources = Object.assign([bridge, init, packages, stop], {
    destroy: vi.fn(),
  });
  const pyodide = {
    runPython: vi.fn(() => resources),
    loadPackagesFromImports: vi.fn(async () => undefined),
    loadedPackages: {},
  };
  vi.mocked(loadPyodide).mockResolvedValue(
    pyodide as unknown as PyodideInterface,
  );
  const controller = new DefaultWasmController();
  vi.spyOn(controller, "mountFilesystem").mockResolvedValue({
    code: "",
    filename: "notebook.py",
  });
  vi.mocked(getController).mockResolvedValue(controller);
  await import("../worker/worker");
  handlers.bootstrap({ version: "0.25.1" });
  await handlers.requests.startSession({
    code: "",
    filename: "notebook.py",
    queryParameters: {},
    userConfig: defaultUserConfig(),
  });
  return { controller, init, notebook, event, pyodide };
}

it("delivers startup notifications after a delayed first subscription, without rerunning on resubscribe", async () => {
  const { controller, init, event, pyodide } = await startWorker();
  try {
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(rpc.send.initialized).toHaveBeenCalledOnce();
    expect(pyodide.loadPackagesFromImports).toHaveResolved();
    expect(init).not.toHaveBeenCalled();

    await handlers.requests.notebookSubscribe({ id: "first", cursor: null });
    await vi.waitFor(() => expect(init).toHaveBeenCalledOnce());
    expect(rpc.send.notebookEvent.mock.calls).toEqual([
      [{ id: "first", event }],
    ]);

    await handlers.requests.notebookUnsubscribe("first");
    await handlers.requests.notebookSubscribe({ id: "second", cursor: null });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(init).toHaveBeenCalledOnce();
  } finally {
    await controller.stopSession();
  }
});

it("does not authorize startup through a subscription canceled while opening", async () => {
  const subscribing = new Deferred<void>();
  const { controller, init, notebook } = await startWorker(subscribing.promise);
  try {
    const opened = handlers.requests.notebookSubscribe({
      id: "canceled",
      cursor: null,
    });
    await vi.waitFor(() => expect(notebook.subscribe).toHaveBeenCalledOnce());
    const closed = handlers.requests.notebookUnsubscribe("canceled");
    subscribing.resolve();
    await Promise.all([opened, closed]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(init).not.toHaveBeenCalled();

    await handlers.requests.notebookSubscribe({ id: "active", cursor: null });
    await vi.waitFor(() => expect(init).toHaveBeenCalledOnce());
  } finally {
    await controller.stopSession();
  }
});

it("waits for a successful subscription after an opening failure", async () => {
  const { controller, init, notebook } = await startWorker();
  try {
    notebook.subscribe.mockRejectedValueOnce(new Error("Subscription failed"));
    await expect(
      handlers.requests.notebookSubscribe({ id: "failed", cursor: null }),
    ).rejects.toThrow("Subscription failed");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(init).not.toHaveBeenCalled();

    await handlers.requests.notebookSubscribe({ id: "active", cursor: null });
    await vi.waitFor(() => expect(init).toHaveBeenCalledOnce());
  } finally {
    await controller.stopSession();
  }
});
