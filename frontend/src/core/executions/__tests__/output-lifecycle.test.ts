/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import type { NotebookTransport } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { createStore } from "jotai";
import { describe, expect, it, onTestFinished, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
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
  setCellBlocked,
  requestRun,
  withdrawRequest,
} from "../atoms";
import { scratchOutputView } from "../output";

const C1 = cellId("c1");
const value = (data: string): Protocol.ValueOutcome => ({
  kind: "value",
  display: { mimetype: "text/plain", data },
});

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
  const emit = (execution: Protocol.Execution) =>
    message({ event: "execution", id: String(++cursor), data: { execution } });
  const remove = (execution: Protocol.Execution) =>
    message({
      event: "execution.removed",
      id: String(++cursor),
      data: { id: execution.id, time: MockExecutions.T1 },
    });
  const snapshot = (records: Protocol.Execution[], notebookId = "n1") => {
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
      const result = MockExecutions.completed(C1, value("A"));
      snapshot([result]);
      const run: Protocol.Run = {
        id: "missed",
        notebook_id: "n1",
        runtime_id: "r1",
        origin: { kind: "cells", cell_ids: [C1] },
        state: { status: "queued" },
      };
      const pending = requestRun(store, [C1])!;
      acceptRun(store, pending, run);
      const late = requestRun(store, [C1])!;
      setCellBlocked(store, C1, true);
      clearCellOutputs(store, [C1]);
      expect(store.get(cellExecutionInputsAtom).blocked.has(C1)).toBe(true);
      expect(store.get(cellOutputAtom(C1))).toBeNull();

      if (recovery !== "in-place reset") {
        await reconnect();
      }
      if (recovery !== "replay") {
        snapshot([result]);
      } else {
        message({ event: "ready", id: "120", data: {} });
      }
      const { requested, blocked } = store.get(cellExecutionInputsAtom);
      expect([...requested]).toEqual([]);
      expect([...blocked]).toEqual([]);
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
    const result = MockExecutions.completed(C1, value("A"));
    snapshot([result]);
    clearCellOutputs(store, [C1]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();

    const shown = (data: string) => ({
      ...MockExecutions.completed(C1, value(data)),
      id: result.id,
    });
    emit(shown("B"));
    emit(shown("A"));
    // No reader needs to observe the intermediate display for it to count.
    snapshot([shown("A")]);
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
    emit({ ...MockExecutions.running(C1, value("A")), id: running.id });
    clearCellOutputs(store, [C1]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();

    const completed = {
      ...MockExecutions.completed(C1, value("A")),
      id: running.id,
    };
    emit(completed);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    remove(completed);
    const next = MockExecutions.running(C1);
    emit(next);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    emit({ ...MockExecutions.running(C1, value("A")), id: next.id });
    expect(store.get(cellOutputAtom(C1))?.data).toBe("A");
  });
  it("keeps the scratch display after its execution expires", async () => {
    const { store, replica, emit, remove, snapshot } = await setup();
    const scratch = MockExecutions.completed(null, value("scratch result"));
    snapshot([scratch]);
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
      value: null,
    });
    emit(next);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toEqual(
      before,
    );
    emit({
      ...next,
      state: { status: "running", started_at, value: value("next") },
    });
    expect(scratchOutputView(store.get(replica.executionsAtom))?.data).toBe(
      "next",
    );
    emit({
      ...next,
      state: {
        status: "completed",
        started_at,
        completed_at: "2026-10-01T09:22:01Z",
        outcome: value("next"),
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
    snapshot([MockExecutions.completed(null, value("old"))]);
    const cleared = MockExecutions.execution(null, {
      status: "completed",
      started_at: MockExecutions.T0,
      completed_at: "2026-10-01T09:22:00Z",
      outcome: { kind: "value", display: null },
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
