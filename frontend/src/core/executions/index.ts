/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Cell status, timing, and output, as the editor reads them.
 *
 * The host's notebook stream is the source of truth. Its runs, executions,
 * and results say what every cell is doing. The atoms here derive views
 * from that stream, adding only what the host cannot know yet, such as a
 * run this browser has asked for but not heard back about.
 */

export {
  cellExecutionInputsAtom,
  cellFreshnessAtom,
  cellOutputInputsAtom,
  clearCellOutputs,
  notebookIsRunningAtom,
  notebookQueuedOrRunningCountAtom,
  observeCellMessage,
  runtimeStatusAtom,
  waitForRuntimeRunning,
} from "./atoms";
export type { CellFreshness, CellFreshnessLookup } from "./freshness";
export { replyInput } from "./input";
export { runCells, syncEdits } from "./run";
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
