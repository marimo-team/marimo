/* Copyright 2026 Marimo. All rights reserved. */

/** How a document's cells fall into columns. */

import type { EditableDocument } from "@/core/notebook/document";
import type { CellId } from "./ids";

/**
 * Each cell's column: its `column` config, or the column of the cell before
 * it. The first cell starts in column 0.
 */
export function resolveColumns(
  document: EditableDocument,
): Map<CellId, number> {
  const columns = new Map<CellId, number>();
  let current = 0;
  for (const id of document.order) {
    const column = document.cells.get(id)?.config.column;
    if (column != null && column >= 0) {
      current = column;
    }
    // The protocol's ids are plain strings; the notebook brands them.
    columns.set(id as CellId, current);
  }
  return columns;
}

/** The cells of each column in order, with empty columns for gaps. */
export function groupByColumn(document: EditableDocument): CellId[][] {
  const columns: CellId[][] = [[]];
  for (const [id, column] of resolveColumns(document)) {
    while (columns.length <= column) {
      columns.push([]);
    }
    columns[column].push(id);
  }
  return columns;
}
