/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { CellMessage } from "../kernel/messages";
import type { TypedString } from "@/utils/typed";
import type { CellId } from "./ids";
export type RunId = TypedString<"RunId">;

export interface CellRun {
  cellId: CellId;
  code: string;
  elapsedTime?: number;
  startTime: number;
  status: "success" | "error" | "queued" | "running";
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

export const MAX_RUNS = 50;
export const MAX_CODE_LENGTH = 200;

const {
  reducer,
  createActions,
  valueAtom: runsAtom,
  useActions: useRunsActions,
} = createReducerAndAtoms(initialState, {
  addCellOperation: (
    state: RunsState,
    opts: { cellOperation: CellMessage; code: string },
  ): RunsState => {
    const { cellOperation, code } = opts;
    const runId = cellOperation.run_id as RunId | undefined;
    if (!runId) {
      return state;
    }
    let runIds: RunId[];

    let run = state.runMap.get(runId);
    if (run) {
      runIds = state.runIds;
      // Shallow copy the run to avoid mutating the existing run
      run = { ...run };
    } else {
      // If it is a brand new run and the cell code is "pure markdown",
      // we don't want to show the trace since it's not helpful.
      // This spams the tracing because we re-render pure markdown on keystrokes.
      if (isPureMarkdown(code)) {
        return state;
      }

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

    // We determine if the cell operation errored by looking at the output
    const erroredOutput =
      cellOperation.output &&
      (cellOperation.output.channel === "marimo-error" ||
        cellOperation.output.channel === "stderr");

    const nextRuns: CellRun[] = [];
    let found = false;
    for (const existingCellRun of run.cellRuns) {
      if (existingCellRun.cellId === cellOperation.cell_id) {
        const hasErroredPreviously = existingCellRun.status === "error";
        let status: CellRun["status"];
        let startTime = existingCellRun.startTime;

        if (hasErroredPreviously || erroredOutput) {
          status = "error";
        } else if (cellOperation.status === "queued") {
          status = "queued";
        } else if (cellOperation.status === "running") {
          status = "running";
          startTime = cellOperation.timestamp;
        } else {
          status = "success";
        }

        let elapsedTime: number | undefined = undefined;
        if (status === "success" || status === "error") {
          elapsedTime = cellOperation.timestamp - existingCellRun.startTime;
        }

        nextRuns.push({
          ...existingCellRun,
          startTime: startTime,
          elapsedTime: elapsedTime,
          status: status,
        });
        found = true;
      } else {
        nextRuns.push(existingCellRun);
      }
    }
    if (!found) {
      let status: CellRun["status"];

      if (erroredOutput) {
        status = "error";
      } else if (cellOperation.status === "queued") {
        status = "queued";
      } else if (cellOperation.status === "running") {
        status = "running";
      } else {
        status = "success";
      }

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
  clearRuns: (state: RunsState): RunsState => ({
    ...state,
    runIds: [],
    runMap: new Map(),
  }),
  removeRun: (state: RunsState, runId: RunId): RunsState => {
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

const MARKDOWN_REGEX = /mo\.md\(\s*r?('''|""")/;
function isPureMarkdown(code: string): boolean {
  return code.startsWith("mo.md(") && MARKDOWN_REGEX.test(code);
}

export { runsAtom, useRunsActions };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
  isPureMarkdown,
};
