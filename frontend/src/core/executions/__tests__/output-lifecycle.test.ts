/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import type { NotebookTransport } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { createStore } from "jotai";
import { describe, expect, it, onTestFinished, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId, runId } from "@/__tests__/branded";
import { createNotebookReplica } from "@/core/notebook/replica";
import {
  fakeBackend,
  fixtureMessages,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { Deferred } from "@/utils/Deferred";
import {
  acceptRun,
  cellExecutionInputsAtom,
  cellOutputAtom,
  clearCellOutputs,
  isCurrent,
  requestRun,
  withdrawRequest,
} from "../atoms";
import { scratchOutputView } from "../output";

const C1 = cellId("c1");
const text = (data: string): Protocol.Media => ({
  mimetype: "text/plain",
  data,
});

type Record = Protocol.Execution | Protocol.Output;

async function setup() {
  interface Attempt {
    message: Parameters<NotebookTransport>[1]["message"];
    drop(): void;
  }
  let opened = new Deferred<Attempt>();
  const backend = fakeBackend({
    transport: ({ signal }, handlers) =>
      new Promise<void>((resolve) => {
        handlers.open();
        opened.resolve({ message: handlers.message, drop: resolve });
        signal.addEventListener("abort", () => resolve(), { once: true });
      }),
  });
  const store = createStore();
  const replica = createNotebookReplica(store);
  store.set(activeNotebookReplicaAtom, replica);
  const disconnect = replica.connect(backend, { onNotification: vi.fn() });
  onTestFinished(disconnect);
  let attempt = await opened.promise;
  const message: Attempt["message"] = (frame) => attempt.message(frame);
  const reconnect = async () => {
    opened = new Deferred<Attempt>();
    attempt.drop();
    await vi.advanceTimersByTimeAsync(2000);
    attempt = await opened.promise;
  };
  let cursor = 100;
  const emit = (record: Record) =>
    message(
      "execution_id" in record
        ? { event: "output", id: String(++cursor), data: { output: record } }
        : {
            event: "execution",
            id: String(++cursor),
            data: { execution: record },
          },
    );
  const remove = (execution: Protocol.Execution) =>
    message({
      event: "execution.removed",
      id: String(++cursor),
      data: { id: execution.id, time: MockExecutions.T1 },
    });
  const snapshot = (records: readonly Record[], notebookId = "n1") => {
    message({ event: "reset", data: {} });
    fixtureMessages("notebook-events.sse")
      .filter(({ event }) => ["notebook", "document", "cell"].includes(event))
      .forEach((event) =>
        message(
          JSON.parse(
            JSON.stringify(event).replaceAll(
              '"n1"',
              JSON.stringify(notebookId),
            ),
          ),
        ),
      );
    records.forEach(emit);
    message({ event: "ready", id: String(++cursor), data: {} });
  };
  return {
    store,
    replica,
    emit,
    remove,
    snapshot,
    message,
    reconnect,
  };
}

describe("output lifetime", () => {
  it.each(["replay", "snapshot", "in-place reset"] as const)(
    "expires editor marks on %s for the same notebook",
    async (recovery) => {
      vi.useFakeTimers();
      onTestFinished(() => {
        vi.useRealTimers();
      });
      const { store, snapshot, message, reconnect } = await setup();
      const result = MockExecutions.shown(C1, text("A"));
      snapshot(result);
      const run: Protocol.RunOutput = {
        id: runId("missed"),
        notebook_id: "n1",
        runtime_id: "r1",
        origin: { kind: "cells", cell_ids: [C1] },
        created_at: "2026-10-01T09:20:00Z",
        state: { status: "queued" },
      };
      const pending = requestRun(store, [C1])!;
      acceptRun(store, pending, run);
      const late = requestRun(store, [C1])!;
      clearCellOutputs(store, [C1]);
      expect(store.get(cellOutputAtom(C1))).toBeNull();

      if (recovery !== "in-place reset") {
        await reconnect();
      }
      if (recovery !== "replay") {
        snapshot(result);
      } else {
        message({ event: "ready", id: "120", data: {} });
      }
      const { requested } = store.get(cellExecutionInputsAtom);
      expect([...requested]).toEqual([]);
      expect(store.get(cellOutputAtom(C1))?.data).toBe("A");
      expect(isCurrent(store, late)).toBe(false);

      const current = requestRun(store, [C1])!;
      acceptRun(store, late, run);
      withdrawRequest(store, pending);
      expect(isCurrent(store, current)).toBe(true);
      expect([...store.get(cellExecutionInputsAtom).requested]).toEqual([C1]);
      withdrawRequest(store, current);
      expect([...store.get(cellExecutionInputsAtom).requested]).toEqual([]);
    },
  );

  it("keeps a changed display visible after its execution retires", async () => {
    const { store, replica, emit, remove, snapshot } = await setup();
    const [result, output] = MockExecutions.shown(C1, text("A"));
    snapshot([result, output]);
    clearCellOutputs(store, [C1]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();

    emit(MockExecutions.output(result, text("B")));
    emit(output);
    // No reader needs to observe the intermediate output for it to count.
    snapshot([result, output]);
    remove(result);
    const running = MockExecutions.running(C1);
    emit(running);
    expect(store.get(replica.executionsAtom).executions.has(result.id)).toBe(
      false,
    );
    expect(store.get(cellOutputAtom(C1))?.data).toBe("A");
    snapshot([running]);
    expect(store.get(cellOutputAtom(C1))?.data).toBe("A");
  });

  it("keeps a clear through completion and retirement, until a newer result", async () => {
    const { store, emit, remove, snapshot } = await setup();
    const running = MockExecutions.running(C1);
    snapshot([running]);
    emit(MockExecutions.output(running, text("A")));
    clearCellOutputs(store, [C1]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();

    const completed = { ...MockExecutions.completed(C1), id: running.id };
    emit(completed);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    remove(completed);
    const next = MockExecutions.running(C1);
    emit(next);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    emit(MockExecutions.output(next, text("A")));
    expect(store.get(cellOutputAtom(C1))?.data).toBe("A");
  });
  it("keeps the scratch display after its execution expires", async () => {
    const { store, replica, emit, remove, snapshot } = await setup();
    const [scratch, shown] = MockExecutions.shown(null, text("scratch result"));
    snapshot([scratch, shown]);
    const before = scratchOutputView(store.get(replica.executionsAtom));
    expect(before?.data).toBe("scratch result");
    remove(scratch);
    expect(store.get(replica.executionsAtom).executions.size).toBe(0);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toEqual(
      before,
    );
    snapshot([]);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toEqual(
      before,
    );

    const started_at = "2026-10-01T09:22:00Z";
    const next = MockExecutions.execution(null, {
      status: "running",
      started_at,
    });
    emit(next);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toEqual(
      before,
    );
    emit(MockExecutions.output(next, text("next")));
    expect(scratchOutputView(store.get(replica.executionsAtom))?.data).toBe(
      "next",
    );
    emit({
      ...next,
      state: {
        status: "completed",
        started_at,
        completed_at: "2026-10-01T09:22:01Z",
        outcome: { kind: "succeeded" },
        depends_on: {},
      },
    });
    remove(next);
    expect(scratchOutputView(store.get(replica.executionsAtom))?.data).toBe(
      "next",
    );
    snapshot([], "n2");
    expect(scratchOutputView(store.get(replica.executionsAtom))).toBeNull();
  });

  it("keeps scratch output cleared when an empty execution expires", async () => {
    const { store, replica, emit, remove, snapshot } = await setup();
    snapshot(MockExecutions.shown(null, text("old")));
    const cleared = MockExecutions.execution(null, {
      status: "completed",
      started_at: MockExecutions.T0,
      completed_at: "2026-10-01T09:22:00Z",
      outcome: { kind: "succeeded" },
      depends_on: {},
    });
    emit(cleared);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toBeNull();
    remove(cleared);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toBeNull();
    snapshot([]);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toBeNull();
  });
});
