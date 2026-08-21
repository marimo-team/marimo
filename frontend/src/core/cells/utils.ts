/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { Objects } from "@/utils/objects";
import type { MarimoError, OutputMessage } from "../kernel/messages";
import { isErrorMime } from "../mime";
import type { RuntimeState } from "../network/types";
import type { NotebookState } from "./cells";
import type { CellId } from "./ids";
import { deriveCellSemanticState } from "./semantic-state";

export function notebookIsRunning(state: NotebookState) {
  return Object.values(state.cellRuntime).some(
    (cell) => cell.status === "running",
  );
}

export function notebookQueueOrRunningCount(state: NotebookState) {
  return Object.values(state.cellRuntime).filter(
    (cell) => cell.status === "running" || cell.status === "queued",
  ).length;
}

export function notebookNeedsRun(state: NotebookState) {
  return staleCellIds(state).length > 0;
}

export function notebookCells(state: NotebookState) {
  return state.cellIds.inOrderIds.map((cellId) => state.cellData[cellId]);
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
  for (const cellId of cellIds.inOrderIds) {
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
  for (const cellId of cellIds.inOrderIds) {
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
 * Get the status of the descendants of the given cell.
 */
export function getDescendantsStatus(state: NotebookState, cellId: CellId) {
  const column = state.cellIds.findWithId(cellId);
  const descendants = column.getDescendants(cellId);
  const semanticStates = descendants.flatMap((id) => {
    const data = state.cellData[id];
    const runtime = state.cellRuntime[id];
    return data && runtime ? [deriveCellSemanticState(data, runtime)] : [];
  });
  const outdated = semanticStates.some(
    (cell) =>
      cell.freshness.kind !== "current" || cell.lastRun.kind === "interrupted",
  );
  const failed = semanticStates.some((cell) => cell.lastRun.kind === "failed");
  const running = semanticStates.some((cell) => cell.phase.kind === "running");
  const queued = semanticStates.some((cell) => cell.phase.kind === "queued");
  const blocked = semanticStates.some(
    (cell) => cell.availability.kind === "blocked",
  );
  const stopped = semanticStates.some(
    (cell) => cell.lastRun.kind === "stopped",
  );

  return {
    outdated,
    failed,
    running,
    queued,
    blocked,
    stopped,
  };
}

/** Cells with pending work that can be run or synchronized. */
export function staleCellIds(state: NotebookState) {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.inOrderIds.filter(
    (cellId) =>
      deriveCellSemanticState(cellData[cellId], cellRuntime[cellId])
        .shouldSchedule,
  );
}

export function isUninstantiated({
  executionTime,
  status,
  errored,
  interrupted,
  stopped,
}: {
  executionTime: number | null;
  status: RuntimeState;
  errored: boolean;
  interrupted: boolean;
  stopped: boolean;
}) {
  return (
    // hasn't run ...
    executionTime === null &&
    // isn't currently queued/running &&
    status !== "queued" &&
    status !== "running" &&
    // and isn't in an error state.
    !(errored || interrupted || stopped)
  );
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
