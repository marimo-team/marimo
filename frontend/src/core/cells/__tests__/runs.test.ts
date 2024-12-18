/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it, beforeEach } from "vitest";
import {
  exportedForTesting,
  MAX_CODE_LENGTH,
  MAX_RUNS,
  type RunId,
  type RunsState,
} from "../runs";
import type { CellMessage } from "@/core/kernel/messages";

describe("RunsState Reducer", () => {
  const { reducer, initialState } = exportedForTesting;

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

  beforeEach(() => {
    state = initialState();
  });

  it("should initialize with an empty state", () => {
    expect(state.runIds).toEqual([]);
    expect(state.runMap.size).toBe(0);
  });

  it("should add a cell operation to a new run", () => {
    const nextState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation,
        code,
      },
    });

    expect(nextState.runIds).toEqual([runId]);
    expect(nextState.runMap.get(runId)).toEqual({
      runId,
      runStartTime: timestamp,
      cellRuns: [
        {
          cellId,
          code: code.slice(0, MAX_CODE_LENGTH),
          elapsedTime: 0,
          startTime: timestamp,
          status: "queued",
        },
      ],
    });
  });

  it("should clear all runs", () => {
    const runId = "run1" as RunId;
    const cellId = "cell1";
    const timestamp = Date.now();

    const intermediateState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp,
          status: "queued",
        },
        code: "console.log('Hello World');",
      },
    });

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

    let intermediateState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId1,
          cell_id: "cell1",
          timestamp,
          status: "queued",
        },
        code: "console.log('Hello World');",
      },
    });

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
    state = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp,
          status: "queued",
        },
        code: "console.log('Hello World');",
      },
    });

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
    expect(updatedState.runMap.get(runId)?.cellRuns[0].status).toBe("running");
    expect(updatedState.runMap.get(runId)?.cellRuns[0].startTime).toBe(
      runStartTimestamp,
    );

    const successState = reducer(state, {
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
    expect(successState.runMap.get(runId)?.cellRuns[0].status).toBe("success");
    expect(successState.runMap.get(runId)?.cellRuns[0].startTime).toBe(
      runStartTimestamp,
    );
    expect(successState.runMap.get(runId)?.cellRuns[0].elapsedTime).toBe(5000);
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

  it("should update the run status to error when an error occurs", () => {
    state = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId,
          cell_id: cellId,
          timestamp,
          status: "queued",
        },
        code: "console.log('Hello World');",
      },
    });

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
    expect(errorState.runMap.get(runId)?.cellRuns[0].status).toBe("error");
    expect(errorState.runMap.get(runId)?.cellRuns[0].elapsedTime).toBe(
      errorTimestamp - timestamp,
    );
  });

  it("should order runs from newest to oldest", () => {
    const runId1 = "run1" as RunId;
    const runId2 = "run2" as RunId;
    const runId3 = "run3" as RunId;
    const timestamp = Date.now();

    let intermediateState = reducer(state, {
      type: "addCellOperation",
      payload: {
        cellOperation: {
          run_id: runId1,
          cell_id: "cell1",
          timestamp,
          status: "queued",
        },
        code: "console.log('Run 1');",
      },
    });

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

    expect(finalState.runIds).toEqual([runId3, runId2, runId1]);
  });
});
