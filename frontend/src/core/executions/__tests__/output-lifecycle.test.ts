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
});
