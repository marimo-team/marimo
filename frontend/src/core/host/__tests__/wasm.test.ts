/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookEvents, StreamStopped } from "@marimo-team/client";
import { afterEach, assert, describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { createWasmNotebookBackend, type WasmNotebookBridge } from "../wasm";
import { fixtureEvents } from "./fixtures";

const streams: NotebookEvents[] = [];
afterEach(async () => {
  for (const stream of streams.splice(0)) {
    stream.close();
    await stream.closed.catch(() => undefined);
  }
});

function worker() {
  const frames = fixtureEvents("notebook-events.sse");
  const document = frames.find((event) => event.event === "document")?.data
    .document;
  assert(document);
  const listeners = new Set<(event: unknown) => void>();
  const reply = { ok: true, status: 200, data: { document, cells: {} } };
  const wire = { status: 200, body: reply.data };
  const bridge = {
    notebookId: "n1",
    subscribe: vi.fn(
      async (_cursor: string | null, emit: (event: unknown) => void) => {
        listeners.add(emit);
        frames.forEach(emit);
        return () => {
          listeners.delete(emit);
        };
      },
    ),
    call: vi.fn<WasmNotebookBridge["call"]>().mockResolvedValue(wire),
  };
  return { bridge, listeners, reply, wire };
}

async function follow(bridge: WasmNotebookBridge) {
  const stream = new NotebookEvents(
    createWasmNotebookBackend(bridge).transport,
  );
  streams.push(stream);
  const ready = new Deferred<void>();
  stream.subscribe((event) => {
    if (event.event === "ready") {
      ready.resolve();
    }
  }, ready.reject);
  await ready.promise;
  return stream;
}

describe("WASM notebook backend", () => {
  it("follows independent readers and releases each subscription on close", async () => {
    const { bridge, listeners } = worker();
    const first = await follow(bridge);
    const second = await follow(bridge);
    expect(listeners.size).toBe(2);
    expect(second.status).toBe("connected");
    first.close();
    await first.closed;
    expect(listeners.size).toBe(1);
    second.close();
    await second.closed;
    expect(listeners.size).toBe(0);
  });

  it("closes during startup and releases the late subscription", async () => {
    const { bridge } = worker();
    const pending = new Deferred<() => void>();
    bridge.subscribe.mockReturnValue(pending.promise);
    const controller = new AbortController();
    const done = createWasmNotebookBackend(bridge).transport(
      { cursor: "previous-4", signal: controller.signal },
      { open: vi.fn(), message: vi.fn() },
    );
    expect(bridge.subscribe).toHaveBeenCalledWith(
      "previous-4",
      expect.any(Function),
    );
    controller.abort();
    await done;
    const close = vi.fn();
    pending.resolve(close);
    await vi.waitFor(() => expect(close).toHaveBeenCalledOnce());
  });

  it("stops on worker initialization failure", async () => {
    const { bridge } = worker();
    bridge.subscribe.mockRejectedValue(new Error("Initialization failed"));
    await expect(
      createWasmNotebookBackend(bridge).transport(
        { cursor: null, signal: new AbortController().signal },
        { open: vi.fn(), message: vi.fn() },
      ),
    ).rejects.toBeInstanceOf(StreamStopped);
  });

  it("refuses commands for any notebook but the worker's", () => {
    const { bridge } = worker();
    expect(() => createWasmNotebookBackend(bridge).notebook("n2")).toThrow(
      "serves notebook n1, not n2",
    );
    expect(bridge.call).not.toHaveBeenCalled();
  });

  it("sends edits as calls with the retry key and validates replies", async () => {
    const { bridge, reply } = worker();
    const backend = createWasmNotebookBackend(bridge);
    expect(
      await backend.notebook("n1").edit([], { idempotencyKey: "edit-7" }),
    ).toEqual(reply);
    expect(bridge.call).toHaveBeenCalledWith({
      operation: "notebook.edit",
      params: { notebook_id: "n1" },
      headers: { "idempotency-key": "edit-7" },
      body: { changes: [] },
    });
    const problem = {
      type: "tag:marimo.io,2026:host/forbidden",
      title: "Forbidden",
      status: 403,
    };
    bridge.call.mockResolvedValue({ status: 403, body: problem });
    expect(await backend.notebook("n1").edit([])).toEqual({
      ok: false,
      status: 403,
      problem,
    });
    bridge.call.mockResolvedValue({ status: 200, body: {} });
    await expect(backend.notebook("n1").edit([])).rejects.toThrow(
      /Invalid input/,
    );
  });

  it("cancels waiting for an accepted edit and permits retry with the same key", async () => {
    const { bridge, reply, wire } = worker();
    const pending = new Deferred<unknown>();
    bridge.call.mockReturnValue(pending.promise);
    const backend = createWasmNotebookBackend(bridge);
    const controller = new AbortController();
    const editing = backend.notebook("n1").edit([], {
      signal: controller.signal,
      idempotencyKey: "edit-8",
    });
    await vi.waitFor(() => expect(bridge.call).toHaveBeenCalledOnce());
    controller.abort();
    await expect(editing).rejects.toBe(controller.signal.reason);
    pending.resolve(wire);
    expect(
      await backend.notebook("n1").edit([], { idempotencyKey: "edit-8" }),
    ).toEqual(reply);
    expect(bridge.call.mock.calls[0]).toEqual(bridge.call.mock.calls[1]);
    await expect(
      backend.notebook("n1").edit([], { signal: controller.signal }),
    ).rejects.toBe(controller.signal.reason);
    expect(bridge.call).toHaveBeenCalledTimes(2);
  });
});
