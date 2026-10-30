/* Copyright 2026 Marimo. All rights reserved. */

/** Notebook operations that move cells and arrange columns. */

import { dequal as isEqual } from "dequal";
import { atom, type Getter, type Setter } from "jotai";
import { reorderColumnSizes } from "@/components/editor/columns/storage";
import type {
  DocumentEditor,
  EditableDocument,
} from "@/core/notebook/document";
import { arrayMove } from "@/utils/arrays";
import { notebookAtom, type UndoMoveEntry } from "./cells";
import { documentOf, focusWhenMounted, modelOf } from "./edit";
import { CellId } from "./ids";
import {
  type CellColumnId,
  columnIdsAtom,
  columnOf,
  findColumn,
  type Layout,
  type LayoutColumn,
  layoutAtom,
} from "./layout";

/** A placement to restore a cell to: its column and its index there. */
export interface Placement {
  columnId: CellColumnId;
  index: number;
}

/** A cell with the cells its fold hides, which move with it. */
function blockOf(column: LayoutColumn, id: CellId): CellId[] {
  return [id, ...(column.folds.get(id) ?? [])];
}

/** A column as the blocks the page shows, in order. Together they hold every cell. */
function blocksOf(column: LayoutColumn): CellId[][] {
  return column.visible.map((id) => blockOf(column, id));
}

/** The cells of every column, as arrays to rearrange. */
function columnsOf(layout: Layout): CellId[][] {
  return layout.columns.map((column) => [...column.ids]);
}

function without(columns: CellId[][], ids: ReadonlySet<CellId>): CellId[][] {
  return columns.map((column) => column.filter((id) => !ids.has(id)));
}

/**
 * The `column` configs that make the document's columns match `columns`,
 * in the form the file is written in: with one column no cell carries a
 * column, and with several only the first cell of each carries its index.
 * An emptied column keeps its place as a gap, since the next column's first
 * cell still names its index, until a drop compacts it.
 */
function columnConfigs(
  columns: readonly (readonly CellId[])[],
  configured: (id: CellId) => number | null,
): Array<[CellId, number | null]> {
  const fixes: Array<[CellId, number | null]> = [];
  const single = columns.length === 1;
  columns.forEach((column, index) => {
    column.forEach((id, position) => {
      const target = !single && position === 0 ? index : null;
      if (configured(id) !== target) {
        fixes.push([id, target]);
      }
    });
  });
  return fixes;
}

/** The steps that make the document's cells fall into `columns`, or null when they do. */
function arrangement(
  document: EditableDocument,
  columns: readonly (readonly CellId[])[],
): ((tx: DocumentEditor) => void) | null {
  const order = columns.flat();
  const fixes = columnConfigs(
    columns,
    (id) => document.cells.get(id)?.config.column ?? null,
  );
  const reordered = !isEqual(order, document.order);
  if (!reordered && fixes.length === 0) {
    return null;
  }
  return (tx) => {
    if (reordered) {
      tx.setOrder(order);
    }
    for (const [id, column] of fixes) {
      tx.updateConfig(id, { column });
    }
  };
}

/**
 * Make the document's cells fall into `columns`, in that order, as one edit.
 * Nothing is written when they already do. The columns as they stand keep
 * their ids, so one this rearrangement empties stays until a drop compacts
 * it.
 */
export function arrange(get: Getter, set: Setter, columns: CellId[][]): void {
  nameColumns(
    set,
    get(layoutAtom).columns.map((column) => column.id),
  );
  const edit = arrangement(documentOf(get), columns);
  if (edit !== null) {
    set(modelOf(get).editAtom, edit);
  }
}

/** Name the columns as they now stand, keeping the ids of those that remain. */
function nameColumns(set: Setter, ids: readonly CellColumnId[]): void {
  set(columnIdsAtom, ids);
}

function newColumnId(): CellColumnId {
  return `column-${CellId.create()}` as CellColumnId;
}

/**
 * Move a cell one block up or down its column, or to the start of the
 * neighbouring column. A folded header moves with its section.
 */
export const moveCellAtom = atom(
  null,
  (
    get,
    set,
    {
      cellId,
      before,
      direction,
    }: { cellId: CellId; before?: boolean; direction?: "left" | "right" },
  ): void => {
    const layout = get(layoutAtom);
    const column = columnOf(layout, cellId);
    const at = layout.columns.indexOf(column);
    const columns = columnsOf(layout);
    if (direction) {
      const to = direction === "left" ? at - 1 : at + 1;
      if (to < 0 || to >= columns.length) {
        return;
      }
      const block = blockOf(column, cellId);
      const cleaned = without(columns, new Set(block));
      cleaned[to] = [...block, ...cleaned[to]];
      arrange(get, set, cleaned);
      focusWhenMounted(set, cellId);
      return;
    }
    const blocks = blocksOf(column);
    const index = blocks.findIndex((block) => block[0] === cellId);
    const target = before ? index - 1 : index + 1;
    if (index !== -1 && target >= 0 && target < blocks.length) {
      columns[at] = arrayMove(blocks, index, target).flat();
      arrange(get, set, columns);
    }
    focusWhenMounted(set, cellId);
  },
);

function sendTo(
  get: Getter,
  set: Setter,
  { cellId, scroll = true }: { cellId: CellId; scroll?: boolean },
  edge: "top" | "bottom",
): void {
  const layout = get(layoutAtom);
  const column = columnOf(layout, cellId);
  const blocks = blocksOf(column);
  const index = blocks.findIndex((block) => block[0] === cellId);
  const target = edge === "top" ? 0 : blocks.length - 1;
  if (index === -1 || index === target) {
    return;
  }
  const columns = columnsOf(layout);
  columns[layout.columns.indexOf(column)] = arrayMove(
    blocks,
    index,
    target,
  ).flat();
  arrange(get, set, columns);
  if (scroll) {
    focusWhenMounted(set, cellId);
  }
}

/** Move a cell, with its fold, to the top of its column. */
export const sendToTopAtom = atom(
  null,
  (get, set, options: { cellId: CellId; scroll?: boolean }): void =>
    sendTo(get, set, options, "top"),
);

/** Move a cell, with its fold, to the bottom of its column. */
export const sendToBottomAtom = atom(
  null,
  (get, set, options: { cellId: CellId; scroll?: boolean }): void =>
    sendTo(get, set, options, "bottom"),
);

/** Drop a dragged cell, with its fold, where another cell is. */
export const dropCellOverCellAtom = atom(
  null,
  (
    get,
    set,
    { cellId, overCellId }: { cellId: CellId; overCellId: CellId },
  ): void => {
    const layout = get(layoutAtom);
    const from = columnOf(layout, cellId);
    const to = columnOf(layout, overCellId);
    const columns = columnsOf(layout);
    if (from === to) {
      const blocks = blocksOf(from);
      const index = blocks.findIndex((block) => block[0] === cellId);
      const target = blocks.findIndex((block) => block[0] === overCellId);
      if (index === -1 || target === -1 || index === target) {
        return;
      }
      columns[layout.columns.indexOf(from)] = arrayMove(
        blocks,
        index,
        target,
      ).flat();
      arrange(get, set, columns);
      return;
    }
    const block = blockOf(from, cellId);
    const cleaned = without(columns, new Set(block));
    const target = cleaned[layout.columns.indexOf(to)];
    const at = target.indexOf(overCellId);
    target.splice(at, 0, ...block);
    arrange(get, set, cleaned);
  },
);

/** Drop a dragged cell, with its fold, at the start of a column. */
export const dropCellOverColumnAtom = atom(
  null,
  (
    get,
    set,
    { cellId, columnId }: { cellId: CellId; columnId: CellColumnId },
  ): void => {
    const layout = get(layoutAtom);
    const to = findColumn(layout, columnId);
    if (to === undefined) {
      return;
    }
    const block = blockOf(columnOf(layout, cellId), cellId);
    const cleaned = without(columnsOf(layout), new Set(block));
    cleaned[layout.columns.indexOf(to)].unshift(...block);
    arrange(get, set, cleaned);
  },
);

/** Move a cell, with its fold, to an index in a column. Out of range clamps. */
export const moveCellToIndexAtom = atom(
  null,
  (
    get,
    set,
    {
      cellId,
      columnId,
      index,
    }: { cellId: CellId; columnId: CellColumnId; index: number },
  ): void => {
    const layout = get(layoutAtom);
    const to = findColumn(layout, columnId);
    if (to === undefined) {
      return;
    }
    const from = columnOf(layout, cellId);
    const block = blockOf(from, cellId);
    const columns = columnsOf(layout);
    const fromIndex = from.ids.indexOf(cellId);
    const cleaned = without(columns, new Set(block));
    const target = cleaned[layout.columns.indexOf(to)];
    let at = Math.max(0, Math.min(index, to.ids.length));
    if (from === to && fromIndex < at) {
      at -= block.length;
    }
    target.splice(Math.max(0, Math.min(at, target.length)), 0, ...block);
    arrange(get, set, cleaned);
  },
);

/**
 * Move cells to just before or after a target cell, in their order. With
 * the cells' previous placements, the move can be undone.
 */
export const moveCellsRelativeToAtom = atom(
  null,
  (
    get,
    set,
    {
      cellIds,
      targetCellId,
      position,
      previousPlacements,
    }: {
      cellIds: CellId[];
      targetCellId: CellId;
      position: "before" | "after";
      previousPlacements?: Placement[];
    },
  ): void => {
    if (cellIds.length === 0) {
      return;
    }
    const layout = get(layoutAtom);
    const moving = new Set(cellIds);
    const cleaned = without(columnsOf(layout), moving);
    const target =
      cleaned[layout.columns.indexOf(columnOf(layout, targetCellId))];
    let at = target.indexOf(targetCellId);
    if (at === -1) {
      // The target moves too, so the cells go to the end of its column.
      at = target.length;
    } else if (position === "after") {
      at += 1;
    }
    target.splice(at, 0, ...cellIds);
    arrange(get, set, cleaned);
    if (previousPlacements && previousPlacements.length === cellIds.length) {
      const entry: UndoMoveEntry = {
        type: "move",
        cellIds,
        placements: previousPlacements,
      };
      set(notebookAtom, (state) => ({
        ...state,
        history: [...state.history, entry],
      }));
    }
  },
);

/** Put cells back where they were, by column and index. A vanished column takes the last. */
export function placeCells(
  get: Getter,
  set: Setter,
  cellIds: readonly CellId[],
  placements: readonly Placement[],
): void {
  const layout = get(layoutAtom);
  const cleaned = without(columnsOf(layout), new Set(cellIds));
  const columnIndex = (columnId: CellColumnId) => {
    const index = layout.columns.findIndex((column) => column.id === columnId);
    return index === -1 ? cleaned.length - 1 : index;
  };
  const sorted = cellIds
    .map((id, i) => ({
      id,
      column: columnIndex(placements[i].columnId),
      index: placements[i].index,
    }))
    .toSorted((a, b) => a.column - b.column || a.index - b.index);
  for (const { id, column, index } of sorted) {
    const target = cleaned[column];
    target.splice(Math.max(0, Math.min(index, target.length)), 0, id);
  }
  arrange(get, set, cleaned);
}

// Columns --------------------------------------------------------------------

/** Add a column after another, with one new cell to start it, and focus the cell. */
export const addColumnAtom = atom(
  null,
  (get, set, { columnId }: { columnId: CellColumnId }): void => {
    const layout = get(layoutAtom);
    const at = layout.columns.findIndex((column) => column.id === columnId);
    if (at === -1) {
      return;
    }
    const id = CellId.create();
    const columns = columnsOf(layout);
    columns.splice(at + 1, 0, [id]);
    const ids = layout.columns.map((column) => column.id);
    ids.splice(at + 1, 0, newColumnId());
    const document = documentOf(get);
    const previous = layout.columns[at].ids.at(-1);
    set(modelOf(get).editAtom, (tx) => {
      tx.createCell(
        { id, code: "", config: { column: at + 1 } },
        previous === undefined ? {} : { after: previous },
      );
      arrangement(document, columns)?.(tx);
    });
    nameColumns(set, ids);
    focusWhenMounted(set, id);
  },
);

/** Start a new column at a cell, unless it already starts the first column. */
export const addColumnBreakpointAtom = atom(
  null,
  (get, set, { cellId }: { cellId: CellId }): void => {
    const layout = get(layoutAtom);
    const column = columnOf(layout, cellId);
    const at = layout.columns.indexOf(column);
    const index = column.ids.indexOf(cellId);
    if (at === 0 && index === 0) {
      return;
    }
    const columns = columnsOf(layout);
    columns.splice(at, 1, column.ids.slice(0, index), column.ids.slice(index));
    const ids = layout.columns.map((column) => column.id);
    ids.splice(at + 1, 0, newColumnId());
    arrange(get, set, columns);
    nameColumns(set, ids);
  },
);

/** Remove a column, moving its cells to the column before it, or after it for the first. */
export const deleteColumnAtom = atom(
  null,
  (get, set, { columnId }: { columnId: CellColumnId }): void => {
    const layout = get(layoutAtom);
    const at = layout.columns.findIndex((column) => column.id === columnId);
    if (at === -1 || layout.columns.length <= 1) {
      return;
    }
    const columns = columnsOf(layout);
    const target = at === 0 ? 1 : at - 1;
    columns[target] =
      at === 0
        ? [...columns[at], ...columns[target]]
        : [...columns[target], ...columns[at]];
    columns.splice(at, 1);
    const ids = layout.columns.map((column) => column.id);
    ids.splice(at, 1);
    arrange(get, set, columns);
    nameColumns(set, ids);
  },
);

/** Bring every cell into the first column. */
export const mergeAllColumnsAtom = atom(null, (get, set): void => {
  const layout = get(layoutAtom);
  if (layout.columns.length <= 1) {
    return;
  }
  arrange(get, set, [layout.columns.flatMap((column) => [...column.ids])]);
  nameColumns(set, [layout.columns[0].id]);
});

/** Drop the columns a drag left empty. */
export const compactColumnsAtom = atom(null, (get, set): void => {
  const layout = get(layoutAtom);
  const kept = layout.columns.filter((column) => column.ids.length > 0);
  if (kept.length === layout.columns.length || layout.columns.length <= 1) {
    return;
  }
  arrange(
    get,
    set,
    kept.map((column) => [...column.ids]),
  );
  nameColumns(
    set,
    kept.map((column) => column.id),
  );
});

/** Move a column where another is, or one step left or right, with its saved width. */
export const moveColumnAtom = atom(
  null,
  (
    get,
    set,
    {
      column,
      overColumn,
    }: {
      column: CellColumnId;
      overColumn: CellColumnId | "_left_" | "_right_";
    },
  ): void => {
    if (column === overColumn) {
      return;
    }
    const layout = get(layoutAtom);
    const ids = layout.columns.map((column) => column.id);
    const from = ids.indexOf(column);
    const to =
      overColumn === "_left_"
        ? from - 1
        : overColumn === "_right_"
          ? from + 1
          : ids.indexOf(overColumn);
    if (from === -1 || to < 0 || to >= ids.length) {
      return;
    }
    arrange(get, set, arrayMove(columnsOf(layout), from, to));
    nameColumns(set, arrayMove(ids, from, to));
    reorderColumnSizes(from, to);
  },
);
