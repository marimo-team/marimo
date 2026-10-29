/* Copyright 2026 Marimo. All rights reserved. */

/** The cells as they appear on the page: by column, with folded sections hidden. */

import { atom, useAtomValue } from "jotai";
import type { CellColumnId } from "@/utils/id-tree";
import { findCollapseRange } from "../dom/outline";
import { notebookAtom } from "./cells";
import type { CellId } from "./ids";
import type { Outline } from "./outline";

/** The headers whose sections the user folded. Only this browser knows. */
export const collapsedAtom = atom<ReadonlySet<CellId>>(new Set<CellId>());

export interface LayoutColumn {
  readonly id: CellColumnId;
  /** Every cell of the column, in order. */
  readonly ids: readonly CellId[];
  /** The cells on the page: those no fold hides. */
  readonly visible: readonly CellId[];
  /** Each folded header and the cells it hides, nested sections included. */
  readonly folds: ReadonlyMap<CellId, readonly CellId[]>;
}

export interface Layout {
  readonly columns: readonly LayoutColumn[];
}

/**
 * The cells each folded header hides. A section runs from its header to the
 * cell before the next header of the same or a higher level, so a folded
 * header inside a folded section is hidden along with its own section.
 */
export function foldSections(
  ids: readonly CellId[],
  outlines: (Outline | null)[],
  collapsed: ReadonlySet<CellId>,
): Map<CellId, readonly CellId[]> {
  const folds = new Map<CellId, readonly CellId[]>();
  ids.forEach((id, index) => {
    const outline = outlines[index];
    if (!collapsed.has(id) || !outline || outline.items.length === 0) {
      return;
    }
    const range = findCollapseRange(index, outlines);
    if (range === null || range[1] === index) {
      return;
    }
    folds.set(id, ids.slice(index + 1, range[1] + 1));
  });
  return folds;
}

export function deriveLayout(
  columns: ReadonlyArray<{ id: CellColumnId; ids: readonly CellId[] }>,
  outlineOf: (id: CellId) => Outline | null,
  collapsed: ReadonlySet<CellId>,
): Layout {
  return {
    columns: columns.map(({ id, ids }) => {
      const folds = foldSections(ids, ids.map(outlineOf), collapsed);
      const hidden = new Set([...folds.values()].flat());
      return { id, ids, visible: ids.filter((c) => !hidden.has(c)), folds };
    }),
  };
}

/**
 * The layout of the notebook's cells.
 *
 * TODO(MO-8028): Order and columns come from the reducer's tree until the
 * arrange family edits the document; then they derive from the document and
 * the column ids this browser keeps. Outlines come from executions later.
 */
export const layoutAtom = atom((get): Layout => {
  const { cellIds, cellRuntime } = get(notebookAtom);
  return deriveLayout(
    cellIds.getColumns().map((column) => ({
      id: column.id,
      ids: column.inOrderIds,
    })),
    (id) => cellRuntime[id]?.outline ?? null,
    get(collapsedAtom),
  );
});

export const useLayout = () => useAtomValue(layoutAtom);

export function findColumn(
  layout: Layout,
  columnId: CellColumnId,
): LayoutColumn | undefined {
  return layout.columns.find((column) => column.id === columnId);
}

/** The column holding `id`. Throws for a cell the layout does not have. */
export function columnOf(layout: Layout, id: CellId): LayoutColumn {
  const column = layout.columns.find((column) => column.ids.includes(id));
  if (column === undefined) {
    throw new Error(`Cell ${id} is not in the layout`);
  }
  return column;
}

/** The cells a folded header hides, or undefined when `id` is not a folded header. */
export function foldOf(
  layout: Layout,
  id: CellId,
): readonly CellId[] | undefined {
  for (const column of layout.columns) {
    const fold = column.folds.get(id);
    if (fold !== undefined) {
      return fold;
    }
  }
  return undefined;
}

/** The headers whose folds hide `id`. */
export function foldsHiding(layout: Layout, id: CellId): CellId[] {
  const column = layout.columns.find((column) => column.ids.includes(id));
  if (column === undefined) {
    return [];
  }
  return [...column.folds]
    .filter(([, hidden]) => hidden.includes(id))
    .map(([header]) => header);
}

/** The visible cell `offset` places from `id` in its column, if there is one. */
export function visibleNeighbor(
  layout: Layout,
  id: CellId,
  offset: -1 | 1,
): CellId | undefined {
  const { visible } = columnOf(layout, id);
  const index = visible.indexOf(id);
  return index === -1 ? undefined : visible[index + offset];
}
