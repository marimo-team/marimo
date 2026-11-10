/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import type * as Protocol from "@marimo-team/client/protocol";
import type { CellMessage } from "@/core/kernel/messages";
import {
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import type { Executions } from "@/core/notebook/replica";
import {
  acceptRun,
  cellExecutionInputsAtom,
  notebookQueuedOrRunningCountAtom,
  observeCellMessage,
  requestRun,
  type RunRequest,
  withdrawRequest,
} from "../atoms";
import { cellExecutionView } from "../select";

const C1 = cellId("c1");
const C2 = cellId("c2");

type Store = ReturnType<typeof createStore>;

function run(
  cells: Protocol.CellId[],
  status: Protocol.Run["status"] = "queued",
  id = "run-1",
): Protocol.Run {
  return {
    id,
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

/** A store whose replica shows the two-cell fixture document. */
function shown() {
  const store = createStore();
  const replica = MockExecutions.seed(store, [], null, documentOf());
  return { store, replica };
}

function request(store: Store, cells: Protocol.CellId[]): RunRequest {
  const made = requestRun(store, cells);
  if (made === null) {
    throw new Error("no notebook is shown");
  }
  return made;
}

function statusOf(store: Store, id = C1) {
  return cellExecutionView(store.get(cellExecutionInputsAtom), id).status;
}

function requested(store: Store) {
  return [...store.get(cellExecutionInputsAtom).requested];
}

describe("requestRun", () => {
  it("reads the cells as queued until the request is withdrawn", () => {
    const { store } = shown();
    const made = request(store, [C1, C2]);
    expect(statusOf(store, C1)).toBe("queued");
    expect(statusOf(store, C2)).toBe("queued");
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(2);

    withdrawRequest(store, made);

    expect(statusOf(store, C1)).toBe("idle");
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("records nothing while no notebook is shown", () => {
    const store = createStore();
    const replica = MockExecutions.seed(store, [], null, documentOf());
    store.set(replica.notebookAtom, null);

    expect(requestRun(store, [C1])).toBeNull();
    expect(statusOf(store)).toBe("idle");
  });

  it("stops showing a requested cell that leaves the document", () => {
    const { store, replica } = shown();
    request(store, [C1]);
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(1);

    store.set(replica.documentAtom, withCells(documentOf(), { c1: null }));

    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("forgets requests and blocked cells with the notebook they were made in", () => {
    const { store, replica } = shown();
    request(store, [C1]);
    observeCellMessage(store, {
      ...cellOp("disabled-transitively"),
      cell_id: C2,
    });

    store.set(replica.notebookAtom, MockExecutions.notebook("n2"));

    expect(requested(store)).toEqual([]);
    expect(statusOf(store)).toBe("idle");
    expect(store.get(cellExecutionInputsAtom).blocked.size).toBe(0);
  });
});

describe("observeCellMessage", () => {
  it("does not show a requested cell as queued once the kernel reports it blocked", () => {
    const { store } = shown();
    request(store, [C1]);
    expect(statusOf(store)).toBe("queued");

    observeCellMessage(store, cellOp("disabled-transitively"));

    const view = cellExecutionView(store.get(cellExecutionInputsAtom), C1);
    expect(view.status).toBe("idle");
    expect(view.blocked).toBe(true);
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("forgets requests and blocked cells with the replica they were made for", () => {
    const { store } = shown();
    request(store, [C1]);
    observeCellMessage(store, cellOp("disabled-transitively"));

    MockExecutions.seed(store, [], null, documentOf());

    const view = cellExecutionView(store.get(cellExecutionInputsAtom), C1);
    expect(view.status).toBe("idle");
    expect(view.blocked).toBe(false);
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("keeps a request while the cell is merely queued", () => {
    const { store } = shown();
    request(store, [C1]);

    observeCellMessage(store, cellOp("queued"));

    expect(statusOf(store)).toBe("queued");
  });
});

describe("acceptRun", () => {
  it("hands the request over to the run once the stream shows it", () => {
    const { store, replica } = shown();
    const made = request(store, [C1]);
    acceptRun(store, made, run([C1]));
    expect(statusOf(store)).toBe("queued");
    expect(requested(store)).toEqual([C1]);

    // The response landed first, and the run event follows.
    const stream = store.get(replica.executionsAtom);
    store.set(replica.executionsAtom, withRuns(stream, [run([C1])]));
    expect(requested(store)).toEqual([]);
    expect(statusOf(store)).toBe("queued");
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(1);

    // The run ends without ever planning the cell.
    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed")]),
    );
    expect(statusOf(store)).toBe("idle");
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  });

  it("hands over at once when the stream showed the run first", () => {
    const { store, replica } = shown();
    const made = request(store, [C1]);
    const stream = store.get(replica.executionsAtom);
    store.set(replica.executionsAtom, withRuns(stream, [run([C1])]));

    acceptRun(store, made, run([C1]));

    expect(requested(store)).toEqual([]);
    expect(statusOf(store)).toBe("queued");
  });

  it("leaves a later request for the same cell when an earlier run ends", () => {
    const { store, replica } = shown();
    const first = request(store, [C1]);
    const second = request(store, [C1]);
    acceptRun(store, first, run([C1]));

    const stream = store.get(replica.executionsAtom);
    store.set(replica.executionsAtom, withRuns(stream, [run([C1])]));
    expect(requested(store)).toEqual([C1]);
    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed")]),
    );
    expect(statusOf(store)).toBe("queued");

    acceptRun(store, second, run([C1], "queued", "run-2"));
    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed"), run([C1], "queued", "run-2")]),
    );
    expect(requested(store)).toEqual([]);
    expect(statusOf(store)).toBe("queued");

    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed", "run-2")]),
    );
    expect(statusOf(store)).toBe("idle");
  });

  it("keeps waiting while the stream is between a reset and its snapshot", () => {
    const { store, replica } = shown();
    const made = request(store, [C1]);
    acceptRun(store, made, run([C1]));

    const notebook = store.get(replica.notebookAtom);
    store.set(replica.notebookAtom, null);
    const stream = store.get(replica.executionsAtom);
    store.set(replica.executionsAtom, { ...stream });
    store.set(replica.notebookAtom, notebook);
    expect(requested(store)).toEqual([C1]);
    expect(statusOf(store)).toBe("queued");

    store.set(replica.executionsAtom, withRuns(stream, [run([C1])]));
    expect(requested(store)).toEqual([]);
    expect(statusOf(store)).toBe("queued");
  });

  it("drops the request once the replica shows another notebook", () => {
    const { store, replica } = shown();
    const made = request(store, [C1]);
    acceptRun(store, made, run([C1]));

    store.set(replica.notebookAtom, MockExecutions.notebook("n2"));
    const stream = store.get(replica.executionsAtom);
    store.set(replica.executionsAtom, withRuns(stream, [run([C1])]));
    store.set(replica.notebookAtom, MockExecutions.notebook("n1"));

    expect(requested(store)).toEqual([]);
  });

  it("stops following a run once the replica changes", () => {
    const { store, replica } = shown();
    const made = request(store, [C1]);
    acceptRun(store, made, run([C1]));

    MockExecutions.seed(store, [], null, documentOf());
    request(store, [C1]);
    const stream = store.get(replica.executionsAtom);
    store.set(
      replica.executionsAtom,
      withRuns(stream, [run([C1], "completed")]),
    );

    expect(statusOf(store)).toBe("queued");
  });
});
