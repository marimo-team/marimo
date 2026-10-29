/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookEvents, StreamStopped } from "@marimo-team/client";
import { afterEach, assert, describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { createWasmNotebookBackend, type WasmNotebookBridge } from "../wasm";
import { fixtureEvents } from "../../notebook/replica/__tests__/fixtures";

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
      controller.signal,
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

  it.each(["edit", "save"] as const)(
    "sends %s calls with the retry key and validates replies",
    async (operation) => {
      const { bridge, reply } = worker();
      const notebook = createWasmNotebookBackend(bridge).notebook("n1");
      const command =
        operation === "edit"
          ? notebook.edit.bind(notebook, [])
          : notebook.save.bind(notebook);
      expect(await command({ idempotencyKey: `${operation}-7` })).toEqual(
        reply,
      );
      expect(bridge.call).toHaveBeenCalledWith({
        operation: `notebook.${operation}`,
        params: { notebook_id: "n1" },
        headers: { "idempotency-key": `${operation}-7` },
        body: operation === "edit" ? { changes: [] } : {},
      });
      const problem = {
        type: "tag:marimo.io,2026:host/forbidden",
        title: "Forbidden",
        status: 403,
      };
      bridge.call.mockResolvedValue({ status: 403, body: problem });
      expect(await command()).toEqual({
        ok: false,
        status: 403,
        problem,
      });
      bridge.call.mockResolvedValue({ status: 200, body: {} });
      await expect(command()).rejects.toThrow(/Invalid input/);
    },
  );

  it.each(["edit", "save"] as const)(
    "cancels waiting for an accepted %s and permits retry with the same key",
    async (operation) => {
      const { bridge, reply, wire } = worker();
      const pending = new Deferred<unknown>();
      bridge.call.mockReturnValue(pending.promise);
      const notebook = createWasmNotebookBackend(bridge).notebook("n1");
      const command =
        operation === "edit"
          ? notebook.edit.bind(notebook, [])
          : notebook.save.bind(notebook);
      const controller = new AbortController();
      const pendingCommand = command({
        signal: controller.signal,
        idempotencyKey: `${operation}-8`,
      });
      await vi.waitFor(() => expect(bridge.call).toHaveBeenCalledOnce());
      controller.abort();
      await expect(pendingCommand).rejects.toBe(controller.signal.reason);
      pending.resolve(wire);
      expect(await command({ idempotencyKey: `${operation}-8` })).toEqual(
        reply,
      );
      expect(bridge.call.mock.calls[0]).toEqual(bridge.call.mock.calls[1]);
      await expect(command({ signal: controller.signal })).rejects.toBe(
        controller.signal.reason,
      );
      expect(bridge.call).toHaveBeenCalledTimes(2);
    },
  );
});
