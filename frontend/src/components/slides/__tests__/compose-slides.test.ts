/* Copyright 2026 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import {
  buildSlideIndices,
  composeSlides,
  computeDeckNavigation,
  resolveDeckNavigationTarget,
  resolveActiveCellIndex,
} from "../compose-slides";
import type { SlideType } from "@/components/editor/renderers/slides-layout/types";

interface Cell {
  id: string;
  /**
   * Optional for ergonomics; mirrors the on-disk shape where a missing
   * `type` means "use the default slide type". The `compose` helper below
   * normalizes this to `"slide"` before passing through.
   */
  type?: SlideType;
}

const compose = (cells: Cell[]) =>
  composeSlides({
    cells,
    getType: (c) => c.type ?? "slide",
  });

/**
 * Collapse the tree to a readable shape so failures produce tiny, obvious
 * diffs:
 *   stacks -> subslides -> blocks -> { f: isFragment, ids: [...] }
 */
const shape = (cells: Cell[]) =>
  compose(cells).stacks.map((s) =>
    s.subslides.map((sub) =>
      sub.blocks.map((b) => ({
        f: b.isFragment,
        ids: b.cells.map((x) => x.id),
      })),
    ),
  );

describe("composeSlides", () => {
  it("returns an empty composition for empty input", () => {
    expect(compose([])).toEqual({ stacks: [] });
  });

  it("treats each 'slide' cell as its own stack", () => {
    expect(
      shape([
        { id: "a", type: "slide" },
        { id: "b", type: "slide" },
        { id: "c", type: "slide" },
      ]),
    ).toEqual([
      [[{ f: false, ids: ["a"] }]],
      [[{ f: false, ids: ["b"] }]],
      [[{ f: false, ids: ["c"] }]],
    ]);
  });

  it("nests 'sub-slide' cells under the current slide (vertical stack)", () => {
    expect(
      shape([
        { id: "a", type: "slide" },
        { id: "b", type: "sub-slide" },
        { id: "c", type: "sub-slide" },
        { id: "d", type: "slide" },
      ]),
    ).toEqual([
      [
        [{ f: false, ids: ["a"] }],
        [{ f: false, ids: ["b"] }],
        [{ f: false, ids: ["c"] }],
      ],
      [[{ f: false, ids: ["d"] }]],
    ]);
  });

  it("wraps fragments in their own block on the current subslide", () => {
    expect(
      shape([
        { id: "a", type: "slide" },
        { id: "b", type: "fragment" },
        { id: "c", type: "fragment" },
      ]),
    ).toEqual([
      [
        [
          { f: false, ids: ["a"] },
          { f: true, ids: ["b"] },
          { f: true, ids: ["c"] },
        ],
      ],
    ]);
  });

  it("treats cells with no type as their own new slide (the default)", () => {
    expect(
      shape([
        { id: "a", type: "slide" },
        { id: "b" },
        { id: "c", type: "fragment" },
        { id: "d" },
      ]),
    ).toEqual([
      [[{ f: false, ids: ["a"] }]],
      [
        [
          { f: false, ids: ["b"] },
          { f: true, ids: ["c"] },
        ],
      ],
      [[{ f: false, ids: ["d"] }]],
    ]);
  });

  it("creates an implicit initial subslide when the first cell is a fragment", () => {
    expect(shape([{ id: "a", type: "fragment" }])).toEqual([
      [[{ f: true, ids: ["a"] }]],
    ]);
  });

  it("creates an implicit initial stack when the first cell is a sub-slide", () => {
    expect(
      shape([
        { id: "a", type: "sub-slide" },
        { id: "b", type: "sub-slide" },
      ]),
    ).toEqual([[[{ f: false, ids: ["a"] }], [{ f: false, ids: ["b"] }]]]);
  });

  it("drops 'skip' cells from the deck", () => {
    expect(
      shape([
        { id: "a", type: "slide" },
        { id: "b", type: "skip" },
        { id: "c", type: "fragment" },
      ]),
    ).toEqual([
      [
        [
          { f: false, ids: ["a"] },
          { f: true, ids: ["c"] },
        ],
      ],
    ]);
  });

  it("skip at the very start does not create an empty leading stack", () => {
    expect(
      shape([
        { id: "a", type: "skip" },
        { id: "b", type: "slide" },
      ]),
    ).toEqual([[[{ f: false, ids: ["b"] }]]]);
  });

  it("opens a fresh fragment block for each consecutive fragment cell", () => {
    expect(
      shape([
        { id: "a", type: "slide" },
        { id: "b", type: "fragment" },
        { id: "c", type: "fragment" },
        { id: "d", type: "fragment" },
      ]),
    ).toEqual([
      [
        [
          { f: false, ids: ["a"] },
          { f: true, ids: ["b"] },
          { f: true, ids: ["c"] },
          { f: true, ids: ["d"] },
        ],
      ],
    ]);
  });

  it("resets fragment context when a new subslide opens", () => {
    expect(
      shape([
        { id: "a", type: "slide" },
        { id: "b", type: "fragment" },
        { id: "c", type: "sub-slide" },
        { id: "d", type: "fragment" },
      ]),
    ).toEqual([
      [
        [
          { f: false, ids: ["a"] },
          { f: true, ids: ["b"] },
        ],
        [
          { f: false, ids: ["c"] },
          { f: true, ids: ["d"] },
        ],
      ],
    ]);
  });

  it("handles a realistic mixed sequence", () => {
    expect(
      shape([
        { id: "title", type: "slide" },
        { id: "intro", type: "fragment" },
        { id: "deep", type: "sub-slide" },
        { id: "deep-body", type: "fragment" },
        { id: "debug", type: "skip" },
        { id: "outro", type: "slide" },
      ]),
    ).toEqual([
      [
        [
          { f: false, ids: ["title"] },
          { f: true, ids: ["intro"] },
        ],
        [
          { f: false, ids: ["deep"] },
          { f: true, ids: ["deep-body"] },
        ],
      ],
      [[{ f: false, ids: ["outro"] }]],
    ]);
  });

  it("is generic over cell shape (preserves object identity)", () => {
    const a = { id: "a", type: "slide" as const, extra: 42 };
    const b = { id: "b", type: "fragment" as const, extra: 7 };
    const result = composeSlides({ cells: [a, b], getType: (c) => c.type });
    expect(result.stacks[0].subslides[0].blocks[0].cells[0]).toBe(a);
    expect(result.stacks[0].subslides[0].blocks[1].cells[0]).toBe(b);
  });
});

describe("buildSlideIndices", () => {
  const build = (cells: Cell[]) => {
    const composition = composeSlides({
      cells,
      getType: (c) => c.type ?? "slide",
    });
    return buildSlideIndices({ composition, cells, getId: (c) => c.id });
  };

  it("maps each cell to its {h, v, f} location", () => {
    const cells: Cell[] = [
      { id: "a", type: "slide" },
      { id: "b", type: "fragment" },
      { id: "c", type: "sub-slide" },
      { id: "d", type: "slide" },
      { id: "e", type: "fragment" },
      { id: "f", type: "fragment" },
    ];
    const { cellToTarget } = build(cells);
    expect(cellToTarget.get("a")).toEqual({ h: 0, v: 0, f: -1 });
    expect(cellToTarget.get("b")).toEqual({ h: 0, v: 0, f: 0 });
    expect(cellToTarget.get("c")).toEqual({ h: 0, v: 1, f: -1 });
    expect(cellToTarget.get("d")).toEqual({ h: 1, v: 0, f: -1 });
    expect(cellToTarget.get("e")).toEqual({ h: 1, v: 0, f: 0 });
    expect(cellToTarget.get("f")).toEqual({ h: 1, v: 0, f: 1 });
  });

  it("maps {h, v, f} back to the flat index of the last visible cell", () => {
    const cells: Cell[] = [
      { id: "a", type: "slide" },
      { id: "b", type: "fragment" },
      { id: "c", type: "fragment" },
    ];
    const { targetToCellIndex } = build(cells);
    // Before any fragment is revealed, the active cell is the last pre-fragment cell.
    expect(targetToCellIndex.get("0,0,-1")).toBe(0); // "a"
    // After fragment 0 is shown, active advances to "b".
    expect(targetToCellIndex.get("0,0,0")).toBe(1); // "b"
    // After fragment 1 is shown, active advances to "c".
    expect(targetToCellIndex.get("0,0,1")).toBe(2); // "c"
  });

  it("populates f=-1 with the first cell when the subslide starts with a fragment", () => {
    const cells: Cell[] = [{ id: "a", type: "fragment" }];
    const { targetToCellIndex } = build(cells);
    expect(targetToCellIndex.get("0,0,-1")).toBe(0);
    expect(targetToCellIndex.get("0,0,0")).toBe(0);
  });

  it("drops skipped cells from the index entirely", () => {
    const cells: Cell[] = [
      { id: "a", type: "slide" },
      { id: "b", type: "skip" },
    ];
    const { cellToTarget } = build(cells);
    expect(cellToTarget.has("a")).toBe(true);
    expect(cellToTarget.has("b")).toBe(false);
  });
});

describe("resolveActiveCellIndex", () => {
  const map = new Map<string, number>([
    ["0,0,-1", 0],
    ["0,0,0", 1],
    ["0,0,1", 2],
    ["1,0,-1", 3],
  ]);

  it("returns the exact match when one exists", () => {
    expect(resolveActiveCellIndex(map, { h: 0, v: 0, f: 1 })).toBe(2);
  });

  it("falls back to f=-1 when there is no fragment-specific entry", () => {
    // reveal may report f=0 for slides without any fragments
    expect(resolveActiveCellIndex(map, { h: 1, v: 0, f: 0 })).toBe(3);
  });

  it("returns undefined for unknown stacks", () => {
    expect(resolveActiveCellIndex(map, { h: 9, v: 0, f: 0 })).toBeUndefined();
  });
});

describe("resolveDeckNavigationTarget", () => {
  const resolve = (cells: Cell[], activeIndex: number | undefined) => {
    const composition = compose(cells);
    const { cellToTarget } = buildSlideIndices({
      composition,
      cells,
      getId: (cell) => cell.id,
    });
    return resolveDeckNavigationTarget({
      activeIndex,
      cells,
      cellToTarget,
      getId: (cell) => cell.id,
    });
  };

  it("returns the selected cell target when the cell is part of the deck", () => {
    expect(
      resolve(
        [
          { id: "a", type: "slide" },
          { id: "b", type: "fragment" },
        ],
        1,
      ),
    ).toEqual({ h: 0, v: 0, f: 0 });
  });

  it("parks a skipped cell on the closest earlier deck cell", () => {
    expect(
      resolve(
        [
          { id: "a", type: "slide" },
          { id: "skip", type: "skip" },
          { id: "b", type: "slide" },
        ],
        1,
      ),
    ).toEqual({ h: 0, v: 0, f: -1 });
  });

  it("falls forward when a skipped cell appears before any real slide", () => {
    expect(
      resolve(
        [
          { id: "skip", type: "skip" },
          { id: "a", type: "slide" },
        ],
        0,
      ),
    ).toEqual({ h: 0, v: 0, f: -1 });
  });

  it("returns undefined when there is no real slide to park on", () => {
    expect(resolve([{ id: "skip", type: "skip" }], 0)).toBeUndefined();
  });
});

describe("computeDeckNavigation", () => {
  it("returns null when the deck is already on a non-fragment target", () => {
    expect(
      computeDeckNavigation({ h: 0, v: 0, f: -1 }, { h: 0, v: 0, f: -1 }),
    ).toBeNull();
  });

  it("returns null when the deck is already on the target fragment", () => {
    expect(
      computeDeckNavigation({ h: 0, v: 0, f: 1 }, { h: 0, v: 0, f: 1 }),
    ).toBeNull();
  });

  it("navigates to a different stack", () => {
    expect(
      computeDeckNavigation({ h: 0, v: 0, f: -1 }, { h: 2, v: 0, f: -1 }),
    ).toEqual({ h: 2, v: 0, f: -1 });
  });

  it("navigates to a different subslide within the same stack", () => {
    expect(
      computeDeckNavigation({ h: 1, v: 0, f: -1 }, { h: 1, v: 2, f: -1 }),
    ).toEqual({ h: 1, v: 2, f: -1 });
  });

  it("collapses revealed fragments when jumping to the parent slide", () => {
    // Regression: previously left `f` unchanged, so the deck would stay on
    // the last-revealed fragment when the user clicked the parent slide in
    // the minimap.
    expect(
      computeDeckNavigation({ h: 0, v: 0, f: 2 }, { h: 0, v: 0, f: -1 }),
    ).toEqual({ h: 0, v: 0, f: -1 });
  });

  it("collapses fragments when jumping to a parent slide in a different stack", () => {
    expect(
      computeDeckNavigation({ h: 1, v: 0, f: 3 }, { h: 0, v: 0, f: -1 }),
    ).toEqual({ h: 0, v: 0, f: -1 });
  });

  it("advances to a specific fragment on the same slide", () => {
    expect(
      computeDeckNavigation({ h: 0, v: 0, f: -1 }, { h: 0, v: 0, f: 2 }),
    ).toEqual({ h: 0, v: 0, f: 2 });
  });

  it("rewinds to an earlier fragment on the same slide", () => {
    expect(
      computeDeckNavigation({ h: 0, v: 0, f: 3 }, { h: 0, v: 0, f: 1 }),
    ).toEqual({ h: 0, v: 0, f: 1 });
  });

  it("jumps across stacks directly to a fragment", () => {
    expect(
      computeDeckNavigation({ h: 0, v: 0, f: -1 }, { h: 2, v: 1, f: 0 }),
    ).toEqual({ h: 2, v: 1, f: 0 });
  });
});
