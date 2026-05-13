/* Copyright 2026 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { SlideType, SlidesLayout } from "./types";

export interface SlideCellLike {
  id: CellId;
  output: { data: unknown } | null;
}

export interface SlideCellsInfo<T extends SlideCellLike> {
  cellsWithOutput: T[];
  skippedIds: Set<CellId>;
  slideTypes: Map<CellId, SlideType>;
  // Index of the first cell in `cellsWithOutput` that is not skipped
  startCellIndex: number;
}

export function computeSlideCellsInfo<T extends SlideCellLike>(
  cells: readonly T[],
  layout: Pick<SlidesLayout, "cells">,
): SlideCellsInfo<T> {
  const cellsWithOutput = cells.filter(
    (cell) => cell.output != null && cell.output.data !== "",
  );
  const skippedIds = new Set<CellId>();
  const slideTypes = new Map<CellId, SlideType>();

  let startCell: T | null = null;
  let startCellIndex = 0;

  for (const [index, cell] of cellsWithOutput.entries()) {
    const type = layout.cells.get(cell.id)?.type;
    if (type) {
      slideTypes.set(cell.id, type);
    }
    if (type === "skip") {
      skippedIds.add(cell.id);
    } else if (startCell === null) {
      startCell = cell;
      startCellIndex = index;
    }
  }
  return {
    cellsWithOutput,
    skippedIds,
    slideTypes,
    startCellIndex,
  };
}
