/* Copyright 2026 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { SlideConfig } from "../editor/renderers/slides-layout/types";
import type { ComposedSubslide } from "./compose-slides";

/** Lone-line marker between blocks; `<NotesAside>` renders this as `<hr>`. */
export const NOTES_DIVIDER = "---";

const BLOCK_JOIN = `\n\n${NOTES_DIVIDER}\n\n`;

export const collectBlockNotes = <C extends { id: CellId }>(
  cells: readonly C[],
  slideConfigs: ReadonlyMap<CellId, SlideConfig>,
): string =>
  cells
    .map((cell) => slideConfigs.get(cell.id)?.speakerNotes ?? "")
    .filter((note) => note.trim().length > 0)
    .join("\n\n");

export interface SubslideNotes {
  /** Notes shown when no fragment is current. */
  slideLevel: string;
  /** Cumulative notes for each fragment block, keyed by block index. */
  cumulativeByBlock: Map<number, string>;
}

/**
 * Per-fragment cumulative notes: slide-level notes plus each revealed
 * fragment's notes, separated by a horizontal-rule line.
 */
export const buildSubslideNotes = <C extends { id: CellId }>(
  subslide: ComposedSubslide<C>,
  slideConfigs: ReadonlyMap<CellId, SlideConfig>,
): SubslideNotes => {
  const blockNotes = subslide.blocks.map((block) =>
    collectBlockNotes(block.cells, slideConfigs),
  );

  const slideLevel = subslide.blocks
    .map((block, i) => (block.isFragment ? "" : blockNotes[i]))
    .filter((note) => note.length > 0)
    .join("\n\n");

  const cumulativeByBlock = new Map<number, string>();
  const revealsSoFar: string[] = [];
  subslide.blocks.forEach((block, i) => {
    if (!block.isFragment) {
      return;
    }
    const myNotes = blockNotes[i];
    if (myNotes.length > 0) {
      revealsSoFar.push(myNotes);
    }
    const accumulated = [slideLevel, ...revealsSoFar]
      .filter((s) => s.length > 0)
      .join(BLOCK_JOIN);
    if (accumulated.length > 0) {
      cumulativeByBlock.set(i, accumulated);
    }
  });

  return { slideLevel, cumulativeByBlock };
};
