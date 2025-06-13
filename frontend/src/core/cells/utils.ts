/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { Objects } from "@/utils/objects";
import type { RuntimeState } from "../network/types";
import type { NotebookState } from "./cells";
import type { CellId } from "./ids";

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
    if (!ref.current) {
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
 * Get the status of the descendants of the given cell.
 */
export function getDescendantsStatus(state: NotebookState, cellId: CellId) {
  const column = state.cellIds.findWithId(cellId);
  const descendants = column.getDescendants(cellId);
  const stale = descendants.some(
    (id) => state.cellRuntime[id]?.staleInputs || state.cellData[id]?.edited,
  );
  const errored = descendants.some((id) => state.cellRuntime[id]?.errored);
  const runningOrQueued = descendants.some(
    (id) =>
      state.cellRuntime[id]?.status === "running" ||
      state.cellRuntime[id]?.status === "queued",
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
export function staleCellIds(state: NotebookState) {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.inOrderIds.filter(
    (cellId) =>
      isUninstantiated({
        // runElapstedTimeMs is what we've seen in this session
        executionTime:
          cellRuntime[cellId].runElapsedTimeMs ??
          // lastExecutionTime is what was seen on session start/resume
          cellData[cellId].lastExecutionTime,
        status: cellRuntime[cellId].status,
        errored: cellRuntime[cellId].errored,
        interrupted: cellRuntime[cellId].interrupted,
        stopped: cellRuntime[cellId].stopped,
      }) ||
      cellData[cellId].edited ||
      cellRuntime[cellId].interrupted ||
      (cellRuntime[cellId].staleInputs &&
        // if a cell is disabled, it can't be run ...
        !(
          cellRuntime[cellId].status === "disabled-transitively" ||
          cellData[cellId].config.disabled
        )),
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
