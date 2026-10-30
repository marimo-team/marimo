/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellColumnId } from "@/core/cells/layout";
import type { CellId } from "../ids";
import {
  columnOf,
  deriveLayout,
  foldSections,
  foldsHiding,
  visibleNeighbor,
} from "../layout";
import type { Outline } from "../outline";

const [h1, a, h2, b, c, h1b, d] = ["h1", "a", "h2", "b", "c", "h1b", "d"].map(
  cellId,
);
const ids = [h1, a, h2, b, c, h1b, d];

function heading(level: number): Outline {
  return { items: [{ name: `H${level}`, level, by: { id: `h${level}` } }] };
}
const outlines = new Map<CellId, Outline>([
  [h1, heading(1)],
  [h2, heading(2)],
  [h1b, heading(1)],
]);
const outlineOf = (id: CellId) => outlines.get(id) ?? null;
const column = (id: string, cells: CellId[]) => ({
  id: id as CellColumnId,
  ids: cells,
});

describe("foldSections", () => {
  it("folds a header until the next header of its level or higher", () => {
    const folds = foldSections(ids, ids.map(outlineOf), new Set([h2]));
    expect([...folds]).toEqual([[h2, [b, c]]]);
  });

  it("hides a folded section inside a folded section", () => {
    const folds = foldSections(ids, ids.map(outlineOf), new Set([h1, h2]));
    expect(folds.get(h1)).toEqual([a, h2, b, c]);
    expect(folds.get(h2)).toEqual([b, c]);
  });

  it("folds the last section to the end", () => {
    const folds = foldSections(ids, ids.map(outlineOf), new Set([h1b]));
    expect(folds.get(h1b)).toEqual([d]);
  });

  it("ignores cells without a heading and headers with nothing under them", () => {
    const folds = foldSections(
      [h1, a, h1b],
      [heading(1), null, heading(1)],
      new Set([a, h1b]),
    );
    expect(folds.size).toBe(0);
  });
});

describe("deriveLayout", () => {
  const layout = deriveLayout(
    [column("left", ids), column("right", [])],
    outlineOf,
    new Set([h2]),
  );

  it("lists visible cells per column and keeps empty columns", () => {
    expect(layout.columns.map((c) => c.id)).toEqual(["left", "right"]);
    expect(layout.columns[0].visible).toEqual([h1, a, h2, h1b, d]);
    expect(layout.columns[0].ids).toEqual(ids);
    expect(layout.columns[1].visible).toEqual([]);
  });

  it("finds a cell's column, the folds hiding it, and its visible neighbours", () => {
    expect(columnOf(layout, b).id).toBe("left");
    expect(() => columnOf(layout, cellId("missing"))).toThrow(
      "not in the layout",
    );
    expect(foldsHiding(layout, c)).toEqual([h2]);
    expect(foldsHiding(layout, a)).toEqual([]);
    expect(visibleNeighbor(layout, h2, 1)).toBe(h1b);
    expect(visibleNeighbor(layout, h1b, -1)).toBe(h2);
    expect(visibleNeighbor(layout, h1, -1)).toBeUndefined();
    expect(visibleNeighbor(layout, b, 1)).toBeUndefined();
  });
});
