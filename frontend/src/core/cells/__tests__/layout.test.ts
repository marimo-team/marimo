/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { afterEach, describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import type { CellColumnId } from "@/core/cells/layout";
import type { CellId } from "../ids";
import {
  collapsedAtom,
  columnOf,
  deriveLayout,
  foldSections,
  foldsAfter,
  foldsHiding,
  isColumnId,
  layoutAtom,
  newColumnId,
  visibleNeighbor,
} from "../layout";
import type { Outline } from "../outline";
import { setupNotebook } from "./harness";

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

  it("ignores cells without a heading", () => {
    const folds = foldSections([h1, a], [heading(1), null], new Set([a]));
    expect(folds.size).toBe(0);
  });

  it("keeps an empty fold for a header with nothing under it yet", () => {
    const folds = foldSections(
      [h1, a, h1b],
      [heading(1), null, heading(1)],
      new Set([h1b]),
    );
    expect(folds.get(h1b)).toEqual([]);
  });
});

describe("column ids", () => {
  it("are told apart from cell ids, as drag and drop needs", () => {
    expect(isColumnId(newColumnId())).toBe(true);
    expect(isColumnId(cellId("Hbol"))).toBe(false);
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

  it("names the folds a cell placed after another would fall into", () => {
    // After the folded header or the last cell of its fold, inside it.
    expect(foldsAfter(layout, h2)).toEqual([h2]);
    expect(foldsAfter(layout, c)).toEqual([h2]);
    // After a visible cell no fold reaches, nothing.
    expect(foldsAfter(layout, a)).toEqual([]);
    expect(foldsAfter(layout, h1b)).toEqual([]);

    const nested = deriveLayout(
      [column("left", ids)],
      outlineOf,
      new Set([h1, h2]),
    );
    expect(foldsAfter(nested, c)).toEqual([h1, h2]);
  });
});

describe("layoutAtom", () => {
  const stops: Array<() => void> = [];
  afterEach(() => {
    for (const stop of stops.splice(0)) {
      stop();
    }
  });
  const [c1, c2] = ["c1", "c2"].map(cellId);

  /** Deliver `html` as a cell's output, as the kernel's message does. */
  /** Report what the host shows for a cell, keeping the other cells' outputs. */
  function reporter(store: ReturnType<typeof setupNotebook>["store"]) {
    const results = new Map<CellId, Protocol.Execution>();
    return (id: CellId, html: string) => {
      results.set(
        id,
        MockExecutions.shown(id, { mimetype: "text/html", data: html }),
      );
      MockExecutions.seed(store, [...results.values()]);
    };
  }

  it("is the same layout after output that changes no heading", () => {
    const { store } = setupNotebook(stops);
    const output = reporter(store);
    output(c1, "<h1>Title</h1>");
    const layout = store.get(layoutAtom);

    output(c2, "<p>1</p>");
    output(c1, "<h1>Title</h1>");

    expect(store.get(layoutAtom)).toBe(layout);
  });

  it("follows a heading arriving in a cell's output", () => {
    const { store } = setupNotebook(stops);
    const output = reporter(store);
    store.set(collapsedAtom, new Set([c1]));
    expect(store.get(layoutAtom).columns[0].folds.size).toBe(0);

    output(c1, "<h1>Title</h1>");

    expect(store.get(layoutAtom).columns[0].folds.get(c1)).toEqual([c2]);
  });
});
