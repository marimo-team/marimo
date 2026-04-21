/* Copyright 2026 Marimo. All rights reserved. */

import type { SlideType } from "../editor/renderers/slides-layout/types";

/**
 * A contiguous run of cells that render together on a single subslide.
 *
 * - `isFragment=false`: cells are emitted inline in the <Slide>.
 * - `isFragment=true`:  cells are wrapped in a single <Fragment> so they reveal
 *   as one step.
 */
export interface ComposedBlock<T> {
  isFragment: boolean;
  cells: T[];
}

/**
 * One <Slide>. Vertical stacking is expressed at the Stack level.
 */
export interface ComposedSubslide<T> {
  blocks: ComposedBlock<T>[];
}

/**
 * One horizontal position in the deck.
 *
 * - `subslides.length === 1` -> render as a single <Slide>.
 * - `subslides.length > 1`  -> render as <Stack><Slide/>...</Stack>.
 */
export interface ComposedStack<T> {
  subslides: ComposedSubslide<T>[];
}

export interface Composition<T> {
  stacks: ComposedStack<T>[];
}

/**
 * The per-cell slide-type. `undefined` means "continuation" — the cell sticks
 * to whatever container the previous cell opened (slide / subslide / fragment).
 * This matches RISE's behavior for cells with no `slide_type` metadata.
 */
export type ComposeCellType = SlideType | undefined;

export interface ComposeOptions {
  /** Drop `skip` cells entirely. Defaults to true. */
  dropSkipped?: boolean;
}

/**
 * Groups a flat list of cells into a tree of stacks / subslides / blocks based
 * on each cell's {@link SlideType}.
 *
 * Inspired by the RISE JupyterLab extension's `markupSlides`, but adapted for a
 * declarative React renderer: instead of mutating DOM during the walk, we
 * produce a tree the caller can render however they like.
 *
 * Rules (per cell):
 * - `"slide"`     -> open a new stack + subslide, cell goes in a plain block.
 * - `"sub-slide"` -> open a new subslide inside the current stack.
 * - `"fragment"`  -> open a new fragment block inside the current subslide.
 * - `"skip"`      -> dropped by default; kept (in the current block) when
 *                    `dropSkipped: false`.
 * - `undefined`   -> append to whatever block is currently open (continuation).
 *
 * If the very first cell is a `fragment` or `sub-slide`, a containing stack /
 * subslide is created implicitly.
 */
export function composeSlides<T>(
  cells: readonly T[],
  getType: (cell: T) => ComposeCellType,
  opts: ComposeOptions = {},
): Composition<T> {
  const dropSkipped = opts.dropSkipped ?? true;
  const stacks: ComposedStack<T>[] = [];
  let stack: ComposedStack<T> | null = null;
  let subslide: ComposedSubslide<T> | null = null;
  let block: ComposedBlock<T> | null = null;

  const openStack = () => {
    stack = { subslides: [] };
    stacks.push(stack);
    subslide = null;
    block = null;
  };
  const openSubslide = () => {
    if (!stack) {
      openStack();
    }
    subslide = { blocks: [] };
    stack!.subslides.push(subslide);
    block = null;
  };
  const openBlock = (isFragment: boolean) => {
    if (!subslide) {
      openSubslide();
    }
    block = { isFragment, cells: [] };
    subslide!.blocks.push(block);
  };
  const appendToCurrent = (cell: T) => {
    if (!block) {
      openBlock(false);
    }
    block!.cells.push(cell);
  };

  for (const cell of cells) {
    const type = getType(cell);

    if (type === "skip") {
      if (dropSkipped) {
        continue;
      }
      appendToCurrent(cell);
      continue;
    }

    if (type === "slide") {
      openStack();
      openSubslide();
      openBlock(false);
      block!.cells.push(cell);
    } else if (type === "sub-slide") {
      openSubslide();
      openBlock(false);
      block!.cells.push(cell);
    } else if (type === "fragment") {
      openBlock(true);
      block!.cells.push(cell);
    } else {
      appendToCurrent(cell);
    }
  }

  return { stacks };
}

/**
 * A location within the composed tree. Mirrors reveal.js's `{h, v, f}` indices
 * so callers can feed it directly to `Reveal.slide(h, v, f?)`.
 *
 * - `h`: stack index
 * - `v`: subslide index within that stack
 * - `f`: fragment block index within the subslide, or `-1` for non-fragment
 *   cells (i.e. content that's visible before any fragment is revealed).
 */
export interface SlideTarget {
  h: number;
  v: number;
  f: number;
}

export interface SlideIndices<Id> {
  /** Where each cell lives in the deck. */
  cellToTarget: Map<Id, SlideTarget>;
  /**
   * `"h,v,f"` -> flat index into the original cell list. The value is the
   * "active" cell for that position — i.e. the last cell currently visible
   * on screen, so the active cell advances as the user steps through
   * fragments.
   *
   * `f === -1` represents "nothing revealed yet" and is always populated when
   * a subslide exists, so it doubles as a fallback for subslides that have
   * no fragments at all (reveal reports `f === 0` in that case).
   */
  targetToCellIndex: Map<string, number>;
}

/**
 * Build {@link SlideIndices} for a composition so callers can translate
 * between a flat cell list and reveal.js's `{h, v, f}` indices.
 */
export function buildSlideIndices<T, Id>(
  composition: Composition<T>,
  cells: readonly T[],
  getId: (cell: T) => Id,
): SlideIndices<Id> {
  const cellToTarget = new Map<Id, SlideTarget>();
  const targetToCellIndex = new Map<string, number>();
  const cellIndexById = new Map<Id, number>();
  for (const [i, cell] of cells.entries()) {
    cellIndexById.set(getId(cell), i);
  }

  composition.stacks.forEach((stack, h) => {
    stack.subslides.forEach((sub, v) => {
      // f = -1: "nothing revealed yet" state. Active cell = last cell that
      // appears before the first fragment block. If the subslide starts with
      // a fragment block, fall back to its first cell so we still have an
      // anchor when nothing is visible yet.
      let preFragmentActiveId: Id | undefined;
      for (const block of sub.blocks) {
        if (block.isFragment) {
          break;
        }
        const last = block.cells.at(-1);
        if (last) {
          preFragmentActiveId = getId(last);
        }
      }
      if (preFragmentActiveId === undefined) {
        const fallback = sub.blocks[0]?.cells[0];
        if (fallback) {
          preFragmentActiveId = getId(fallback);
        }
      }
      if (preFragmentActiveId !== undefined) {
        const idx = cellIndexById.get(preFragmentActiveId);
        if (idx != null) {
          targetToCellIndex.set(`${h},${v},-1`, idx);
        }
      }

      let fragmentCounter = -1;
      for (const block of sub.blocks) {
        if (block.isFragment) {
          fragmentCounter++;
          for (const cell of block.cells) {
            cellToTarget.set(getId(cell), { h, v, f: fragmentCounter });
          }
          const last = block.cells.at(-1);
          if (last) {
            const idx = cellIndexById.get(getId(last));
            if (idx != null) {
              targetToCellIndex.set(`${h},${v},${fragmentCounter}`, idx);
            }
          }
        } else {
          for (const cell of block.cells) {
            cellToTarget.set(getId(cell), { h, v, f: -1 });
          }
        }
      }
    });
  });
  return { cellToTarget, targetToCellIndex };
}

/**
 * Resolve the flat cell index for the current reveal indices. For slides
 * without fragments reveal may report `f = 0`, so we fall back to the `-1`
 * entry (which is always populated when a subslide exists).
 */
export function resolveActiveCellIndex(
  targetToCellIndex: ReadonlyMap<string, number>,
  indices: { h: number; v: number; f: number },
): number | undefined {
  const { h, v, f } = indices;
  return (
    targetToCellIndex.get(`${h},${v},${f}`) ??
    targetToCellIndex.get(`${h},${v},-1`)
  );
}
