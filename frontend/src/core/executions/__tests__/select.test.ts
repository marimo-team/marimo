/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, expect, it } from "vitest";
import { CONFIG } from "@/core/notebook/document/__tests__/fixtures";
import type { Execution, Executions, Results } from "@/core/notebook/replica";
import {
  anyRunning,
  type CellExecutionInputs,
  cellExecutionView,
  onlyScratchRunning,
  queuedOrRunningCount,
  runningCellIds,
} from "../select";

const T0 = "2026-10-01T09:20:11Z";
const T1 = "2026-10-01T09:20:12.500Z";
const T2 = "2026-10-01T09:20:20Z";

function record(
  overrides: Partial<Protocol.Execution> & { id: string },
): Protocol.Execution {
  return {
    run_id: "run-1",
    runtime_id: "r1",
    caused_by: null,
    cell_id: "c1",
    code: null,
    code_fingerprint: "0f71456db2ea83f4",
    depends_on: {},
    status: "completed",
    outcome: { kind: "value", display: null },
    started_at: T0,
    completed_at: T1,
    ...overrides,
  };
}

function execution(overrides: Partial<Protocol.Execution> & { id: string }) {
  return { record: record(overrides), items: new Map(), variables: new Map() };
}

function run(
  cells: string[],
  status: Protocol.Run["status"],
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

const CELLS = ["c1", "c2", "c3", "c4", "c5"];

/** Inputs whose document has `CELLS`, with `disabled` kept from running. */
function inputs({
  executions = [],
  runs = [],
  results = new Map(),
  requested = new Set(),
  disabled = [],
  blocked = new Set(),
}: {
  executions?: Execution[];
  runs?: Protocol.Run[];
  results?: Results;
  requested?: ReadonlySet<string>;
  disabled?: readonly string[];
  blocked?: ReadonlySet<string>;
}): CellExecutionInputs {
  const stream: Executions = {
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
  return { executions: stream, results, cells, requested, blocked };
}

describe("cellExecutionView", () => {
  it("is idle with no outcome before a cell runs", () => {
    expect(cellExecutionView(inputs({}), "c1")).toEqual({
      status: "idle",
      blocked: false,
      outcome: null,
      startedAt: null,
      duration: null,
      rendered: false,
    });
  });

  it("follows the execution on the stream while it is unfinished", () => {
    const queued = inputs({
      executions: [
        execution({
          id: "e1",
          status: "queued",
          outcome: null,
          started_at: null,
          completed_at: null,
        }),
      ],
    });
    expect(cellExecutionView(queued, "c1").status).toBe("queued");
    const running = inputs({
      executions: [
        execution({
          id: "e1",
          status: "running",
          outcome: null,
          started_at: T2,
          completed_at: null,
        }),
      ],
      results: new Map([["c1", record({ id: "e0" })]]),
    });
    expect(cellExecutionView(running, "c1")).toEqual({
      status: "running",
      blocked: false,
      outcome: null,
      startedAt: Date.parse(T2),
      duration: null,
      rendered: false,
    });
  });

  it("notes when a running execution has shown a value so far", () => {
    const showing = inputs({
      executions: [
        execution({
          id: "e1",
          status: "running",
          outcome: { kind: "value", display: null },
          completed_at: null,
        }),
      ],
    });
    expect(cellExecutionView(showing, "c1").rendered).toBe(true);
  });

  it("reports how the last completed execution ended, with its timing", () => {
    const ended = (outcome: Protocol.Outcome) =>
      cellExecutionView(
        inputs({
          executions: [execution({ id: "e1", outcome })],
          results: new Map([["c1", record({ id: "e1", outcome })]]),
        }),
        "c1",
      );
    const value = ended({ kind: "value", display: null });
    expect(value).toEqual({
      status: "idle",
      blocked: false,
      outcome: "value",
      startedAt: Date.parse(T0),
      duration: 1500,
      rendered: false,
    });
    const error = (kind: string): Protocol.Outcome => ({
      kind: "error",
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
    expect(ended(error("exception")).outcome).toBe("error");
    const skipped: Protocol.Outcome = {
      kind: "skipped",
      reason: "ancestor-stopped",
      message: "",
      related: [],
    };
    expect(ended(skipped).outcome).toBe("skipped");
    expect(ended({ kind: "interrupted" }).outcome).toBe("interrupted");
  });

  it("reads as queued from a request the stream has not shown a run for", () => {
    const requested = inputs({
      executions: [execution({ id: "e1" })],
      results: new Map([["c1", record({ id: "e1" })]]),
      requested: new Set(["c1"]),
    });
    expect(cellExecutionView(requested, "c1").status).toBe("queued");
    expect(cellExecutionView(requested, "c1").outcome).toBeNull();

    const fresh = inputs({ requested: new Set(["c1"]) });
    expect(cellExecutionView(fresh, "c1").status).toBe("queued");
  });

  it("reads as queued from an unfinished run that names the cell until it is planned", () => {
    const result = new Map([["c1", record({ id: "e1" })]]);
    const accepted = inputs({
      runs: [run(["c1"], "queued", "run-2")],
      executions: [execution({ id: "e1" })],
      results: result,
    });
    expect(cellExecutionView(accepted, "c1").status).toBe("queued");
    expect(cellExecutionView(accepted, "c1").outcome).toBeNull();

    // The cell's execution in the run takes over once the kernel plans it.
    const planned = inputs({
      runs: [run(["c1"], "running", "run-2")],
      executions: [
        execution({
          id: "e2",
          run_id: "run-2",
          status: "running",
          completed_at: null,
        }),
      ],
      results: result,
    });
    expect(cellExecutionView(planned, "c1").status).toBe("running");

    const done = inputs({
      runs: [run(["c1", "c2"], "running", "run-2")],
      executions: [execution({ id: "e2", run_id: "run-2" })],
      results: new Map([["c1", record({ id: "e2", run_id: "run-2" })]]),
    });
    expect(cellExecutionView(done, "c1").status).toBe("idle");
    expect(cellExecutionView(done, "c1").outcome).toBe("value");
    expect(cellExecutionView(done, "c2").status).toBe("queued");

    // The stream let the execution go while its run goes on with other cells.
    const retained = inputs({
      runs: [run(["c1", "c2"], "running", "run-2")],
      results: new Map([["c1", record({ id: "e2", run_id: "run-2" })]]),
    });
    expect(cellExecutionView(retained, "c1").status).toBe("idle");
    expect(cellExecutionView(retained, "c2").status).toBe("queued");

    // A later run names the cell again while the earlier one's result stands.
    const again = inputs({
      runs: [run(["c1"], "running", "run-2"), run(["c1"], "queued", "run-3")],
      executions: [execution({ id: "e2", run_id: "run-2" })],
      results: new Map([["c1", record({ id: "e2", run_id: "run-2" })]]),
    });
    expect(cellExecutionView(again, "c1").status).toBe("queued");

    const over = inputs({ runs: [run(["c1"], "completed")] });
    expect(cellExecutionView(over, "c1").status).toBe("idle");
  });

  it("does not read as queued a named cell a run cannot reach", () => {
    const runs = [run(["c1", "c9"], "queued")];
    expect(
      cellExecutionView(inputs({ runs, disabled: ["c1"] }), "c1").status,
    ).toBe("idle");
    expect(
      cellExecutionView(inputs({ runs, blocked: new Set(["c1"]) }), "c1")
        .status,
    ).toBe("idle");
    // The document no longer has c9.
    expect(cellExecutionView(inputs({ runs }), "c9").status).toBe("idle");
    expect(
      cellExecutionView(inputs({ requested: new Set(["c9"]) }), "c9").status,
    ).toBe("idle");
  });

  it("shows a blocked cell as disabled transitively, with its last outcome", () => {
    const view = cellExecutionView(
      inputs({
        results: new Map([["c1", record({ id: "e1" })]]),
        blocked: new Set(["c1"]),
      }),
      "c1",
    );
    expect(view.status).toBe("idle");
    expect(view.blocked).toBe(true);
    expect(view.outcome).toBe("value");
  });
});

describe("notebook-level views", () => {
  const stream = inputs({
    executions: [
      execution({ id: "e1", status: "running", completed_at: null }),
      execution({
        id: "e2",
        cell_id: "c2",
        status: "queued",
        started_at: null,
        completed_at: null,
      }),
      execution({ id: "e3", cell_id: "c3" }),
      execution({
        id: "s1",
        cell_id: null,
        status: "running",
        completed_at: null,
      }),
    ],
    runs: [run(["c1", "c2", "c5"], "running"), run(["c5"], "queued", "run-2")],
    results: new Map([["c5", record({ id: "e5", cell_id: "c5" })]]),
    requested: new Set(["c2", "c4"]),
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
          status: "running",
          completed_at: null,
        }),
        execution({ id: "e3", cell_id: "c3" }),
      ],
    });
    expect(anyRunning(scratch.executions)).toBe(true);
    expect(onlyScratchRunning(scratch.executions)).toBe(true);
    expect(queuedOrRunningCount(scratch)).toBe(1);
  });
});
