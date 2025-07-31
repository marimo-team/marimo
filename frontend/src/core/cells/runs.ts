/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { TypedString } from "@/utils/typed";
import type { CellMessage } from "../kernel/messages";
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
  cellRuns: ReadonlyMap<CellId, CellRun>;
  runStartTime: number;
}

export interface RunsState {
  runIds: RunId[];
  runMap: ReadonlyMap<RunId, Run>;
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

    const existingRun = state.runMap.get(runId);
    // If it is a brand new run and the cell code is "pure markdown",
    // we don't want to show the trace since it's not helpful.
    // This spams the tracing because we re-render pure markdown on keystrokes.
    if (!existingRun && isPureMarkdown(code)) {
      return state;
    }

    // We determine if the cell operation errored by looking at the output
    const erroredOutput =
      cellOperation.output &&
      (cellOperation.output.channel === "marimo-error" ||
        cellOperation.output.channel === "stderr");

    let status: CellRun["status"] = erroredOutput
      ? "error"
      : cellOperation.status === "queued"
        ? "queued"
        : cellOperation.status === "running"
          ? "running"
          : "success";

    // Create new run if needed
    if (!existingRun) {
      const newRun: Run = {
        runId,
        cellRuns: new Map([
          [
            cellOperation.cell_id as CellId,
            {
              cellId: cellOperation.cell_id as CellId,
              code: code.slice(0, MAX_CODE_LENGTH),
              elapsedTime: 0,
              status: status,
              startTime: cellOperation.timestamp,
            },
          ],
        ]),
        runStartTime: cellOperation.timestamp,
      };

      // Manage run history size
      const runIds = [runId, ...state.runIds];
      const nextRunMap = new Map(state.runMap);
      if (runIds.length > MAX_RUNS) {
        const oldestRunId = runIds.pop();
        if (oldestRunId) {
          nextRunMap.delete(oldestRunId);
        }
      }

      nextRunMap.set(runId, newRun);
      return {
        runIds,
        runMap: nextRunMap,
      };
    }

    // Update existing run
    const nextCellRuns = new Map(existingRun.cellRuns);
    const existingCellRun = nextCellRuns.get(cellOperation.cell_id as CellId);

    // Early return if nothing changed
    if (
      existingCellRun &&
      !erroredOutput &&
      cellOperation.status === "queued"
    ) {
      return state;
    }

    if (existingCellRun) {
      const hasErroredPreviously = existingCellRun.status === "error";

      // Compute new status and timing
      status = hasErroredPreviously || erroredOutput ? "error" : status;

      const startTime =
        cellOperation.status === "running"
          ? cellOperation.timestamp
          : existingCellRun.startTime;

      const elapsedTime =
        status === "success" || status === "error"
          ? cellOperation.timestamp - existingCellRun.startTime
          : undefined;

      nextCellRuns.set(cellOperation.cell_id as CellId, {
        ...existingCellRun,
        startTime,
        elapsedTime,
        status,
      });
    } else {
      nextCellRuns.set(cellOperation.cell_id as CellId, {
        cellId: cellOperation.cell_id as CellId,
        code: code.slice(0, MAX_CODE_LENGTH),
        elapsedTime: 0,
        status: status,
        startTime: cellOperation.timestamp,
      });
    }

    const nextRunMap = new Map(state.runMap);
    nextRunMap.set(runId, {
      ...existingRun,
      cellRuns: nextCellRuns,
    });

    return {
      ...state,
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
