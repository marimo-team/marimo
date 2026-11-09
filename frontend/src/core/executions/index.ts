/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Cell status and timing read from the host's executions.
 *
 * Every atom here is derived, so it can be read but not set. The state
 * behind them changes only through `runCells` and the functions it uses:
 * `submitCells`, `withdrawCells`, and `acceptRun`, plus `observeCellMessage`
 * while cell-ops remain.
 */

export {
  acceptRun,
  cellExecutionInputsAtom,
  cellFreshnessAtom,
  cellOutputInputsAtom,
  clearCellOutputs,
  notebookIsRunningAtom,
  notebookQueuedOrRunningCountAtom,
  observeCellMessage,
  runtimeStatusAtom,
  submitCells,
  waitForRuntimeRunning,
  withdrawCells,
} from "./atoms";
export type { CellFreshness, CellFreshnessLookup } from "./freshness";
export { runCells, syncEdits, waitForRuntime } from "./run";
export {
  useCellExecution,
  useCellFreshness,
  useCellOutline,
  useCellOutput,
  useScratchOutput,
} from "./hooks";
export {
  type CellError,
  type CellOutput,
  cellOutputView,
  type HostDiagnostic,
  scratchOutputView,
} from "./output";
export {
  type CellExecutionInputs,
  type CellExecutionView,
  type CellOutcome,
  type CellRunStatus,
  cellExecutionView,
  onlyScratchRunning,
  runningCellIds,
  scratchStatus,
} from "./select";
