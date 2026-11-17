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
import { cellOutputAtom, clearCellOutputs } from "../atoms";
import { scratchOutputView } from "../output";

const C1 = cellId("c1");
const value = (data: string): Protocol.Outcome => ({
  kind: "value",
  display: { mimetype: "text/plain", data },
});

async function setup() {
  const connected = new Deferred<Parameters<NotebookTransport>[1]>();
  const backend = fakeBackend({
    transport: ({ signal }, handlers) =>
      new Promise<void>((resolve) => {
        handlers.open();
        connected.resolve(handlers);
        signal.addEventListener("abort", () => resolve(), { once: true });
      }),
  });
  const store = createStore();
  const replica = createNotebookReplica(store);
  store.set(activeNotebookReplicaAtom, replica);
  const disconnect = replica.connect(backend, { onNotification: vi.fn() });
  onTestFinished(disconnect);
  const { message } = await connected.promise;
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
  return { store, replica, emit, remove, snapshot, message, disconnect };
}

describe("output lifetime", () => {
  it("keeps a cleared output hidden through reset and disconnect", async () => {
    const { store, snapshot, message, disconnect } = await setup();
    const result = MockExecutions.completed(C1, { outcome: value("A") });
    snapshot([result]);
    clearCellOutputs(store, [C1]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();

    message({ event: "reset", data: {} });
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    snapshot([result]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    disconnect();
    expect(store.get(cellOutputAtom(C1))).toBeNull();
  });
  it("keeps a changed display visible after its execution retires", async () => {
    const { store, replica, emit, remove, snapshot } = await setup();
    const result = MockExecutions.completed(C1, { outcome: value("A") });
    snapshot([result]);
    clearCellOutputs(store, [C1]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();

    emit({ ...result, outcome: value("B") });
    emit({ ...result, outcome: value("A") });
    // No reader needs to observe the intermediate display for it to count.
    snapshot([{ ...result, outcome: value("A") }]);
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
    emit({ ...running, outcome: value("A") });
    clearCellOutputs(store, [C1]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();

    const completed = {
      ...running,
      status: "completed" as const,
      completed_at: MockExecutions.T1,
      outcome: value("A"),
    };
    emit(completed);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    snapshot([completed]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    remove(completed);
    const next = MockExecutions.running(C1);
    emit(next);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    snapshot([next]);
    expect(store.get(cellOutputAtom(C1))).toBeNull();
    emit({ ...next, outcome: value("A") });
    expect(store.get(cellOutputAtom(C1))?.data).toBe("A");
  });
  it("keeps the scratch display after its execution expires", async () => {
    const { store, replica, emit, remove, snapshot } = await setup();
    const scratch = MockExecutions.completed("scratch", {
      cell_id: null,
      outcome: value("scratch result"),
    });
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

    const next = {
      ...MockExecutions.running("scratch"),
      cell_id: null,
      started_at: "2026-10-01T09:22:00Z",
    };
    emit(next);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toEqual(
      before,
    );
    emit({ ...next, outcome: value("next") });
    expect(scratchOutputView(store.get(replica.executionsAtom))?.data).toBe(
      "next",
    );
    emit({
      ...next,
      status: "completed",
      completed_at: "2026-10-01T09:22:01Z",
      outcome: value("next"),
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
    snapshot([
      MockExecutions.completed("scratch", {
        cell_id: null,
        outcome: value("old"),
      }),
    ]);
    const cleared = MockExecutions.completed("scratch", {
      cell_id: null,
      outcome: { kind: "value", display: null },
      completed_at: "2026-10-01T09:22:00Z",
    });
    emit(cleared);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toBeNull();
    remove(cleared);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toBeNull();
    snapshot([]);
    expect(scratchOutputView(store.get(replica.executionsAtom))).toBeNull();
  });
});
