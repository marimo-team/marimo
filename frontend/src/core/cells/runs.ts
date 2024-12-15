/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { CellMessage } from "../kernel/messages";
import type { TypedString } from "@/utils/typed";
import type { CellId } from "./ids";
export type RunId = TypedString<"RunId">;

export interface CellRun {
  cellId: CellId;
  code: string;
  elapsedTime: number;
  startTime: number;
  status: "success" | "error";
}

export interface Run {
  runId: RunId;
  cellRuns: CellRun[];
  runStartTime: number;
}

export interface RunsState {
  runIds: RunId[];
  runMap: Map<RunId, Run>;
}

function initialState(): RunsState {
  return {
    runIds: [],
    runMap: new Map(),
  };
}

const MAX_RUNS = 100;
const MAX_CODE_LENGTH = 200;

const {
  reducer,
  createActions,
  valueAtom: runsAtom,
  useActions: useRunsActions,
} = createReducerAndAtoms(initialState, {
  addCellOperation: (
    state,
    opts: { cellOperation: CellMessage; code: string },
  ) => {
    console.log("addCellOperation", opts);
    const { cellOperation, code } = opts;
    const runId = cellOperation.run_id as RunId | undefined;
    if (!runId) {
      return state;
    }
    let runIds: RunId[];

    let run = state.runMap.get(runId);
    if (run) {
      runIds = state.runIds;
    } else {
      run = {
        runId: runId,
        cellRuns: [],
        runStartTime: cellOperation.timestamp,
      };

      runIds = [runId, ...state.runIds];
      if (runIds.length > MAX_RUNS) {
        const oldestRunId = runIds.pop();
        if (oldestRunId) {
          state.runMap.delete(oldestRunId);
        }
      }
    }

    // TODO: is this ideal?
    const erroredOutput =
      cellOperation.output &&
      (cellOperation.output.channel === "marimo-error" ||
        cellOperation.output.channel === "stderr");

    const nextRuns: CellRun[] = [];
    let found = false;
    for (const existingCellRun of run.cellRuns) {
      if (existingCellRun.cellId === cellOperation.cell_id) {
        const hasErroredPreviously = existingCellRun.status === "error";
        const status: CellRun["status"] =
          hasErroredPreviously || erroredOutput ? "error" : "success";

        // TODO: Need to update the cell run in place, to maintain order
        nextRuns.push({
          ...existingCellRun,
          elapsedTime: cellOperation.timestamp - existingCellRun.startTime,
          status: status,
        });
        found = true;
      } else {
        nextRuns.push(existingCellRun);
      }
    }
    if (!found) {
      const status: CellRun["status"] = erroredOutput ? "error" : "success";

      nextRuns.push({
        cellId: cellOperation.cell_id as CellId,
        code: code.slice(0, MAX_CODE_LENGTH),
        elapsedTime: 0,
        status: status,
        startTime: cellOperation.timestamp,
      });
    }

    run.cellRuns = nextRuns;

    const nextRunMap = new Map(state.runMap);
    nextRunMap.set(runId, run);

    return {
      ...state,
      runIds: runIds,
      runMap: nextRunMap,
    };
  },
  clearRuns: (state) => ({
    ...state,
    runIds: [],
    runMap: new Map(),
  }),
  removeRun: (state, runId: RunId) => {
    const nextRunIds = state.runIds.filter((id) => id !== runId);
    const nextRunMap = new Map(state.runMap);
    nextRunMap.delete(runId);
    return {
      ...state,
      runIds: nextRunIds,
      runMap: nextRunMap,
    };
  },
});

export { runsAtom, useRunsActions };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
