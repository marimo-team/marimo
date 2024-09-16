/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "./ids";
import { arrayShallowEquals } from "@/utils/arrays";
import { Objects } from "@/utils/objects";
import type { EditorView } from "@codemirror/view";
import type { LayoutState } from "../layout/layout";
import { isEqual } from "lodash-es";
import {
  type NotebookState,
  type LastSavedNotebook,
  staleCellIds,
} from "./cells";
import { getAppConfig } from "../config/config";

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

export function notebookNeedsSave(
  state: NotebookState,
  layout: LayoutState,
  lastSavedNotebook: LastSavedNotebook | undefined,
) {
  if (!lastSavedNotebook) {
    return false;
  }
  const { cellIds, cellData } = state;
  const data = cellIds.inOrderIds.map((cellId) => cellData[cellId]);
  const codes = data.map((d) => d.code);
  const configs = data.map((d) => d.config);
  const names = data.map((d) => d.name);
  return (
    !arrayShallowEquals(codes, lastSavedNotebook.codes) ||
    !arrayShallowEquals(configs, lastSavedNotebook.configs) ||
    !arrayShallowEquals(names, lastSavedNotebook.names) ||
    !isEqual(layout.selectedLayout, lastSavedNotebook.layout.selectedLayout) ||
    !isEqual(layout.layoutData, lastSavedNotebook.layout.layoutData)
  );
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
  return cellIds.inOrderIds
    .map((cellId) => cellData[cellId])
    .filter((cell) => cell.config.disabled);
}

export function enabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  return cellIds.inOrderIds
    .map((cellId) => cellData[cellId])
    .filter((cell) => !cell.config.disabled);
}

export function canUndoDeletes(state: NotebookState) {
  return state.history.length > 0;
}

/**
 * Get the status of the descendants of the given cell.
 */
export function getDescendantsStatus(state: NotebookState, cellId: CellId) {
  const descendants = state.cellIds.getDescendants(cellId);
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

export function notebookHasColumns() {
  const appConfig = getAppConfig();
  return appConfig.width === "columns";
}

export function getCellColumn(state: NotebookState, cellIndex: number) {
  let columnIndex = 0;
  let columnBreakpoint = state.columnBreakpoints[0];

  for (const [index, breakpoint] of state.columnBreakpoints.entries()) {
    if (cellIndex < breakpoint) {
      break;
    }
    columnIndex = index;
    columnBreakpoint = breakpoint;
  }

  return [columnIndex, columnBreakpoint];
}

export function updateColumnBreakpoints(
  state: NotebookState,
  cellIndex: number,
  increment: boolean,
) {
  state.columnBreakpoints.forEach((breakpoint, i) => {
    if (breakpoint >= cellIndex) {
      if (increment) {
        state.columnBreakpoints[i] += 1;
      } else {
        state.columnBreakpoints[i] -= 1;
      }
    }
  });
}
