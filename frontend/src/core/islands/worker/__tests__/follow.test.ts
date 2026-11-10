/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, onTestFinished, vi } from "vitest";
import { fixtureMessages } from "@/core/notebook/replica/__tests__/fixtures";
import { followIsland } from "../follow";

async function setup() {
  let receive!: (raw: string) => void;
  const notebook = {
    id: "n1",
    subscribe: vi.fn(async (_id, _cursor, emit) => {
      receive = emit;
    }),
    call: vi.fn<(call: string) => Promise<string>>(async () =>
      JSON.stringify({
        status: 202,
        body: {
          id: "run-1",
          notebook_id: "n1",
          runtime_id: "r1",
          cells: ["c1", "c3", "k7f2"],
          status: "queued",
          outcome: null,
          started_at: null,
          completed_at: null,
        },
      }),
    ),
    unsubscribe: vi.fn(),
    destroy: vi.fn(),
  };
  const emit = vi.fn();
  const onError = vi.fn();
  const lifetime = new AbortController();
  onTestFinished(() => lifetime.abort());
  await followIsland({
    bridge: { notebook },
    sessionGeneration: 1,
    signal: lifetime.signal,
    emit,
    onError,
  });
  const send = (event: unknown) => receive(JSON.stringify(event));
  const snapshot = () => {
    for (const event of fixtureMessages("notebook-events.sse")) {
      if (["run", "execution", "console"].includes(event.event)) {
        continue;
      }
      send(event);
      if (event.event === "ready") {
        break;
      }
    }
  };
  return { notebook, send, snapshot, emit, onError, lifetime };
}

describe("island host startup", () => {
  it("forwards the snapshot before submitting one run for the document", async () => {
    const { notebook, send, snapshot, emit, onError } = await setup();
    expect(notebook.call).not.toHaveBeenCalled();
    snapshot();
    await vi.waitFor(() => expect(notebook.call).toHaveBeenCalledOnce());
    expect(JSON.parse(notebook.call.mock.calls[0][0])).toEqual({
      operation: "runtime.run",
      params: { notebook_id: "n1" },
      headers: { "idempotency-key": "startup:n1:r1" },
      body: { cells: [{ id: "c1" }, { id: "c3" }, { id: "k7f2" }] },
    });
    expect(JSON.parse(emit.mock.calls.at(-1)![0])).toMatchObject({
      event: "ready",
    });
    snapshot();
    send({ event: "marimo", data: { marimo: { op: "completed-run" } } });
    expect(notebook.call).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("waits for the kernel to run after the snapshot is ready", async () => {
    const { notebook, send } = await setup();
    let running: unknown;
    for (const event of fixtureMessages("notebook-events.sse")) {
      if (event.event === "runtime") {
        running = event;
        continue;
      }
      if (["run", "execution", "console"].includes(event.event)) {
        continue;
      }
      send(event);
      if (event.event === "ready") {
        break;
      }
    }
    expect(notebook.call).not.toHaveBeenCalled();
    send(running);
    await vi.waitFor(() => expect(notebook.call).toHaveBeenCalledOnce());
  });

  it("closes its replica with the session and cannot run from a late snapshot", async () => {
    const { notebook, snapshot, lifetime } = await setup();
    lifetime.abort();
    snapshot();
    await Promise.resolve();
    expect(notebook.unsubscribe).toHaveBeenCalledExactlyOnceWith("island-1");
    expect(notebook.call).not.toHaveBeenCalled();
  });

  it("reports a refused run without resubmitting it", async () => {
    const { notebook, snapshot, onError } = await setup();
    notebook.call.mockResolvedValue(
      JSON.stringify({
        status: 409,
        body: { type: "conflict", title: "Runtime stopped", status: 409 },
      }),
    );
    snapshot();
    await vi.waitFor(() => expect(onError).toHaveBeenCalledOnce());
    snapshot();
    expect(notebook.call).toHaveBeenCalledOnce();
  });
});
