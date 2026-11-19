/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { cellOutputAtom } from "@/core/executions";
import {
  cell,
  document,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { executions } from "@/core/notebook/replica/resources/executions";
import { clearAllCellOutputsAtom, clearCellOutputAtom } from "../actions";
import { cellRuntimeAtom, notebookAtom } from "../cells";
import { EMBEDDED } from "../session";
import type { ConsoleOutputMessage } from "../types";

const A = cellId("a");
const B = cellId("b");
const DOCUMENT = withCells(document(), {
  c1: null,
  c2: null,
  [A]: cell(A, ""),
  [B]: cell(B, ""),
});

const STDOUT: ConsoleOutputMessage = {
  channel: "stdout",
  mimetype: "text/plain",
  data: "printed",
  timestamp: 0,
  id: 1,
};
const PROMPT: ConsoleOutputMessage = {
  channel: "stdin",
  mimetype: "text/plain",
  data: "name?",
  timestamp: 0,
  id: 2,
};

function setup() {
  const store = createStore();
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [A]: {}, [B]: {} },
      cellRuntime: {
        [A]: { embeddedConsole: [STDOUT, PROMPT] },
        [B]: { embeddedConsole: [STDOUT] },
      },
    }),
  );
  MockExecutions.seed(
    store,
    [
      MockExecutions.shown(
        A,
        { mimetype: "text/plain", data: "a" },
        { runtime_id: EMBEDDED },
      ),
      MockExecutions.shown(
        B,
        { mimetype: "text/plain", data: "b" },
        { runtime_id: EMBEDDED },
      ),
    ],
    null,
    DOCUMENT,
  );
  return store;
}

describe("clearCellOutputAtom", () => {
  it("hides the host's output and the console, keeping an unanswered prompt", () => {
    const store = setup();
    store.set(clearCellOutputAtom, { cellId: A });

    expect(store.get(cellOutputAtom(A))).toBeNull();
    expect(store.get(cellRuntimeAtom(A)).consoleOutputs).toEqual([PROMPT]);
    expect(store.get(cellOutputAtom(B))?.data).toBe("b");
    expect(store.get(cellRuntimeAtom(B)).consoleOutputs).toMatchObject([
      { channel: "stdout", data: "printed" },
    ]);
  });
});

describe("clearing a running cell", () => {
  it("hides what it shows until it shows something new", () => {
    const store = createStore();
    store.set(
      notebookAtom,
      MockNotebook.notebookState({ cellData: { [A]: {} } }),
    );
    const running = MockExecutions.shown(
      A,
      { mimetype: "text/plain", data: "so far" },
      { status: "running", completed_at: null },
    );
    const replica = MockExecutions.seed(store, [running], null, DOCUMENT);
    store.set(clearCellOutputAtom, { cellId: A });
    expect(store.get(cellOutputAtom(A))).toBeNull();

    store.set(replica.executionsAtom, (state) =>
      executions.on.execution!(
        state,
        {
          event: "execution",
          id: "more",
          data: {
            execution: {
              ...running,
              outcome: {
                kind: "value",
                display: { mimetype: "text/plain", data: "more" },
              },
            },
          },
        },
        { phase: "live" },
      ),
    );
    expect(store.get(cellOutputAtom(A))?.data).toBe("more");

    store.set(replica.executionsAtom, (state) =>
      executions.on.execution!(
        state,
        {
          event: "execution",
          id: "again",
          data: { execution: { ...running, outcome: running.outcome } },
        },
        { phase: "live" },
      ),
    );
    expect(store.get(cellOutputAtom(A))?.data).toBe("so far");
  });
});

describe("clearAllCellOutputsAtom", () => {
  it("clears every cell", () => {
    const store = setup();
    const before = store.get(notebookAtom);
    Object.freeze(before.cellRuntime);
    Object.values(before.cellRuntime).forEach(Object.freeze);
    store.set(clearAllCellOutputsAtom);

    expect(store.get(cellOutputAtom(A))).toBeNull();
    expect(store.get(cellOutputAtom(B))).toBeNull();
    const { cellRuntime } = store.get(notebookAtom);
    expect(cellRuntime[A].embeddedConsole).toEqual([PROMPT]);
    expect(cellRuntime[B].embeddedConsole).toEqual([]);
    expect(before.cellRuntime[A].embeddedConsole).toEqual([STDOUT, PROMPT]);
    expect(before.cellRuntime[B].embeddedConsole).toEqual([STDOUT]);
  });
});
