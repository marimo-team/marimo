/* Copyright 2026 Marimo. All rights reserved. */

/** The cells as they appear on the page: by column, with folded sections hidden. */

import { atom, useAtomValue } from "jotai";
import type { EditableDocument } from "@/core/notebook/document";
import { findCollapseRange } from "../dom/outline";
import { activeDocumentModelAtom } from "../session/active-notebook";
import { cellOutlinesAtom } from "./cells";
import { groupByColumn } from "./columns";
import { CellId } from "./ids";
import type { Outline } from "./outline";

/** A column's identity on this page, as drag and drop and saved widths refer to it. */
export type CellColumnId = string & { __brand: "CellColumnId" };

/** The headers whose sections the user folded. Only this browser knows. */
export const collapsedAtom = atom<ReadonlySet<CellId>>(new Set<CellId>());

/**
 * This browser's names for the document's columns, by position. The
 * document knows columns only by position, so `followColumnsAtom` names
 * a column as it appears and forgets one as it goes, and the column
 * operations carry the names along as they rearrange.
 */
export const columnIdsAtom = atom<readonly CellColumnId[]>([]);

/**
 * Trailing columns a rearrangement here emptied. The document cannot hold
 * an empty column at its end, so the page keeps them, as drop targets for
 * the cell being dragged, until a drop compacts them.
 */
export const emptyColumnIdsAtom = atom<readonly CellColumnId[]>([]);

export function newColumnId(): CellColumnId {
  return `column-${CellId.create()}` as CellColumnId;
}

export function isColumnId(id: unknown): id is CellColumnId {
  return typeof id === "string" && id.startsWith("column-");
}

/**
 * Name the document's columns as the document changes. A column that
 * appears takes over an empty column the page keeps, or gets a fresh id;
 * one that goes is forgotten.
 */
export const followColumnsAtom = atom(
  null,
  (get, set, document: EditableDocument): void => {
    const count = groupByColumn(document).length;
    const ids = get(columnIdsAtom);
    if (ids.length === count) {
      return;
    }
    const empty = get(emptyColumnIdsAtom);
    const named = [...ids, ...empty].slice(0, count);
    while (named.length < count) {
      named.push(newColumnId());
    }
    set(columnIdsAtom, named);
    set(emptyColumnIdsAtom, empty.slice(Math.max(0, count - ids.length)));
  },
);

/** The document's columns, each with its id, then the empty ones the page keeps. */
function columnsOf(
  document: EditableDocument | null,
  ids: readonly CellColumnId[],
  empty: readonly CellColumnId[],
): Array<{ id: CellColumnId; ids: CellId[] }> {
  const groups = document === null ? [[]] : groupByColumn(document);
  return [
    ...groups.map((cells, index) => ({
      // Before the first document names them, columns go by position.
      id: ids[index] ?? (`column-${index}` as CellColumnId),
      ids: cells,
    })),
    ...empty.map((id) => ({ id, ids: [] as CellId[] })),
  ];
}

export interface LayoutColumn {
  readonly id: CellColumnId;
  /** Every cell of the column, in order. */
  readonly ids: readonly CellId[];
  /** The cells on the page: those no fold hides. */
  readonly visible: readonly CellId[];
  /**
   * Each folded header and the cells it hides, nested sections included. A
   * folded header with nothing under it yet has an empty fold.
   */
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
    if (range === null) {
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
 * The layout of the notebook's cells: the document's order and columns,
 * this browser's column ids and folds, and the headings in each cell's
 * output.
 */
export const layoutAtom = atom((get): Layout => {
  const model = get(activeDocumentModelAtom);
  const document = model === null ? null : get(model.documentAtom);
  const outlines = get(cellOutlinesAtom);
  return deriveLayout(
    columnsOf(document, get(columnIdsAtom), get(emptyColumnIdsAtom)),
    (id) => outlines[id] ?? null,
    get(collapsedAtom),
  );
});

export const useLayout = () => useAtomValue(layoutAtom);

export const numColumnsAtom = atom((get) => get(layoutAtom).columns.length);

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

/**
 * The folded headers whose sections a cell without a heading would fall
 * into, placed right after `id`: those hiding `id`, and `id` itself when it
 * is a folded header. A section runs until the next heading, so a cell
 * placed after the last cell of a fold is still inside it.
 */
export function foldsAfter(layout: Layout, id: CellId): CellId[] {
  const hiding = foldsHiding(layout, id);
  return foldOf(layout, id) === undefined ? hiding : [...hiding, id];
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
