/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Reducer-only tests for the Build panel state machine.
 *
 * The panel itself is straightforward presentational glue; what's
 * worth nailing down is that the reducer correctly digests the
 * websocket event stream into the shape the UI binds to. Each test
 * walks one realistic flow.
 */

import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { BuildEventNotification } from "@/core/network/types";
import { applyBuildEvent, type BuildState } from "../atoms";

const INITIAL: BuildState = {
  status: "idle",
  totalCompilable: 0,
  executedCount: 0,
  cellResults: new Map(),
};

const cellId = (id: string) => id as CellId;

const event = (
  buildId: string,
  type: string,
  payload: Record<string, unknown> = {},
): BuildEventNotification => ({
  build_id: buildId,
  event_type: type,
  op: "build-event",
  payload,
});

describe("applyBuildEvent", () => {
  it("counts only compilable cells in totalCompilable", () => {
    let state = INITIAL;
    state = applyBuildEvent(
      state,
      event("b1", "phase_started", { phase: "classify" }),
    );
    state = applyBuildEvent(
      state,
      event("b1", "cell_classified", {
        cell_id: "c1",
        name: "x",
        static_kind: "compilable",
      }),
    );
    state = applyBuildEvent(
      state,
      event("b1", "cell_classified", {
        cell_id: "c2",
        name: "y",
        static_kind: "non_compilable",
      }),
    );
    expect(state.totalCompilable).toBe(1);
  });

  it("transitions a cell through executing → executed → planned", () => {
    let state: BuildState = {
      ...INITIAL,
      buildId: "b1",
      status: "running",
      totalCompilable: 1,
    };
    state = applyBuildEvent(
      state,
      event("b1", "cell_executing", {
        cell_id: "c1",
        name: "_",
        display_name: "build_chart",
      }),
    );
    expect(state.cellResults.get(cellId("c1"))?.state).toBe("executing");
    expect(state.cellResults.get(cellId("c1"))?.displayName).toBe(
      "build_chart",
    );
    // Progress label uses the friendly display_name, not the literal `_`.
    expect(state.currentCellName).toBe("build_chart");

    state = applyBuildEvent(
      state,
      event("b1", "cell_executed", {
        cell_id: "c1",
        name: "_",
        display_name: "build_chart",
        elapsed_ms: 12.5,
      }),
    );
    expect(state.cellResults.get(cellId("c1"))?.state).toBe("executed");
    expect(state.cellResults.get(cellId("c1"))?.elapsedMs).toBe(12.5);
    expect(state.executedCount).toBe(1);
    expect(state.currentCellName).toBeUndefined();

    state = applyBuildEvent(
      state,
      event("b1", "cell_planned", {
        cell_id: "c1",
        name: "x",
        status: "compiled",
      }),
    );
    expect(state.cellResults.get(cellId("c1"))?.final).toBe("compiled");
    // The runtime state from `executed` is preserved through `planned`.
    expect(state.cellResults.get(cellId("c1"))?.elapsedMs).toBe(12.5);
  });

  it("ignores events from a stale build_id", () => {
    const state: BuildState = {
      ...INITIAL,
      buildId: "b2",
      status: "running",
      totalCompilable: 5,
    };
    const next = applyBuildEvent(
      state,
      event("b1", "cell_executed", {
        cell_id: "c1",
        name: "x",
        elapsed_ms: 1,
      }),
    );
    expect(next).toBe(state);
  });

  it("starting a new build resets prior cell state", () => {
    const stale: BuildState = {
      ...INITIAL,
      buildId: "old",
      status: "success",
      totalCompilable: 3,
      executedCount: 3,
      cellResults: new Map([
        [
          cellId("c1"),
          {
            cellId: cellId("c1"),
            name: "x",
            displayName: "x",
            state: "executed" as const,
          },
        ],
      ]),
    };
    const next = applyBuildEvent(
      stale,
      event("new", "phase_started", { phase: "classify" }),
    );
    expect(next.buildId).toBe("new");
    expect(next.status).toBe("running");
    expect(next.totalCompilable).toBe(0);
    expect(next.cellResults.size).toBe(0);
  });

  it("populates the result summary on `done`", () => {
    const state: BuildState = {
      ...INITIAL,
      buildId: "b1",
      status: "running",
      totalCompilable: 2,
      executedCount: 2,
    };
    const next = applyBuildEvent(
      state,
      event("b1", "done", {
        output_dir: "/tmp/out",
        compiled_notebook: "/tmp/out/nb.py",
        artifacts_written: 3,
        artifacts_cached: 1,
        artifacts_deleted: 0,
      }),
    );
    expect(next.status).toBe("success");
    expect(next.result).toEqual({
      outputDir: "/tmp/out",
      compiledNotebook: "/tmp/out/nb.py",
      artifactsWritten: 3,
      artifactsCached: 1,
      artifactsDeleted: 0,
    });
  });

  it("captures error and cancelled terminal states", () => {
    const running: BuildState = {
      ...INITIAL,
      buildId: "b1",
      status: "running",
      totalCompilable: 2,
    };
    const errored = applyBuildEvent(
      running,
      event("b1", "error", { message: "boom", cell_name: "c1" }),
    );
    expect(errored.status).toBe("error");
    expect(errored.error).toEqual({ message: "boom", cellName: "c1" });

    const cancelled = applyBuildEvent(running, event("b1", "cancelled"));
    expect(cancelled.status).toBe("cancelled");
  });
});
