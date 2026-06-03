/* Copyright 2026 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { SlideType, SlidesLayout } from "./types";

export interface SlideCellLike {
  id: CellId;
  output: { data: unknown } | null;
}

export interface SlideCellsInfo<T extends SlideCellLike> {
  slideCells: T[];
  skippedIds: Set<CellId>;
  noOutputIds: Set<CellId>;
  slideTypes: Map<CellId, SlideType>;
  // Index of the first cell in `slideCells` that is not effectively skipped.
  startCellIndex: number;
}

export function hasRenderableOutput(cell: SlideCellLike): boolean {
  return cell.output != null && cell.output.data !== "";
}

export function computeSlideCellsInfo<T extends SlideCellLike>(
  cells: readonly T[],
  layout: Pick<SlidesLayout, "cells">,
): SlideCellsInfo<T> {
  const slideCells = [...cells];
  const skippedIds = new Set<CellId>();
  const noOutputIds = new Set<CellId>();
  const slideTypes = new Map<CellId, SlideType>();

  let startCell: T | null = null;
  let startCellIndex = 0;

  for (const [index, cell] of slideCells.entries()) {
    const type = layout.cells.get(cell.id)?.type;
    const hasOutput = hasRenderableOutput(cell);
    if (type) {
      slideTypes.set(cell.id, type);
    }
    if (!hasOutput) {
      noOutputIds.add(cell.id);
    }
    if (type === "skip" || !hasOutput) {
      skippedIds.add(cell.id);
    } else if (startCell === null) {
      startCell = cell;
      startCellIndex = index;
    }
  }
  return {
    slideCells,
    skippedIds,
    noOutputIds,
    slideTypes,
    startCellIndex,
  };
}
