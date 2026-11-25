/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, expect, it } from "vitest";
import { cell, CONFIG } from "@/core/notebook/document/__tests__/fixtures";
import type { Execution, Executions, Results } from "@/core/notebook/replica";
import {
  anyRunning,
  blockedDescendants,
  type CellExecutionInputs,
  cellExecutionView,
  onlyScratchRunning,
  queuedOrRunningCount,
  runningCellIds,
} from "../select";
import { cellId, runId } from "@/__tests__/branded";

const C1 = cellId("c1");
const C2 = cellId("c2");
const C9 = cellId("c9");

it("counts only distinct disabled ancestors in a cycle", () => {
  const analysis: Protocol.AnalysisOutput = {
    notebook_id: "n1",
    document_etag: "v1",
    cells: {
      a: { defs: [], refs: [], parents: [cellId("b")], diagnostics: [] },
      b: { defs: [], refs: [], parents: [cellId("a")], diagnostics: [] },
    },
  };
  const disabled = (id: string) =>
    cell(id, "", { config: { ...CONFIG, disabled: true } });
  const a = disabled("a");
  expect(blockedDescendants(analysis, [a, cell("b", "")])).toEqual(
    new Set(["b"]),
  );
  expect(blockedDescendants(analysis, [a, disabled("b")])).toEqual(
    new Set(["a", "b"]),
  );
});

const T0 = "2026-10-01T09:20:11Z";
const T1 = "2026-10-01T09:20:12.500Z";
const T2 = "2026-10-01T09:20:20Z";

const QUEUED: Protocol.ExecutionStateOutput = { status: "queued" };
const RUNNING: Protocol.ExecutionStateOutput = {
  status: "running",
  started_at: T0,
};

function record(
  overrides: Partial<Protocol.ExecutionOutput> & { id: string },
): Protocol.ExecutionOutput {
  return {
    run_id: runId("run-1"),
    runtime_id: "r1",
    caused_by_id: null,
    cell_id: C1,
    code_fingerprint: "0f71456db2ea83f4",
    created_at: null,
    state: {
      status: "completed",
      started_at: T0,
      completed_at: T1,
      outcome: { kind: "succeeded" },
      depends_on: {},
    },
    ...overrides,
  };
}

function execution(
  overrides: Partial<Protocol.ExecutionOutput> & { id: string },
) {
  return {
    record: record(overrides),
    output: null,
    outputVersion: 0,
    items: new Map(),
  };
}

function run(
  cells: string[],
  status: Protocol.RunState["status"],
  id = "run-1",
): Protocol.RunOutput {
  return {
    id: runId(id),
    notebook_id: "n1",
    runtime_id: "r1",
    origin: { kind: "cells", cell_ids: cells.map(cellId) },
    created_at: "2026-10-01T09:20:00Z",
    state:
      status === "completed"
        ? {
            status,
            started_at: null,
            completed_at: "2026-10-01T09:20:02Z",
            outcome: { kind: "succeeded" },
          }
        : status === "running"
          ? { status, started_at: "2026-10-01T09:20:01Z" }
          : { status },
  };
}

const CELLS = ["c1", "c2", "c3", "c4", "c5"].map(cellId);

/** Inputs whose document has `CELLS`, with `disabled` kept from running. */
function inputs({
  executions = [],
  runs = [],
  results = new Map(),
  requested = new Set(),
  disabled = [],
  blocked = new Set(),
  runtimeId = null,
}: {
  executions?: Execution[];
  runs?: Protocol.RunOutput[];
  results?: Results;
  requested?: ReadonlySet<Protocol.CellId>;
  disabled?: readonly string[];
  blocked?: ReadonlySet<Protocol.CellId>;
  runtimeId?: string | null;
}): CellExecutionInputs {
  const stream: Executions = {
    scratch: null,
    results,
    variables: new Map(),
    runs: new Map(runs.map((r) => [r.id, r])),
    executions: new Map(executions.map((e) => [e.record.id, e])),
    latest: new Map(
      executions.flatMap((e) =>
        e.record.cell_id === null ? [] : [[e.record.cell_id, e.record.id]],
      ),
    ),
  };
  const cells = new Map(
    CELLS.map((id) => [
      id,
      { config: { ...CONFIG, disabled: disabled.includes(id) } },
    ]),
  );
  return {
    executions: stream,
    results,
    cells,
    requested,
    blocked,
    shownBlocked: blocked,
    runtimeId,
  };
}

describe("cellExecutionView", () => {
  it("is idle with no outcome before a cell runs", () => {
    expect(cellExecutionView(inputs({}), C1)).toEqual({
      status: "idle",
      blocked: false,
      shownBlock: null,
      outcome: null,
      startedAt: null,
      duration: null,
      live: true,
    });
  });

  it("follows the execution on the stream while it is unfinished", () => {
    const queued = inputs({
      executions: [
        execution({
          id: "e1",
          state: QUEUED,
        }),
      ],
    });
    expect(cellExecutionView(queued, C1).status).toBe("queued");
    const running = inputs({
      executions: [
        execution({
          id: "e1",
          state: { status: "running", started_at: T2 },
        }),
      ],
      results: new Map([[C1, execution({ id: "e0" })]]),
    });
    expect(cellExecutionView(running, C1)).toEqual({
      status: "running",
      blocked: false,
      shownBlock: null,
      outcome: null,
      startedAt: Date.parse(T2),
      duration: null,
      live: true,
    });
  });

  it("says whether the notebook's runtime produced the cell's result", () => {
    const result = execution({ id: "e1" });
    const produced = (runtimeId: string | null) =>
      cellExecutionView(
        inputs({ results: new Map([[C1, result]]), runtimeId }),
        C1,
      ).live;
    expect(produced("r1")).toBe(true);
    // A restart replaces the runtime and keeps the results.
    expect(produced("r2")).toBe(false);
    // Nothing to compare against, as on a static page.
    expect(produced(null)).toBe(true);
    // A restored result names no runtime.
    expect(
      cellExecutionView(
        inputs({
          results: new Map([[C1, execution({ id: "e1", runtime_id: null })]]),
          runtimeId: "r1",
        }),
        C1,
      ).live,
    ).toBe(false);
  });

  it("reports how the last completed execution ended, with its timing", () => {
    const completedWith = (outcome: Protocol.ExecutionOutcomeOutput) => ({
      status: "completed" as const,
      started_at: T0,
      completed_at: T1,
      outcome,
      depends_on: {},
    });
    const ended = (outcome: Protocol.ExecutionOutcomeOutput) =>
      cellExecutionView(
        inputs({
          executions: [execution({ id: "e1", state: completedWith(outcome) })],
          results: new Map([
            [C1, execution({ id: "e1", state: completedWith(outcome) })],
          ]),
        }),
        C1,
      );
    const value = ended({ kind: "succeeded" });
    expect(value).toEqual({
      status: "idle",
      blocked: false,
      shownBlock: null,
      outcome: "succeeded",
      startedAt: Date.parse(T0),
      duration: 1500,
      live: true,
    });
    const error = (kind: string): Protocol.ExecutionOutcomeOutput => ({
      kind: "failed",
      error: {
        kind,
        message: "",
        name: null,
        traceback: null,
        source: "marimo",
        severity: "error",
        range: null,
        related: [],
      },
    });
    expect(ended(error("exception")).outcome).toBe("failed");
    const skipped: Protocol.ExecutionOutcomeOutput = {
      kind: "skipped",
      reason: "ancestor-stopped",
      message: "",
      related: [],
    };
    expect(ended(skipped).outcome).toBe("skipped");
    expect(ended({ kind: "cancelled" }).outcome).toBe("cancelled");
  });

  it("reads as queued from a request the stream has not shown a run for", () => {
    const requested = inputs({
      executions: [execution({ id: "e1" })],
      results: new Map([[C1, execution({ id: "e1" })]]),
      requested: new Set([C1]),
    });
    expect(cellExecutionView(requested, C1).status).toBe("queued");
    expect(cellExecutionView(requested, C1).outcome).toBeNull();

    const fresh = inputs({ requested: new Set([C1]) });
    expect(cellExecutionView(fresh, C1).status).toBe("queued");
  });

  it("reads as queued from an unfinished run that names the cell until it is planned", () => {
    const result = new Map([[C1, execution({ id: "e1" })]]);
    const accepted = inputs({
      runs: [run(["c1"], "queued", "run-2")],
      executions: [execution({ id: "e1" })],
      results: result,
    });
    expect(cellExecutionView(accepted, C1).status).toBe("queued");
    expect(cellExecutionView(accepted, C1).outcome).toBeNull();

    // The cell's execution in the run takes over once the kernel plans it.
    const planned = inputs({
      runs: [run(["c1"], "running", "run-2")],
      executions: [
        execution({
          id: "e2",
          run_id: runId("run-2"),
          state: RUNNING,
        }),
      ],
      results: result,
    });
    expect(cellExecutionView(planned, C1).status).toBe("running");

    const done = inputs({
      runs: [run(["c1", "c2"], "running", "run-2")],
      executions: [execution({ id: "e2", run_id: runId("run-2") })],
      results: new Map([[C1, execution({ id: "e2", run_id: runId("run-2") })]]),
    });
    expect(cellExecutionView(done, C1).status).toBe("idle");
    expect(cellExecutionView(done, C1).outcome).toBe("succeeded");
    expect(cellExecutionView(done, C2).status).toBe("queued");

    // The stream let the execution go while its run goes on with other cells.
    const retained = inputs({
      runs: [run(["c1", "c2"], "running", "run-2")],
      results: new Map([[C1, execution({ id: "e2", run_id: runId("run-2") })]]),
    });
    expect(cellExecutionView(retained, C1).status).toBe("idle");
    expect(cellExecutionView(retained, C2).status).toBe("queued");

    // A later run names the cell again while the earlier one's result stands.
    const again = inputs({
      runs: [run(["c1"], "running", "run-2"), run(["c1"], "queued", "run-3")],
      executions: [execution({ id: "e2", run_id: runId("run-2") })],
      results: new Map([[C1, execution({ id: "e2", run_id: runId("run-2") })]]),
    });
    expect(cellExecutionView(again, C1).status).toBe("queued");

    const over = inputs({ runs: [run(["c1"], "completed")] });
    expect(cellExecutionView(over, C1).status).toBe("idle");
  });

  it("does not read as queued a named cell a run cannot reach", () => {
    const runs = [run(["c1", "c9"], "queued")];
    expect(
      cellExecutionView(inputs({ runs, disabled: ["c1"] }), C1).status,
    ).toBe("idle");
    expect(
      cellExecutionView(inputs({ runs, blocked: new Set([C1]) }), C1).status,
    ).toBe("idle");
    // The document no longer has c9.
    expect(cellExecutionView(inputs({ runs }), C9).status).toBe("idle");
    expect(
      cellExecutionView(inputs({ requested: new Set([C9]) }), C9).status,
    ).toBe("idle");
  });

  it("shows a blocked cell as disabled transitively, with its last outcome", () => {
    const view = cellExecutionView(
      inputs({
        results: new Map([[C1, execution({ id: "e1" })]]),
        blocked: new Set([C1]),
      }),
      C1,
    );
    expect(view.status).toBe("idle");
    expect(view.blocked).toBe(true);
    expect(view.outcome).toBe("succeeded");
  });
});

describe("notebook-level views", () => {
  const stream = inputs({
    executions: [
      execution({ id: "e1", state: RUNNING }),
      execution({
        id: "e2",
        cell_id: C2,
        state: QUEUED,
      }),
      execution({ id: "e3", cell_id: cellId("c3") }),
      execution({
        id: "s1",
        cell_id: null,
        state: RUNNING,
      }),
    ],
    runs: [run(["c1", "c2", "c5"], "running"), run(["c5"], "queued", "run-2")],
    results: new Map([
      [cellId("c5"), execution({ id: "e5", cell_id: cellId("c5") })],
    ]),
    requested: new Set([C2, cellId("c4")]),
  });

  it("counts unfinished executions and cells awaiting a run the kernel has not planned", () => {
    expect(anyRunning(stream.executions)).toBe(true);
    expect(queuedOrRunningCount(stream)).toBe(5);
    expect(runningCellIds(stream.executions)).toEqual(["c1"]);
    expect(onlyScratchRunning(stream.executions)).toBe(false);
  });

  it("tells scratch work apart from cells", () => {
    const scratch = inputs({
      executions: [
        execution({
          id: "s1",
          cell_id: null,
          state: RUNNING,
        }),
        execution({ id: "e3", cell_id: cellId("c3") }),
      ],
    });
    expect(anyRunning(scratch.executions)).toBe(true);
    expect(onlyScratchRunning(scratch.executions)).toBe(true);
    expect(queuedOrRunningCount(scratch)).toBe(1);
  });
});
