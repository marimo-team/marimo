/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { cellOutputAtom } from "@/core/executions";
import { clearAllCellOutputsAtom, clearCellOutputAtom } from "../actions";
import { notebookAtom } from "../cells";
import type { ConsoleOutputMessage } from "../types";

const A = cellId("a");
const B = cellId("b");

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
        [A]: { consoleOutputs: [STDOUT, PROMPT] },
        [B]: { consoleOutputs: [STDOUT] },
      },
    }),
  );
  MockExecutions.seed(store, [
    MockExecutions.shown(A, { mimetype: "text/plain", data: "a" }),
    MockExecutions.shown(B, { mimetype: "text/plain", data: "b" }),
  ]);
  return store;
}

describe("clearCellOutputAtom", () => {
  it("hides the host's output and the console, keeping an unanswered prompt", () => {
    const store = setup();
    store.set(clearCellOutputAtom, { cellId: A });

    expect(store.get(cellOutputAtom(A))).toBeNull();
    expect(store.get(notebookAtom).cellRuntime[A].consoleOutputs).toEqual([
      PROMPT,
    ]);
    expect(store.get(cellOutputAtom(B))?.data).toBe("b");
    expect(store.get(notebookAtom).cellRuntime[B].consoleOutputs).toEqual([
      STDOUT,
    ]);
  });
});

describe("clearAllCellOutputsAtom", () => {
  it("clears every cell", () => {
    const store = setup();
    store.set(clearAllCellOutputsAtom);

    expect(store.get(cellOutputAtom(A))).toBeNull();
    expect(store.get(cellOutputAtom(B))).toBeNull();
    const { cellRuntime } = store.get(notebookAtom);
    expect(cellRuntime[A].consoleOutputs).toEqual([PROMPT]);
    expect(cellRuntime[B].consoleOutputs).toEqual([]);
  });
});
