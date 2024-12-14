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
    let run = state.runMap.get(runId);
    if (!run) {
      run = {
        runId: runId,
        cellRuns: [],
        runStartTime: cellOperation.timestamp,
      };
    }

    const nextRuns: CellRun[] = [];
    let found = false;
    for (const cellRun of run.cellRuns) {
      if (cellRun.cellId === cellOperation.cell_id) {
        nextRuns.push({
          ...cellRun,
          elapsedTime: cellOperation.timestamp - cellRun.startTime,
        });
        found = true;
      } else {
        nextRuns.push(cellRun);
      }
    }
    if (!found) {
      nextRuns.push({
        cellId: cellOperation.cell_id as CellId,
        code: code.slice(0, MAX_CODE_LENGTH),
        elapsedTime: 0,
        // TODO: not actually correct logic
        status: cellOperation.status === "idle" ? "success" : "error",
        startTime: cellOperation.timestamp,
      });
    }

    const nextRunMap = new Map(state.runMap);
    nextRunMap.set(runId, run);

    return {
      ...state,
      runIds: [runId, ...state.runIds.slice(0, MAX_RUNS)],
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
