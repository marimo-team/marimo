/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import {
  type CellError,
  type CellExecutionInputs,
  type CellExecutionView,
  type CellFreshness,
  type CellFreshnessLookup,
  type CellOutput,
  cellExecutionView,
} from "@/core/executions";
import type { Executions } from "@/core/notebook/replica";
import { Objects } from "@/utils/objects";
import { isErrorMime } from "../mime";
import type { NotebookState } from "./cells";
import type { CellId } from "./ids";

export function notebookNeedsRun(
  state: NotebookState,
  executions: CellExecutionInputs,
  freshness: CellFreshnessLookup,
) {
  return staleCellIds(state, executions, freshness).length > 0;
}

export function notebookCells(state: NotebookState) {
  return state.cellIds.map((cellId) => state.cellData[cellId]);
}

export function notebookCellEditorViews({ cellHandles }: NotebookState) {
  const views: Record<CellId, EditorView> = {};
  for (const [cell, ref] of Objects.entries(cellHandles)) {
    if (!ref.current?.editorView) {
      continue;
    }
    views[cell] = ref.current.editorView;
  }
  return views;
}

export function disabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  const disabledCells: CellId[] = [];
  for (const cellId of cellIds) {
    const cell = cellData[cellId];
    if (cell.config.disabled) {
      disabledCells.push(cellId);
    }
  }
  return disabledCells;
}

export function enabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  const enabledCells: CellId[] = [];
  for (const cellId of cellIds) {
    const cell = cellData[cellId];
    if (!cell.config.disabled) {
      enabledCells.push(cellId);
    }
  }
  return enabledCells;
}

export function canUndoDeletes(state: NotebookState) {
  return state.history.length > 0;
}

/**
 * Label for the undo action based on the last history entry type.
 */
export function getUndoLabel(state: NotebookState): string {
  const last = state.history[state.history.length - 1];
  if (!last) {
    return "Undo cell deletion";
  }
  return last.type === "move" ? "Undo move" : "Undo cell deletion";
}

/**
 * Summarize the run state of the given descendants, whether any is stale,
 * errored, or running.
 */
export function getDescendantsStatus(
  executions: CellExecutionInputs,
  freshness: CellFreshnessLookup,
  descendants: readonly CellId[],
) {
  const views = descendants.map((id) => cellExecutionView(executions, id));
  const stale = descendants.some(
    (id) => freshness(id).sourceChanged || freshness(id).inputsChanged,
  );
  const errored = views.some((view) => view.outcome === "error");
  const runningOrQueued = views.some(
    (view) => view.status === "running" || view.status === "queued",
  );

  return {
    stale,
    errored,
    runningOrQueued,
  };
}

/**
 * Cells that are stale and can be run.
 */
export function staleCellIds(
  state: NotebookState,
  executions: CellExecutionInputs,
  freshness: CellFreshnessLookup,
) {
  const { cellIds, cellData } = state;
  return cellIds.filter((cellId) => {
    const execution = cellExecutionView(executions, cellId);
    if (execution.status !== "idle") {
      // A run in progress covers the source it was asked for. Only an edit
      // since then, visible once the host has planned the run, needs another.
      return (
        inFlight(executions.executions, cellId) &&
        freshness(cellId).sourceChanged
      );
    }
    return (
      isUninstantiated(execution) ||
      cellNeedsRun({
        freshness: freshness(cellId),
        interrupted: execution.outcome === "interrupted",
        disabled: cellData[cellId].config.disabled,
        blocked: execution.blocked,
      })
    );
  });
}

/** Whether the host holds a planned or started execution of the cell that has not completed. */
function inFlight(executions: Executions, cellId: CellId): boolean {
  const latest = executions.latest.get(cellId);
  const record =
    latest === undefined
      ? undefined
      : executions.executions.get(latest)?.record;
  return record !== undefined && record.status !== "completed";
}

/** Whether a cell has never run: no result to show and nothing in flight. */
export function isUninstantiated({
  status,
  outcome,
}: Pick<CellExecutionView, "status" | "outcome">) {
  return outcome === null && status !== "queued" && status !== "running";
}

/**
 * Whether a cell needs to be run: its source changed, its last run was
 * interrupted, or an input changed and the cell can run. A disabled cell,
 * or one blocked by a disabled ancestor, is not flagged for changed inputs
 * until it can run again.
 */
export function cellNeedsRun({
  freshness,
  interrupted,
  disabled,
  blocked,
}: {
  freshness: CellFreshness;
  interrupted: boolean;
  disabled: boolean | undefined;
  blocked: boolean;
}): boolean {
  return (
    freshness.sourceChanged ||
    interrupted ||
    (freshness.inputsChanged && !(disabled || blocked))
  );
}

export function cellStatusClasses({
  needsRun,
  errored,
  stopped,
  disabled,
  blocked,
}: {
  needsRun: boolean;
  errored: boolean;
  stopped: boolean;
  disabled: boolean | undefined;
  blocked: boolean;
}) {
  return {
    "needs-run": needsRun,
    "has-error": errored,
    stopped,
    disabled: disabled ?? false,
    stale: blocked,
  };
}

/**
 * Status classes for a published cell (read or present mode, output only).
 */
export function publishedCellClasses({
  errored,
  stopped,
}: {
  errored: boolean;
  stopped: boolean;
}) {
  return {
    published: true,
    "has-error": errored,
    stopped: stopped,
  };
}

/**
 * Whether a published cell (read or present mode) should be hidden.
 *
 * Errored, interrupted, and stopped cells (and error outputs) are hidden in
 * published views, unless `show_tracebacks` is enabled and the output carries
 * an exception traceback to display inline.
 */
export function shouldHidePublishedCell({
  errored,
  interrupted,
  stopped,
  output,
  showErrorTracebacks,
}: {
  errored: boolean;
  interrupted: boolean;
  stopped: boolean;
  output: CellOutput | null;
  showErrorTracebacks: boolean;
}): boolean {
  const outputIsError = isErrorMime(output?.mimetype);
  const hasTraceback =
    showErrorTracebacks &&
    outputIsError &&
    Array.isArray(output?.data) &&
    output.data.some(
      (e: CellError) =>
        e.type === "exception" && "traceback" in e && e.traceback,
    );
  return (errored || interrupted || stopped || outputIsError) && !hasTraceback;
}
