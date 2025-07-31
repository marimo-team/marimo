/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it } from "vitest";
import type { CellMessage } from "@/core/kernel/messages";
import { invariant } from "@/utils/invariant";
import {
  exportedForTesting,
  MAX_CODE_LENGTH,
  MAX_RUNS,
  type RunId,
  type RunsState,
} from "../runs";

const { reducer, initialState, isPureMarkdown } = exportedForTesting;

function first<T>(map: ReadonlyMap<string, T> | undefined): T {
  invariant(map, "Map is undefined");
  return map.values().next().value as T;
}

describe("RunsState Reducer", () => {
  let state: RunsState;

  const runId = "run1" as RunId;
  const cellId = "cell1";
  const timestamp = Date.now();
  const code = "print('Hello World')";

  const cellOperation: CellMessage = {
    run_id: runId,
    cell_id: cellId,
    timestamp,
    status: "queued",
  };

  function addQueuedCell(): RunsState {
    return reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: cellOperation,
        code: "print('Hello World')",
      },
    });
  }

  beforeEach(() => {
    state = initialState();
  });

  it("should initialize with an empty state", () => {
    expect(state.runIds).toEqual([]);
    expect(state.runMap.size).toBe(0);
  });

  it("should add a cell operation to a new run", () => {
    const nextState = addQueuedCell();

    expect(nextState.runIds).toEqual([runId]);
    expect(nextState.runMap.get(runId)).toEqual({
      runId,
      runStartTime: timestamp,
      cellRuns: new Map([
        [
          cellId,
          {
            cellId,
            code: code.slice(0, MAX_CODE_LENGTH),
            elapsedTime: 0,
            startTime: timestamp,
            status: "queued",
          },
        ],
      ]),
    });
  });

  it("should clear all runs", () => {
    const intermediateState = addQueuedCell();

    const clearedState = reducer(intermediateState, {
      type: "clearRuns",
      payload: undefined,
    });

    expect(clearedState.runIds).toEqual([]);
    expect(clearedState.runMap.size).toBe(0);
  });

  it("should remove a specific run by ID", () => {
    const runId1 = "run1" as RunId;
    const runId2 = "run2" as RunId;
    const timestamp = Date.now();

    let intermediateState = addQueuedCell();

    intermediateState = reducer(intermediateState, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId2,
          cell_id: "cell2",
          timestamp,
          status: "queued",
        },
        code: "console.log('Run 2');",
      },
    });

    const nextState = reducer(intermediateState, {
      type: "removeRun",
      payload: runId1,
    });

    expect(nextState.runIds).toEqual([runId2]);
    expect(nextState.runMap.has(runId1)).toBe(false);
  });

  it("should update an existing run with a new cell operation", () => {
    const state = addQueuedCell();

    const runStartTimestamp = timestamp + 1000;
    const updatedState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp: timestamp + 1000,
          status: "running",
        },
        code: "console.log('Hello World');",
      },
    });

    expect(updatedState.runIds).toEqual([runId]);
    expect(first(updatedState.runMap.get(runId)?.cellRuns).status).toBe(
      "running",
    );
    expect(first(updatedState.runMap.get(runId)?.cellRuns).startTime).toBe(
      runStartTimestamp,
    );

    const successState = reducer(updatedState, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp: runStartTimestamp + 5000,
          status: "success",
        },
        code: "console.log('Hello World');",
      },
    });

    expect(successState.runIds).toEqual([runId]);
    expect(first(successState.runMap.get(runId)?.cellRuns).status).toBe(
      "success",
    );
    expect(first(successState.runMap.get(runId)?.cellRuns).startTime).toBe(
      runStartTimestamp,
    );
    expect(first(successState.runMap.get(runId)?.cellRuns).elapsedTime).toBe(
      5000,
    );
  });

  it("should limit the number of runs to MAX_RUNS", () => {
    for (let i = 1; i <= MAX_RUNS + 1; i++) {
      state = reducer(state, {
        type: "addCellOperation",
        payload: {
          cellOperation: {
            run_id: `run${i}`,
            cell_id: `cell${i}`,
            timestamp: timestamp,
            status: "queued",
          },
          code: "console.log('Hello World');",
        },
      });
    }

    expect(state.runIds.length).toBe(MAX_RUNS);
    expect(state.runMap.size).toBe(MAX_RUNS);

    // Oldest run should be removed
    expect(state.runIds).not.toContain("run1");
    expect(state.runMap.has("run1" as RunId)).toBe(false);
  });

  it("should truncate code to MAX_CODE_LENGTH", () => {
    const longCode = "a".repeat(MAX_CODE_LENGTH + 10);
    const truncatedCode = longCode.slice(0, MAX_CODE_LENGTH);

    const nextState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp,
          status: "queued",
        },
        code: longCode,
      },
    });

    expect(first(nextState.runMap.get(runId)?.cellRuns).code).toBe(
      truncatedCode,
    );
  });

  it("should update the run status to error when stderr occurs", () => {
    const state = addQueuedCell();

    const errorTimestamp = timestamp + 2000;
    const errorState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp: errorTimestamp,
          status: "running",
          output: {
            channel: "stderr",
            text: "Error occurred",
          },
        },
        code: "console.log('Hello World');",
      },
    });

    expect(errorState.runIds).toEqual([runId]);
    expect(first(errorState.runMap.get(runId)?.cellRuns).status).toBe("error");
    expect(first(errorState.runMap.get(runId)?.cellRuns).elapsedTime).toBe(
      errorTimestamp - timestamp,
    );
  });

  it("should update the run status to error when marimo-error occurs", () => {
    const state = addQueuedCell();

    const errorTimestamp = timestamp + 2000;
    const errorState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp: errorTimestamp,
          status: "running",
          output: {
            channel: "marimo-error",
            text: "Error occurred",
          },
        },
        code: "console.log('Hello World');",
      },
    });

    expect(errorState.runIds).toEqual([runId]);
    expect(first(errorState.runMap.get(runId)?.cellRuns).status).toBe("error");
    expect(first(errorState.runMap.get(runId)?.cellRuns).elapsedTime).toBe(
      errorTimestamp - timestamp,
    );
  });

  it("should maintain status as error when there was a previous error", () => {
    const erroredState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp,
          output: {
            channel: "marimo-error",
          },
        },
        code: "console.log('Hello World');",
      },
    });

    const finalState = reducer(erroredState, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp: timestamp + 2000,
          status: "running", // shouldn't happen
        },
        code: "console.log('Hello World');",
      },
    });

    expect(finalState.runIds).toEqual([runId]);
    expect(first(finalState.runMap.get(runId)?.cellRuns).status).toBe("error");
  });

  it("should order runs from newest to oldest", () => {
    const runId2 = "run2" as RunId;
    const runId3 = "run3" as RunId;
    const timestamp = Date.now();

    let intermediateState = addQueuedCell();

    intermediateState = reducer(intermediateState, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId2,
          cell_id: "cell2",
          timestamp: timestamp + 1000,
          status: "queued",
        },
        code: "console.log('Run 2');",
      },
    });

    const finalState = reducer(intermediateState, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId3,
          cell_id: "cell3",
          timestamp: timestamp + 2000,
          status: "queued",
        },
        code: "console.log('Run 3');",
      },
    });

    expect(finalState.runIds).toEqual([runId3, runId2, runId]);
  });

  it("should create a new run object when adding a cell operation", () => {
    const state1 = addQueuedCell();
    const run1 = state1.runMap.get(runId);

    const state2 = reducer(state1, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: "cell2",
          timestamp: timestamp + 1000,
          status: "queued",
        },
        code: "print('Another cell')",
      },
    });

    const run2 = state2.runMap.get(runId);
    expect(run2).not.toBe(run1);
    expect(run2?.cellRuns).not.toBe(run1?.cellRuns);
  });

  it("should create new run object when updating cell status", () => {
    const state1 = addQueuedCell();
    const run1 = state1.runMap.get(runId);

    const state2 = reducer(state1, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp: timestamp + 1000,
          status: "running",
        },
        code: code,
      },
    });

    const run2 = state2.runMap.get(runId);
    expect(run2).not.toBe(run1);
    expect(run2?.cellRuns).not.toBe(run1?.cellRuns);
  });

  it("should skip markdown for first run", () => {
    const markdownState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp,
          status: "queued",
        },
        code: 'mo.md("""# Hello""")',
      },
    });

    expect(markdownState.runIds).toEqual([]);
    expect(markdownState.runMap.size).toBe(0);
  });

  it("should not skip markdown if first run was not markdown", () => {
    // Add non-markdown run first
    let nextState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp,
          status: "queued",
        },
        code: "print('hello')",
      },
    });

    // Add markdown run second
    nextState = reducer(nextState, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: "cell2",
          timestamp: timestamp + 1000,
          status: "queued",
        },
        code: 'mo.md("""# Hello""")',
      },
    });

    expect(nextState.runIds).toEqual([runId]);
    expect(nextState.runMap.size).toBe(1);
    expect(nextState.runMap.get(runId)?.cellRuns.size).toBe(2);
  });
});

describe("isPureMarkdown", () => {
  it("should return true for pure markdown", () => {
    expect(isPureMarkdown("mo.md(r'''")).toBe(true);
    expect(isPureMarkdown('mo.md(r"""')).toBe(true);
    expect(isPureMarkdown("mo.md('''")).toBe(true);
    expect(isPureMarkdown('mo.md("""')).toBe(true);

    expect(isPureMarkdown("mo.md(\nr'''")).toBe(true);
    expect(isPureMarkdown('mo.md(\nr"""')).toBe(true);
    expect(isPureMarkdown("mo.md(\n'''")).toBe(true);
    expect(isPureMarkdown('mo.md(\n"""')).toBe(true);
  });

  it("should return false for non-markdown", () => {
    expect(isPureMarkdown("mo.md(f'''")).toBe(false);
    expect(isPureMarkdown('mo.md(f"""')).toBe(false);
  });
});
