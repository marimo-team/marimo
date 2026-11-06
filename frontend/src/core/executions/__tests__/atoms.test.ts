/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import type { CellMessage } from "@/core/kernel/messages";
import {
  cellExecutionInputsAtom,
  notebookQueuedOrRunningCountAtom,
  observeCellMessage,
  submitCells,
} from "../atoms";
import { cellExecutionView } from "../select";

const C1 = cellId("c1");

function cellOp(status: CellMessage["status"]): CellMessage {
  return {
    cell_id: C1,
    output: null,
    console: null,
    status,
    timestamp: 1,
  };
}

describe("observeCellMessage", () => {
  it("withdraws a submission once the kernel reports the cell blocked", () => {
    const store = createStore();
    MockExecutions.seed(store, []);
    submitCells(store, [C1]);
    expect(
      cellExecutionView(store.get(cellExecutionInputsAtom), C1).status,
    ).toBe("queued");

    observeCellMessage(store, cellOp("disabled-transitively"));

    const view = cellExecutionView(store.get(cellExecutionInputsAtom), C1);
    expect(view.status).toBe("idle");
    expect(view.blocked).toBe(true);
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("forgets submissions and blocked cells with the replica they were made for", () => {
    const store = createStore();
    MockExecutions.seed(store, []);
    submitCells(store, [C1]);
    observeCellMessage(store, cellOp("disabled-transitively"));

    MockExecutions.seed(store, []);

    const view = cellExecutionView(store.get(cellExecutionInputsAtom), C1);
    expect(view.status).toBe("idle");
    expect(view.blocked).toBe(false);
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("keeps a submission while the cell is merely queued", () => {
    const store = createStore();
    MockExecutions.seed(store, []);
    submitCells(store, [C1]);

    observeCellMessage(store, cellOp("queued"));

    expect(
      cellExecutionView(store.get(cellExecutionInputsAtom), C1).status,
    ).toBe("queued");
  });

  it("forgets acknowledged submissions and blocked cells when the replica follows a new notebook", () => {
    const store = createStore();
    const replica = MockExecutions.seed(store, []);
    submitCells(store, [C1]);
    observeCellMessage(store, {
      ...cellOp("disabled-transitively"),
      cell_id: cellId("c2"),
    });

    const completed = MockExecutions.inputs([MockExecutions.completed(C1)]);
    store.set(replica.executionsAtom, completed.executions);
    store.set(replica.resultsAtom, completed.results);
    expect(
      cellExecutionView(store.get(cellExecutionInputsAtom), C1).status,
    ).toBe("idle");

    const empty = MockExecutions.inputs([]);
    store.set(replica.executionsAtom, empty.executions);
    store.set(replica.resultsAtom, empty.results);
    store.set(replica.notebookAtom, {
      ...store.get(replica.notebookAtom),
      id: "n2",
    });

    expect(store.get(cellExecutionInputsAtom)).toEqual(empty);
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });
});
