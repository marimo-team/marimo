/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookEvents, StreamStopped } from "@marimo-team/client";
import { createStore } from "jotai/vanilla";
import { afterEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { ConnectionState } from "../../notebook/replica/connection";
import {
  type FakeEdit,
  type FakeSave,
  fakeBackend,
} from "../../notebook/replica/__tests__/fixtures";
import { createNotebookReplica } from "../../notebook/replica/replica";
import { createEditorBackend } from "../backend";

const wasm = vi.hoisted(() => ({ enabled: false, create: vi.fn() }));
vi.mock("../../wasm/utils", () => ({ isWasm: () => wasm.enabled }));
vi.mock("../../wasm/bridge", () => ({
  PyodideBridge: { INSTANCE: { createNotebookBackend: wasm.create } },
}));

afterEach(() => {
  wasm.enabled = false;
  wasm.create.mockReset();
  vi.unstubAllGlobals();
});

const options = {
  static: false,
  snapshot: null,
  transportType: "websocket" as const,
  url: () => "ws://localhost/ws",
  headers: () => ({}),
  notebookUrl: (id: string) =>
    new URL(`http://localhost/api/marimo/v1/notebooks/${id}`),
  waitUntilReady: async () => undefined,
  checkHealth: async () => true,
};

/** Record each socket the transport opens. They never connect. */
function sockets() {
  const opened: string[] = [];
  vi.stubGlobal(
    "WebSocket",
    class extends EventTarget {
      public constructor(url: URL) {
        super();
        opened.push(String(url));
      }
      public close() {}
    },
  );
  return opened;
}

describe("createEditorBackend", () => {
  it.each([
    ["a static notebook", { ...options, static: true }, "idle"],
    ["WASM", options, "wasm"],
    ["SSE", { ...options, transportType: "sse" as const }, "fetch"],
    ["the default", options, "socket"],
  ] as const)("follows %s", async (_name, chosen, expected) => {
    wasm.enabled = expected === "wasm";
    const worker = vi.fn(() => new Promise<void>(() => undefined));
    wasm.create.mockResolvedValue(fakeBackend({ transport: worker }));
    const fetch = vi.fn(() => new Promise<Response>(() => undefined));
    const opened = sockets();
    vi.stubGlobal("fetch", fetch);
    const events = new NotebookEvents(createEditorBackend(chosen).transport);
    await vi.waitFor(() =>
      expect(
        {
          idle: events.status === "connected" && !wasm.create.mock.calls.length,
          wasm: worker.mock.calls.length === 1,
          fetch: fetch.mock.calls.length === 1,
          socket: opened.length === 1,
        }[expected],
      ).toBe(true),
    );
    events.close();
  });

  it("edits a reported notebook on its host with the session's headers", async () => {
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(
          JSON.stringify({ type: "conflict", title: "Conflict", status: 409 }),
          {
            status: 409,
            headers: { "Content-Type": "application/problem+json" },
          },
        ),
    );
    vi.stubGlobal("fetch", fetch);
    const backend = createEditorBackend({
      ...options,
      headers: () => ({
        Authorization: "Bearer editor-token",
        "Marimo-Server-Token": "server-token",
      }),
    });
    const result = await backend
      .notebook("n1")
      .edit([], { idempotencyKey: "edit-1" });
    expect(result).toMatchObject({ ok: false, status: 409 });
    const [[input, init]] = fetch.mock.calls;
    expect(String(input)).toBe(
      "http://localhost/api/marimo/v1/notebooks/n1/edits",
    );
    const headers = new Headers(init?.headers);
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer editor-token");
    expect(headers.get("Marimo-Server-Token")).toBe("server-token");
    expect(headers.get("Idempotency-Key")).toBe("edit-1");
  });

  it("does not edit a static notebook", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const result = await createEditorBackend({ ...options, static: true })
      .notebook("n1")
      .edit([], { idempotencyKey: "edit-1" });
    expect(result).toMatchObject({ ok: false, status: 501 });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("routes WASM commands through the worker once its stream starts", async () => {
    wasm.enabled = true;
    const edit = vi.fn<FakeEdit>();
    const save = vi.fn<FakeSave>();
    const transport = vi.fn(async () => undefined);
    wasm.create.mockResolvedValue(fakeBackend({ transport, edit, save }));
    const backend = createEditorBackend(options);
    expect(wasm.create).not.toHaveBeenCalled();
    expect(() => backend.notebook("n1")).toThrow("has not started");

    const attempt = { cursor: null, signal: new AbortController().signal };
    const handlers = { open: vi.fn(), message: vi.fn() };
    await backend.transport(attempt, handlers);
    await backend.transport(attempt, handlers);
    expect(wasm.create).toHaveBeenCalledOnce();
    expect(transport).toHaveBeenCalledWith(attempt, handlers);
    await backend.notebook("n1").edit([], { idempotencyKey: "edit-1" });
    expect(edit).toHaveBeenCalledWith("n1", [], { idempotencyKey: "edit-1" });
    await backend.notebook("n2").save({ idempotencyKey: "save-1" });
    expect(save).toHaveBeenCalledWith("n2", { idempotencyKey: "save-1" });
  });

  it("stops following WASM when the worker does not start", async () => {
    wasm.enabled = true;
    wasm.create.mockRejectedValue(new Error("Initialization failed"));
    await expect(
      createEditorBackend(options).transport(
        { cursor: null, signal: new AbortController().signal },
        { open: vi.fn(), message: vi.fn() },
      ),
    ).rejects.toBeInstanceOf(StreamStopped);
  });
});

describe("the session backend's startup", () => {
  it.each([true, false])(
    "rechecks health after failed startup (healthy: %s)",
    async (healthy) => {
      const opened = sockets();
      const waitUntilReady = vi
        .fn()
        .mockRejectedValue(new Error("Startup gave up"));
      const checkHealth = vi.fn().mockResolvedValue(healthy);
      const store = createStore();
      const client = createNotebookReplica(store);
      onTestFinished(
        client.connect(
          createEditorBackend({ ...options, waitUntilReady, checkHealth }),
          { onNotification: vi.fn() },
        ),
      );
      await vi.waitFor(() =>
        expect(store.get(client.connectionAtom).state).toBe(
          ConnectionState.CLOSED,
        ),
      );

      await client.reconnect();
      await vi.waitFor(() => expect(opened).toHaveLength(healthy ? 1 : 0));
      expect({
        healthChecks: checkHealth.mock.calls.length,
        startupWaits: waitUntilReady.mock.calls.length,
        state: store.get(client.connectionAtom).state,
      }).toEqual({
        healthChecks: 1,
        startupWaits: 1,
        state: healthy ? ConnectionState.CONNECTING : ConnectionState.CLOSED,
      });
    },
  );

  it("shares one startup wait across connections", async () => {
    const opened = sockets();
    const ready = new Deferred<void>();
    const waitUntilReady = vi.fn(() => ready.promise);
    const backend = createEditorBackend({ ...options, waitUntilReady });
    const client = createNotebookReplica(createStore());
    // Strict Mode connects, disconnects, and connects again.
    client.connect(backend, { onNotification: vi.fn() })();
    onTestFinished(client.connect(backend, { onNotification: vi.fn() }));
    await Promise.resolve();
    expect(opened).toEqual([]);

    ready.resolve();
    await vi.waitFor(() => expect(opened).toHaveLength(1));
    expect(waitUntilReady).toHaveBeenCalledOnce();
  });

  it("opens nothing for a connection that ended during startup", async () => {
    const opened = sockets();
    const ready = new Deferred<void>();
    const store = createStore();
    const client = createNotebookReplica(store);
    const disconnect = client.connect(
      createEditorBackend({ ...options, waitUntilReady: () => ready.promise }),
      { onNotification: vi.fn() },
    );
    expect(store.get(client.connectionAtom)).toEqual({
      state: ConnectionState.CONNECTING,
    });
    disconnect();
    ready.resolve();
    await ready.promise;
    await Promise.resolve();
    expect(opened).toEqual([]);
    expect(store.get(client.connectionAtom)).toEqual({
      state: ConnectionState.NOT_STARTED,
    });
  });
});
