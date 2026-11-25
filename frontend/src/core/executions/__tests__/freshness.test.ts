/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, expect, it } from "vitest";
import type { Executions, Result } from "@/core/notebook/replica";
import { type CellFreshnessInputs, freshnessOf } from "../freshness";
import { cellId, runId } from "@/__tests__/branded";

const C3 = cellId("c3");
const FIXTURE_CELL = cellId("k7f2");

const T0 = "2026-10-01T09:20:11Z";
const T1 = "2026-10-01T09:20:12.500Z";

/** The spec's worked example: `c3` binds `x`, which `k7f2` reads. */
const C3_FINGERPRINT = "0f71456db2ea83f4";
const K7F2_FINGERPRINT = "db2b1c9e4a7f0d36";

function cell(
  id: string,
  fingerprint: string,
  overrides: Partial<Protocol.CellOutput> = {},
): Protocol.CellOutput {
  return {
    id: cellId(id),
    notebook_id: "n1",
    code: null,
    name: "_",
    config: {
      column: null,
      disabled: false,
      hide_code: false,
      expand_output: false,
    },
    etag: `etag-${id}`,
    code_fingerprint: fingerprint,
    version: 1,
    ...overrides,
  };
}

const SUCCEEDED: Protocol.ExecutionOutcomeOutput = { kind: "succeeded" };

/** A completed state that read `depends_on`. */
function completed(
  depends_on: Protocol.ExecutionCompletedOutput["depends_on"] = {},
  outcome: Protocol.ExecutionOutcomeOutput = SUCCEEDED,
): Protocol.ExecutionCompletedOutput {
  return {
    status: "completed",
    started_at: T0,
    completed_at: T1,
    outcome,
    depends_on,
  };
}

function record(
  fields: Partial<Protocol.ExecutionOutput> & {
    id: string;
    cell_id: Protocol.CellId;
    code_fingerprint: string;
  },
): Protocol.ExecutionOutput {
  return {
    run_id: runId("run-1"),
    runtime_id: "r1",
    caused_by_id: null,
    created_at: null,
    state: completed(),
    ...fields,
  };
}

function variable(
  name: string,
  execution: string,
  update = 0,
): Protocol.Variable {
  return {
    id: `${execution}-${name}`,
    execution_id: execution,
    name,
    revision: { execution_id: execution, update },
    type: null,
    preview: null,
  };
}

function execution(
  rec: Protocol.ExecutionOutput,
  variables: Protocol.Variable[] = [],
) {
  return {
    record: rec,
    output: null,
    outputVersion: 0,
    items: new Map(),
    variables: new Map(variables.map((v) => [v.id, v])),
  };
}

function inputs({
  cells,
  executions,
  results = executions.map((e) => e.record),
}: {
  cells: Protocol.CellOutput[];
  executions: ReturnType<typeof execution>[];
  /** Defaults to the executions on the stream. */
  results?: Protocol.ExecutionOutput[];
}): CellFreshnessInputs {
  const stream: Executions = {
    results: new Map(),
    scratch: null,
    runs: new Map(),
    variables: new Map(
      executions.flatMap((e) =>
        e.record.cell_id === null ? [] : [[e.record.cell_id, e.variables]],
      ),
    ),
    executions: new Map(executions.map((e) => [e.record.id, e])),
    latest: new Map(
      executions.flatMap((e) =>
        e.record.cell_id === null ? [] : [[e.record.cell_id, e.record.id]],
      ),
    ),
  };
  const retained = new Map<Protocol.CellId, Result | null>(
    cells.map((c) => [c.id, null]),
  );
  for (const result of results) {
    if (result.cell_id !== null) {
      retained.set(result.cell_id, {
        record: result,
        output: null,
        outputVersion: 0,
      });
    }
  }
  return {
    cells: new Map(cells.map((c) => [c.id, c])),
    executions: { ...stream, results: retained },
    results: retained,
  };
}

const c3 = cell("c3", C3_FINGERPRINT);
const k7f2 = cell("k7f2", K7F2_FINGERPRINT);
const e12 = record({
  id: "e12",
  cell_id: C3,
  code_fingerprint: C3_FINGERPRINT,
});
const e13 = record({
  id: "e13",
  cell_id: FIXTURE_CELL,
  code_fingerprint: K7F2_FINGERPRINT,
  state: completed({ x: { execution_id: "e12", update: 0 } }),
});

describe("cellFreshness", () => {
  it("is current for a cell that never completed, having nothing to compare", () => {
    const state = inputs({ cells: [c3], executions: [] });
    expect(freshnessOf(state)(C3)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
    expect(freshnessOf(state)(cellId("missing"))).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("finds both executions of the worked example current", () => {
    const state = inputs({
      cells: [c3, k7f2],
      executions: [execution(e12, [variable("x", "e12")]), execution(e13)],
    });
    const freshness = freshnessOf(state);
    expect(freshness(C3)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
    expect(freshness(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("is outdated as updated once a value it depends on advances", () => {
    const state = inputs({
      cells: [c3, k7f2],
      executions: [execution(e12, [variable("x", "e12", 1)]), execution(e13)],
    });
    const freshness = freshnessOf(state);
    expect(freshness(C3)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
    expect(freshness(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("is outdated as edited when the cell's code changed, and so are its dependents", () => {
    const state = inputs({
      cells: [cell("c3", "ffff000011112222"), k7f2],
      executions: [execution(e12, [variable("x", "e12")]), execution(e13)],
    });
    const freshness = freshnessOf(state);
    expect(freshness(C3)).toEqual({
      sourceChanged: true,
      inputsChanged: false,
    });
    // The dependent's own source and the values it read are as they were.
    expect(freshness(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("marks changed inputs through a binder that did not run again", () => {
    const m = cell("m", "aaaa111122223333");
    const e14 = record({
      id: "e14",
      cell_id: C3,
      code_fingerprint: C3_FINGERPRINT,
    });
    const e15 = record({
      id: "e15",
      cell_id: cellId("m"),
      code_fingerprint: "aaaa111122223333",
      state: completed({ y: { execution_id: "e13", update: 0 } }),
    });
    const state = inputs({
      cells: [c3, k7f2, m],
      executions: [
        execution(e14, [variable("x", "e14")]),
        execution(e13, [variable("y", "e13")]),
        execution(e15),
      ],
    });
    const freshness = freshnessOf(state);
    expect(freshness(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
    expect(freshness(cellId("m"))).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("is outdated as replaced once the binding execution runs again", () => {
    const e14 = record({
      id: "e14",
      cell_id: C3,
      code_fingerprint: C3_FINGERPRINT,
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [execution(e14, [variable("x", "e14")]), execution(e13)],
    });
    expect(freshnessOf(state)(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("is outdated as replaced while the binding cell runs again and the name is unbound", () => {
    const queued = record({
      id: "e14",
      cell_id: C3,
      code_fingerprint: C3_FINGERPRINT,
      state: { status: "queued" },
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [execution(queued), execution(e13)],
      results: [e12, e13],
    });
    const freshness = freshnessOf(state);
    expect(freshness(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
    // The retained result for c3 still compares by its own fingerprint.
    expect(freshness(C3)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("is outdated as replaced once a name it read as unbound is bound", () => {
    const reader = record({
      id: "e20",
      cell_id: FIXTURE_CELL,
      code_fingerprint: K7F2_FINGERPRINT,
      state: completed({ y: null }),
    });
    const unbound = inputs({
      cells: [c3, k7f2],
      executions: [execution(reader)],
    });
    expect(freshnessOf(unbound)(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });

    const bound = inputs({
      cells: [c3, k7f2],
      executions: [execution(e12, [variable("y", "e12")]), execution(reader)],
    });
    expect(freshnessOf(bound)(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("reports both facts when the source and a value it read changed", () => {
    const reader = record({
      id: "e21",
      cell_id: FIXTURE_CELL,
      code_fingerprint: "stale",
      state: completed({
        x: { execution_id: "e12", update: 0 },
        z: { execution_id: "e30", update: 0 },
      }),
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [
        execution(e12, [variable("x", "e12", 2)]),
        execution(reader),
      ],
    });
    expect(freshnessOf(state)(FIXTURE_CELL)).toEqual({
      sourceChanged: true,
      inputsChanged: true,
    });
  });

  it("compares a skipped execution by the dependencies it would have read", () => {
    const skipped = record({
      id: "e22",
      cell_id: FIXTURE_CELL,
      code_fingerprint: K7F2_FINGERPRINT,
      state: completed(
        { x: { execution_id: "e12", update: 0 } },
        {
          kind: "skipped",
          reason: "upstream-failed",
          message: "",
          related: [],
        },
      ),
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [
        execution(e12, [variable("x", "e12", 1)]),
        execution(skipped),
      ],
    });
    expect(freshnessOf(state)(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("treats a result whose cell left the document as edited", () => {
    const state = inputs({
      cells: [k7f2],
      executions: [execution(e12, [variable("x", "e12")]), execution(e13)],
      results: [e12, e13],
    });
    expect(freshnessOf(state)(C3)).toEqual({
      sourceChanged: true,
      inputsChanged: false,
    });
  });

  it.each(["running", "completed"] as const)(
    "detects a binding in a newer runtime while its execution is %s",
    (status) => {
      const reader = record({
        id: "reader-r2",
        cell_id: FIXTURE_CELL,
        runtime_id: "r2",
        code_fingerprint: K7F2_FINGERPRINT,
        state: {
          ...completed({ x: null }),
          started_at: "2026-10-01T09:21:00Z",
          completed_at: "2026-10-01T09:21:01Z",
        },
      });
      const binder = record({
        id: "binder-r3",
        cell_id: C3,
        runtime_id: "r3",
        code_fingerprint: C3_FINGERPRINT,
        state:
          status === "completed"
            ? {
                ...completed(),
                started_at: "2026-10-01T09:22:00Z",
                completed_at: "2026-10-01T09:22:01Z",
              }
            : { status, started_at: "2026-10-01T09:22:00Z" },
      });
      const state = inputs({
        cells: [c3, k7f2],
        executions: [
          execution(binder, [variable("x", binder.id)]),
          execution(reader),
        ],
        results: [e12, reader],
      });

      expect(freshnessOf(state)(FIXTURE_CELL)).toEqual({
        sourceChanged: false,
        inputsChanged: true,
      });
    },
  );

  it("treats a name bound only by an earlier runtime as unbound", () => {
    const reader = record({
      id: "e20",
      cell_id: FIXTURE_CELL,
      runtime_id: "r2",
      code_fingerprint: K7F2_FINGERPRINT,
      state: completed({ x: null }),
    });
    const retained = inputs({
      cells: [c3, k7f2],
      executions: [execution(e12, [variable("x", "e12")]), execution(reader)],
    });
    expect(freshnessOf(retained)(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });

    const rebound = record({
      id: "e14",
      cell_id: C3,
      runtime_id: "r2",
      code_fingerprint: C3_FINGERPRINT,
    });
    const bound = inputs({
      cells: [c3, k7f2],
      executions: [
        execution(rebound, [variable("x", "e14")]),
        execution(reader),
      ],
    });
    expect(freshnessOf(bound)(FIXTURE_CELL)).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it.each(["queued", "running"] as const)(
    "flags reverting to completed source while different source is %s",
    (status) => {
      const pending = record({
        id: "e14",
        cell_id: C3,
        code_fingerprint: "ffff000011112222",
        state: status === "running" ? { status, started_at: T0 } : { status },
      });
      const state = inputs({
        cells: [c3],
        executions: [execution(pending)],
        results: [e12],
      });

      expect(freshnessOf(state)(C3)).toEqual({
        sourceChanged: true,
        inputsChanged: false,
      });
    },
  );

  it("does not report changed source while a newer execution runs it", () => {
    const edited = cell("c3", "ffff000011112222");
    const running = record({
      id: "e14",
      cell_id: C3,
      code_fingerprint: "ffff000011112222",
      state: { status: "running", started_at: T0 },
    });
    const covered = inputs({
      cells: [edited, k7f2],
      executions: [execution(running), execution(e13)],
      results: [e12, e13],
    });
    expect(freshnessOf(covered)(C3).sourceChanged).toBe(false);

    const stale = inputs({
      cells: [edited, k7f2],
      executions: [
        execution({ ...running, code_fingerprint: "older" }),
        execution(e13),
      ],
      results: [e12, e13],
    });
    expect(freshnessOf(stale)(C3).sourceChanged).toBe(true);
  });
});
