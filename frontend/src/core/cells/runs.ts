/* Copyright 2026 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type {
  ExecutionOutput as Execution,
  RunId,
} from "@marimo-team/client/protocol";
import { completedAt, startedAt } from "@/core/notebook/replica";
import type { CellId } from "./ids";
export type { RunId };

export interface CellRun {
  cellId: CellId;
  executionId: Execution["id"];
  code: string;
  elapsedTime?: number;
  startTime: number;
  status:
    | "queued"
    | "running"
    | "success"
    | "error"
    | "skipped"
    | "interrupted";
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

function traceStatus(record: Execution): CellRun["status"] {
  if (record.state.status !== "completed") {
    return record.state.status;
  }
  switch (record.state.outcome.kind) {
    case "succeeded":
      return "success";
    case "failed":
      return "error";
    case "cancelled":
      return "interrupted";
    case "skipped":
      return "skipped";
  }
}

const {
  reducer,
  createActions,
  valueAtom: runsAtom,
  useActions: useRunsActions,
} = createReducerAndAtoms(initialState, {
  addExecution: (
    state: RunsState,
    {
      record,
      code,
      receivedAt,
    }: { record: Execution; code: string | undefined; receivedAt: number },
  ): RunsState => {
    if (record.run_id === null || record.cell_id === null) {
      return state;
    }
    const runId = record.run_id;
    const cellId = record.cell_id;
    const previous = state.runMap.get(runId);
    if (previous === undefined && code !== undefined && isPureMarkdown(code)) {
      return state;
    }
    const cellRuns = new Map(previous?.cellRuns);
    const prior = cellRuns.get(cellId);
    const sameExecution = prior?.executionId === record.id ? prior : undefined;
    const end = completedAt(record);
    const start = startedAt(record);
    const ended = end === null ? undefined : Date.parse(end) / 1000;
    const startTime =
      start === null
        ? (sameExecution?.startTime ?? ended ?? receivedAt)
        : Date.parse(start) / 1000;
    cellRuns.set(cellId, {
      cellId,
      executionId: record.id,
      code: code?.slice(0, MAX_CODE_LENGTH) ?? sameExecution?.code ?? "",
      startTime,
      status: traceStatus(record),
      elapsedTime: ended === undefined ? undefined : ended - startTime,
    });
    const runMap = new Map(state.runMap);
    runMap.set(runId, {
      runId,
      cellRuns,
      runStartTime: previous?.runStartTime ?? startTime,
    });
    if (previous !== undefined) {
      return { ...state, runMap };
    }
    const runIds = [runId, ...state.runIds];
    if (runIds.length > MAX_RUNS) {
      const oldest = runIds.pop();
      if (oldest !== undefined) {
        runMap.delete(oldest);
      }
    }
    return { runIds, runMap };
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
