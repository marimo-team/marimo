/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, expect, it } from "vitest";
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

function inputs({
  executions = [],
  results = new Map(),
  submissions = new Map(),
  blocked = new Set(),
}: {
  executions?: Execution[];
  results?: Results;
  submissions?: ReadonlyMap<string, string | null>;
  blocked?: ReadonlySet<string>;
}): CellExecutionInputs {
  const stream: Executions = {
    runs: new Map(),
    executions: new Map(executions.map((e) => [e.record.id, e])),
    latest: new Map(
      executions.flatMap((e) =>
        e.record.cell_id === null ? [] : [[e.record.cell_id, e.record.id]],
      ),
    ),
  };
  return { executions: stream, results, submissions, blocked };
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

  it("reads as queued from a submission until the host shows a newer execution", () => {
    const before = inputs({
      executions: [execution({ id: "e1" })],
      results: new Map([["c1", record({ id: "e1" })]]),
      submissions: new Map([["c1", "e1"]]),
    });
    expect(cellExecutionView(before, "c1").status).toBe("queued");
    expect(cellExecutionView(before, "c1").outcome).toBeNull();

    // The stream let e1 go while the request was in flight; its result remains.
    const forgotten = inputs({
      results: new Map([["c1", record({ id: "e1" })]]),
      submissions: new Map([["c1", "e1"]]),
    });
    expect(cellExecutionView(forgotten, "c1").status).toBe("queued");

    const shown = inputs({
      executions: [
        execution({ id: "e2", status: "running", completed_at: null }),
      ],
      results: new Map([["c1", record({ id: "e1" })]]),
      submissions: new Map([["c1", "e1"]]),
    });
    expect(cellExecutionView(shown, "c1").status).toBe("running");

    const done = inputs({
      executions: [execution({ id: "e2" })],
      results: new Map([["c1", record({ id: "e2" })]]),
      submissions: new Map([["c1", "e1"]]),
    });
    expect(cellExecutionView(done, "c1").status).toBe("idle");

    const fresh = inputs({ submissions: new Map([["c1", null]]) });
    expect(cellExecutionView(fresh, "c1").status).toBe("queued");
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
    results: new Map([["c5", record({ id: "e5", cell_id: "c5" })]]),
    submissions: new Map([
      ["c2", "e2"],
      ["c4", null],
      ["c5", "e5"],
    ]),
  });

  it("counts unfinished executions and submissions the host has not shown", () => {
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
