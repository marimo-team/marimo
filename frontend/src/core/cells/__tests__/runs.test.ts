/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cellId, runId } from "@/__tests__/branded";
import type { ExecutionOutput as Execution } from "@marimo-team/client/protocol";
import {
  exportedForTesting,
  MAX_CODE_LENGTH,
  MAX_RUNS,
  type RunsState,
} from "../runs";

const { reducer, initialState, isPureMarkdown } = exportedForTesting;

const queued = {
  id: "e1",
  run_id: runId("r1"),
  runtime_id: "runtime",
  caused_by_id: null,
  cell_id: cellId("cell"),
  code_fingerprint: "fp",
  created_at: "2026-10-01T09:20:00Z",
  state: { status: "queued" },
} satisfies Execution;

function observe(
  state: RunsState,
  changes: Partial<Execution> = {},
  code = "print(1)",
) {
  return reducer(state, {
    type: "addExecution",
    payload: { record: { ...queued, ...changes }, code, receivedAt: 99 },
  });
}

describe("execution traces", () => {
  it("derives the same trace from live transitions and a retained completion", () => {
    const started_at = "1970-01-01T00:01:40Z";
    const completed = {
      depends_on: {},
      started_at,
      completed_at: "1970-01-01T00:01:42Z",
      status: "completed",
      outcome: { kind: "cancelled" },
    } satisfies Execution["state"];
    const running = observe(observe(initialState()), {
      state: { started_at, status: "running" },
    });
    for (const state of [
      observe(running, { state: completed }),
      observe(initialState(), { state: completed }),
    ]) {
      expect(
        state.runMap.get(queued.run_id)?.cellRuns.get(cellId("cell")),
      ).toEqual({
        cellId: "cell",
        executionId: "e1",
        code: "print(1)",
        startTime: 100,
        elapsedTime: 2,
        status: "interrupted",
      });
    }
    expect(
      observe(running, {
        state: { ...completed, outcome: { kind: "succeeded" } },
      })
        .runMap.get(queued.run_id)
        ?.cellRuns.get(cellId("cell"))?.status,
    ).toBe("success");
  });

  it.each(["upstream-stopped", "superseded"])(
    "shows %s as skipped",
    (reason) => {
      const state = observe(initialState(), {
        state: {
          status: "completed",
          started_at: null,
          completed_at: null,
          depends_on: {},
          outcome: {
            kind: "skipped",
            reason,
            related: [],
            message: "Did not run",
          },
        },
      });
      expect(
        state.runMap.get(queued.run_id)?.cellRuns.get(cellId("cell"))?.status,
      ).toBe("skipped");
    },
  );

  it("keeps known source only for the execution that ran it", () => {
    const state = observe(initialState());
    for (const [id, preview] of [
      ["e1", "print(1)"],
      ["e2", ""],
    ]) {
      const next = reducer(state, {
        type: "addExecution",
        payload: {
          record: { ...queued, id },
          code: undefined,
          receivedAt: 100,
        },
      });
      expect(
        next.runMap.get(queued.run_id)?.cellRuns.get(cellId("cell"))?.code,
      ).toBe(preview);
    }
  });

  it("keeps bounded history and code previews", () => {
    let state = initialState();
    for (let i = 0; i <= MAX_RUNS; i++) {
      state = observe(
        state,
        { run_id: runId(String(i)) },
        "x".repeat(MAX_CODE_LENGTH + 1),
      );
    }
    expect(state.runMap.size).toBe(MAX_RUNS);
    expect(state.runIds[0]).toBe(String(MAX_RUNS));
    expect(state.runMap.has(runId("0"))).toBe(false);
    expect(
      state.runMap.get(state.runIds[0])?.cellRuns.get(cellId("cell"))?.code
        .length,
    ).toBe(MAX_CODE_LENGTH);
    expect(
      reducer(state, { type: "removeRun", payload: state.runIds[0] }).runIds
        .length,
    ).toBe(MAX_RUNS - 1);
    expect(reducer(state, { type: "clearRuns", payload: undefined })).toEqual(
      initialState(),
    );
  });

  it("omits scratch, unowned executions, and runs containing only markdown", () => {
    const initial = initialState();
    expect(observe(initial, { cell_id: null })).toBe(initial);
    expect(observe(initial, { run_id: null })).toBe(initial);
    const markdown = 'mo.md("""hello""")';
    expect(isPureMarkdown(markdown)).toBe(true);
    expect(observe(initial, {}, markdown)).toBe(initial);
    expect(
      observe(observe(initial), { cell_id: cellId("md") }, markdown).runMap.get(
        queued.run_id,
      )?.cellRuns.size,
    ).toBe(2);
  });
});
