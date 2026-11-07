/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { describe, expect, it } from "vitest";
import type { Execution, Executions } from "@/core/notebook/replica";
import { type CellFreshnessInputs, freshnessOf } from "../freshness";

const T0 = "2026-10-01T09:20:11Z";
const T1 = "2026-10-01T09:20:12.500Z";

/** The spec's worked example: `c3` binds `x`, which `k7f2` reads. */
const C3_FINGERPRINT = "0f71456db2ea83f4";
const K7F2_FINGERPRINT = "db2b1c9e4a7f0d36";

function cell(
  id: string,
  fingerprint: string,
  overrides: Partial<Protocol.Cell> = {},
): Protocol.Cell {
  return {
    id,
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

function record(
  overrides: Partial<Protocol.Execution> & {
    id: string;
    cell_id: string;
    code_fingerprint: string;
  },
): Protocol.Execution {
  return {
    run_id: "run-1",
    runtime_id: "r1",
    caused_by: null,
    code: null,
    depends_on: {},
    status: "completed",
    outcome: { kind: "value", display: null },
    started_at: T0,
    completed_at: T1,
    ...overrides,
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
    revision: { execution, update },
    type: null,
    preview: null,
  };
}

function execution(
  rec: Protocol.Execution,
  variables: Protocol.Variable[] = [],
): Execution {
  return {
    record: rec,
    items: new Map(),
    variables: new Map(variables.map((v) => [v.id, v])),
  };
}

function inputs({
  cells,
  executions,
  results = executions.map((e) => e.record),
}: {
  cells: Protocol.Cell[];
  executions: Execution[];
  /** Defaults to the executions on the stream. */
  results?: Protocol.Execution[];
}): CellFreshnessInputs {
  const stream: Executions = {
    runs: new Map(),
    executions: new Map(executions.map((e) => [e.record.id, e])),
    latest: new Map(
      executions.flatMap((e) =>
        e.record.cell_id === null ? [] : [[e.record.cell_id, e.record.id]],
      ),
    ),
  };
  const retained = new Map<Protocol.CellId, Protocol.Execution | null>(
    cells.map((c) => [c.id, null]),
  );
  for (const result of results) {
    if (result.cell_id !== null) {
      retained.set(result.cell_id, result);
    }
  }
  return {
    cells: new Map(cells.map((c) => [c.id, c])),
    executions: stream,
    results: retained,
  };
}

const c3 = cell("c3", C3_FINGERPRINT);
const k7f2 = cell("k7f2", K7F2_FINGERPRINT);
const e12 = record({
  id: "e12",
  cell_id: "c3",
  code_fingerprint: C3_FINGERPRINT,
});
const e13 = record({
  id: "e13",
  cell_id: "k7f2",
  code_fingerprint: K7F2_FINGERPRINT,
  depends_on: { x: { execution: "e12", update: 0 } },
});

describe("cellFreshness", () => {
  it("is current for a cell that never completed, having nothing to compare", () => {
    const state = inputs({ cells: [c3], executions: [] });
    expect(freshnessOf(state)("c3")).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
    expect(freshnessOf(state)("missing")).toEqual({
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
    expect(freshness("c3")).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
    expect(freshness("k7f2")).toEqual({
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
    expect(freshness("c3")).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
    expect(freshness("k7f2")).toEqual({
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
    expect(freshness("c3")).toEqual({
      sourceChanged: true,
      inputsChanged: false,
    });
    // The dependent's own source and the values it read are as they were.
    expect(freshness("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("marks changed inputs through a binder that did not run again", () => {
    const m = cell("m", "aaaa111122223333");
    const e14 = record({
      id: "e14",
      cell_id: "c3",
      code_fingerprint: C3_FINGERPRINT,
    });
    const e15 = record({
      id: "e15",
      cell_id: "m",
      code_fingerprint: "aaaa111122223333",
      depends_on: { y: { execution: "e13", update: 0 } },
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
    expect(freshness("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
    expect(freshness("m")).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("is outdated as replaced once the binding execution runs again", () => {
    const e14 = record({
      id: "e14",
      cell_id: "c3",
      code_fingerprint: C3_FINGERPRINT,
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [execution(e14, [variable("x", "e14")]), execution(e13)],
    });
    expect(freshnessOf(state)("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("is outdated as replaced while the binding cell runs again and the name is unbound", () => {
    const queued = record({
      id: "e14",
      cell_id: "c3",
      code_fingerprint: C3_FINGERPRINT,
      status: "queued",
      outcome: null,
      started_at: null,
      completed_at: null,
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [execution(queued), execution(e13)],
      results: [e12, e13],
    });
    const freshness = freshnessOf(state);
    expect(freshness("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
    // The retained result for c3 still compares by its own fingerprint.
    expect(freshness("c3")).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("is outdated as replaced once a name it read as unbound is bound", () => {
    const reader = record({
      id: "e20",
      cell_id: "k7f2",
      code_fingerprint: K7F2_FINGERPRINT,
      depends_on: { y: null },
    });
    const unbound = inputs({
      cells: [c3, k7f2],
      executions: [execution(reader)],
    });
    expect(freshnessOf(unbound)("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });

    const bound = inputs({
      cells: [c3, k7f2],
      executions: [execution(e12, [variable("y", "e12")]), execution(reader)],
    });
    expect(freshnessOf(bound)("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it("reports both facts when the source and a value it read changed", () => {
    const reader = record({
      id: "e21",
      cell_id: "k7f2",
      code_fingerprint: "stale",
      depends_on: {
        x: { execution: "e12", update: 0 },
        z: { execution: "e30", update: 0 },
      },
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [
        execution(e12, [variable("x", "e12", 2)]),
        execution(reader),
      ],
    });
    expect(freshnessOf(state)("k7f2")).toEqual({
      sourceChanged: true,
      inputsChanged: true,
    });
  });

  it("compares a skipped execution by the dependencies it would have read", () => {
    const skipped = record({
      id: "e22",
      cell_id: "k7f2",
      code_fingerprint: K7F2_FINGERPRINT,
      outcome: {
        kind: "skipped",
        reason: "upstream-failed",
        message: "",
        related: [],
      },
      depends_on: { x: { execution: "e12", update: 0 } },
    });
    const state = inputs({
      cells: [c3, k7f2],
      executions: [
        execution(e12, [variable("x", "e12", 1)]),
        execution(skipped),
      ],
    });
    expect(freshnessOf(state)("k7f2")).toEqual({
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
    expect(freshnessOf(state)("c3")).toEqual({
      sourceChanged: true,
      inputsChanged: false,
    });
  });

  it.each(["running", "completed"] as const)(
    "detects a binding in a newer runtime while its execution is %s",
    (status) => {
      const reader = record({
        id: "reader-r2",
        cell_id: "k7f2",
        runtime_id: "r2",
        code_fingerprint: K7F2_FINGERPRINT,
        depends_on: { x: null },
        started_at: "2026-10-01T09:21:00Z",
        completed_at: "2026-10-01T09:21:01Z",
      });
      const binder = record({
        id: "binder-r3",
        cell_id: "c3",
        runtime_id: "r3",
        code_fingerprint: C3_FINGERPRINT,
        status,
        started_at: "2026-10-01T09:22:00Z",
        completed_at: status === "completed" ? "2026-10-01T09:22:01Z" : null,
      });
      const state = inputs({
        cells: [c3, k7f2],
        executions: [
          execution(binder, [variable("x", binder.id)]),
          execution(reader),
        ],
        results: [e12, reader],
      });

      expect(freshnessOf(state)("k7f2")).toEqual({
        sourceChanged: false,
        inputsChanged: true,
      });
    },
  );

  it("treats a name bound only by an earlier runtime as unbound", () => {
    const reader = record({
      id: "e20",
      cell_id: "k7f2",
      runtime_id: "r2",
      code_fingerprint: K7F2_FINGERPRINT,
      depends_on: { x: null },
    });
    const retained = inputs({
      cells: [c3, k7f2],
      executions: [execution(e12, [variable("x", "e12")]), execution(reader)],
    });
    expect(freshnessOf(retained)("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });

    const rebound = record({
      id: "e14",
      cell_id: "c3",
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
    expect(freshnessOf(bound)("k7f2")).toEqual({
      sourceChanged: false,
      inputsChanged: true,
    });
  });

  it.each(["queued", "running"] as const)(
    "flags reverting to completed source while different source is %s",
    (status) => {
      const pending = record({
        id: "e14",
        cell_id: "c3",
        code_fingerprint: "ffff000011112222",
        status,
        outcome: null,
        started_at: status === "running" ? T0 : null,
        completed_at: null,
      });
      const state = inputs({
        cells: [c3],
        executions: [execution(pending)],
        results: [e12],
      });

      expect(freshnessOf(state)("c3")).toEqual({
        sourceChanged: true,
        inputsChanged: false,
      });
    },
  );

  it("does not report changed source while a newer execution runs it", () => {
    const edited = cell("c3", "ffff000011112222");
    const running = record({
      id: "e14",
      cell_id: "c3",
      code_fingerprint: "ffff000011112222",
      status: "running",
      outcome: null,
      completed_at: null,
    });
    const covered = inputs({
      cells: [edited, k7f2],
      executions: [execution(running), execution(e13)],
      results: [e12, e13],
    });
    expect(freshnessOf(covered)("c3").sourceChanged).toBe(false);

    const stale = inputs({
      cells: [edited, k7f2],
      executions: [
        execution({ ...running, code_fingerprint: "older" }),
        execution(e13),
      ],
      results: [e12, e13],
    });
    expect(freshnessOf(stale)("c3").sourceChanged).toBe(true);
  });
});
