/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import {
  type CellExecutionInputs,
  type CellExecutionView,
  cellExecutionView,
} from "@/core/executions";
import { Objects } from "@/utils/objects";
import type { MarimoError, OutputMessage } from "../kernel/messages";
import { isErrorMime } from "../mime";
import type { NotebookState } from "./cells";
import type { CellId } from "./ids";

export function notebookNeedsRun(
  state: NotebookState,
  executions: CellExecutionInputs,
) {
  return staleCellIds(state, executions).length > 0;
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
  state: NotebookState,
  executions: CellExecutionInputs,
  descendants: readonly CellId[],
) {
  const views = descendants.map((id) => cellExecutionView(executions, id));
  const stale = descendants.some(
    (id) => state.cellRuntime[id]?.staleInputs || state.cellData[id]?.edited,
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
) {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.filter((cellId) => {
    const execution = cellExecutionView(executions, cellId);
    return (
      isUninstantiated(execution) ||
      cellData[cellId].edited ||
      execution.outcome === "interrupted" ||
      (cellRuntime[cellId].staleInputs &&
        // if a cell is disabled, it can't be run ...
        !(execution.blocked || cellData[cellId].config.disabled))
    );
  });
}

/** Whether a cell has never run: no result to show and nothing in flight. */
export function isUninstantiated({
  status,
  outcome,
}: Pick<CellExecutionView, "status" | "outcome">) {
  return outcome === null && status !== "queued" && status !== "running";
}

/**
 * Whether a cell needs to be run given its edited / interrupted / stale
 * inputs, while accounting for ancestor-disabled cells (which should not be
 * flagged as needing a run until re-enabled).
 */
export function cellNeedsRun({
  edited,
  interrupted,
  staleInputs,
  disabled,
  blocked,
}: {
  edited: boolean;
  interrupted: boolean;
  staleInputs: boolean;
  disabled: boolean | undefined;
  blocked: boolean;
}): boolean {
  return edited || interrupted || (staleInputs && !(disabled || blocked));
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
  output: OutputMessage | null;
  showErrorTracebacks: boolean;
}): boolean {
  const outputIsError = isErrorMime(output?.mimetype);
  const hasTraceback =
    showErrorTracebacks &&
    outputIsError &&
    Array.isArray(output?.data) &&
    output.data.some(
      (e: MarimoError) =>
        e.type === "exception" && "traceback" in e && e.traceback,
    );
  return (errored || interrupted || stopped || outputIsError) && !hasTraceback;
}
