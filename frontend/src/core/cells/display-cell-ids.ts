/* Copyright 2026 Marimo. All rights reserved. */

import { CollapsibleTree, MultiColumn } from "@/utils/id-tree";
import type { NotebookState } from "./cells";
import type { CellId } from "./ids";

const displayCellsCache = new WeakMap<
  MultiColumn<CellId>,
  { previous: MultiColumn<CellId> | null; display: MultiColumn<CellId> }
>();

export function getDisplayCellIds(state: NotebookState): MultiColumn<CellId> {
  if (state.multiColumn) {
    return state.cellIds;
  }
  const layouts = displayCellsCache.get(state.cellIds);
  if (layouts?.previous === state.verticalCellIds) {
    return layouts.display;
  }
  const previousIds = state.verticalCellIds?.inOrderIds;
  const ids = state.cellIds.inOrderIds;
  if (
    previousIds?.length === ids.length &&
    ids.every((id, index) => id === previousIds[index])
  ) {
    return state.verticalCellIds ?? state.cellIds;
  }
  const merged = state.cellIds.mergeAllColumns();
  const previous = state.verticalCellIds?.at(0) ?? merged.at(0);
  const display = new MultiColumn([
    CollapsibleTree.fromWithPreviousShape(ids, previous),
  ]);
  displayCellsCache.set(state.cellIds, {
    previous: state.verticalCellIds,
    display,
  });
  return display;
}
