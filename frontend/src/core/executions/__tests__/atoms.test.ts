/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import type * as Protocol from "@marimo-team/client/protocol";
import type { CellMessage } from "@/core/kernel/messages";
import type { Executions } from "@/core/notebook/replica";
import {
  acceptRun,
  cellExecutionInputsAtom,
  notebookQueuedOrRunningCountAtom,
  observeCellMessage,
  submitCells,
} from "../atoms";
import { cellExecutionView } from "../select";

const C1 = cellId("c1");
const C2 = cellId("c2");

function run(
  cells: Protocol.CellId[],
  status: Protocol.Run["status"] = "queued",
): Protocol.Run {
  return {
    id: "run-1",
    notebook_id: "n1",
    runtime_id: "r1",
    cells,
    status,
    outcome: status === "completed" ? "succeeded" : null,
    started_at: null,
    completed_at: null,
  };
}

function withRuns(executions: Executions, runs: Protocol.Run[]): Executions {
  return { ...executions, runs: new Map(runs.map((r) => [r.id, r])) };
}

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

describe("acceptRun", () => {
  function statusOf(store: ReturnType<typeof createStore>, id = C1) {
    return cellExecutionView(store.get(cellExecutionInputsAtom), id).status;
  }

  it("withdraws a submission the run completed without planning", () => {
    const store = createStore();
    const replica = MockExecutions.seed(store, []);
    submitCells(store, [C1]);
    acceptRun(store, run([C1]));

    const stream = store.get(replica.executionsAtom);
    store.set(replica.executionsAtom, withRuns(stream, [run([C1], "running")]));
    expect(statusOf(store)).toBe("queued");

    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed")]),
    );
    expect(statusOf(store)).toBe("idle");
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("keeps the submission until the stream has shown the run", () => {
    const store = createStore();
    const replica = MockExecutions.seed(store, []);
    submitCells(store, [C1]);

    // The response lands first; the run event follows.
    acceptRun(store, run([C1]));
    expect(statusOf(store)).toBe("queued");

    const stream = store.get(replica.executionsAtom);
    store.set(replica.executionsAtom, withRuns(stream, [run([C1], "running")]));
    expect(statusOf(store)).toBe("queued");
    store.set(replica.executionsAtom, withRuns(stream, []));
    expect(statusOf(store)).toBe("idle");
  });

  it("withdraws only the cells the run was accepted for", () => {
    const store = createStore();
    const replica = MockExecutions.seed(store, []);
    submitCells(store, [C1, C2]);
    acceptRun(store, run([C1]));

    const stream = store.get(replica.executionsAtom);
    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed")]),
    );

    expect(statusOf(store, C1)).toBe("idle");
    expect(statusOf(store, C2)).toBe("queued");
  });

  it("leaves a request made since the run was accepted", () => {
    const store = createStore();
    const replica = MockExecutions.seed(store, []);
    submitCells(store, [C1]);
    acceptRun(store, run([C1]));

    // The run completes the cell; the user then asks for it again.
    const completed = MockExecutions.inputs([MockExecutions.completed(C1)]);
    store.set(replica.resultsAtom, completed.results);
    store.set(
      replica.executionsAtom,
      withRuns(completed.executions, [run([C1], "running")]),
    );
    submitCells(store, [C1]);
    store.set(
      replica.executionsAtom,
      withRuns(completed.executions, [run([C1], "completed")]),
    );

    expect(statusOf(store)).toBe("queued");
  });

  it("stops following a run once the replica changes", () => {
    const store = createStore();
    const replica = MockExecutions.seed(store, []);
    submitCells(store, [C1]);
    acceptRun(store, run([C1]));

    MockExecutions.seed(store, []);
    submitCells(store, [C1]);
    const stream = store.get(replica.executionsAtom);
    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed")]),
    );

    expect(statusOf(store)).toBe("queued");
  });
});
