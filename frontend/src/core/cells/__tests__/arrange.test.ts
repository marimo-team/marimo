/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { cell, CONFIG } from "@/core/notebook/document/__tests__/fixtures";
import type { CellIndex } from "@/utils/id-tree";
import { collapseCellAtom, undoDeleteCellAtom } from "../actions";
import {
  addColumnAtom,
  addColumnBreakpointAtom,
  compactColumnsAtom,
  deleteColumnAtom,
  dropCellOverCellAtom,
  dropCellOverColumnAtom,
  mergeAllColumnsAtom,
  moveCellAtom,
  moveCellsRelativeToAtom,
  moveCellToIndexAtom,
  moveColumnAtom,
  sendToBottomAtom,
  sendToTopAtom,
} from "../arrange";
import { columnIdsAtom, layoutAtom } from "../layout";
import { setupNotebook } from "./harness";

vi.mock("../scrollCellIntoView", () => ({
  focusAndScrollCellIntoView: vi.fn(),
}));

const c1 = cellId("c1");
const c2 = cellId("c2");
const c3 = cellId("c3");
const c4 = cellId("c4");
const stops: Array<() => void> = [];

afterEach(() => {
  for (const stop of stops.splice(0)) {
    stop();
  }
});

const setup = (cells?: Record<string, Protocol.Cell | null>) =>
  setupNotebook(stops, cells);

/** Four cells, the last two in a second column. */
function twoColumns() {
  return setup({
    c3: cell("c3", "z = 3", { config: { ...CONFIG, column: 1 } }),
    c4: cell("c4", "w = 4"),
  });
}

describe("moveCellAtom", () => {
  it("moves a cell up and down its column and focuses it", () => {
    const { store, order, notebook } = setup({ c3: cell("c3", "z = 3") });

    store.set(moveCellAtom, { cellId: c3, before: true });
    expect(order()).toEqual([c1, c3, c2]);
    expect(notebook().scrollKey).toBe(c3);

    store.set(moveCellAtom, { cellId: c3, before: false });
    expect(order()).toEqual([c1, c2, c3]);
  });

  it("stays at the edge of its column, still focusing", () => {
    const { store, order, notebook } = setup();
    store.set(moveCellAtom, { cellId: c1, before: true });
    expect(order()).toEqual([c1, c2]);
    expect(notebook().scrollKey).toBe(c1);
  });

  it("carries a folded header's section with it", () => {
    const { store, order, visible, heading } = setup({
      c3: cell("c3", "z = 3"),
      c4: cell("c4", "w = 4"),
    });
    heading(c2, 1);
    store.set(collapseCellAtom, { cellId: c2 });
    expect(visible()).toEqual([c1, c2]);

    store.set(moveCellAtom, { cellId: c2, before: true });

    expect(order()).toEqual([c2, c3, c4, c1]);
    // The section runs to the next heading, so the cell it passed joins it.
    expect(visible()).toEqual([c2]);
  });

  it("steps over a folded section below it", () => {
    const { store, order, heading } = setup({
      c3: cell("c3", "z = 3"),
      c4: cell("c4", "w = 4"),
    });
    heading(c2, 1);
    store.set(collapseCellAtom, { cellId: c2 });

    store.set(moveCellAtom, { cellId: c1, before: false });
    expect(order()).toEqual([c2, c3, c4, c1]);
  });

  it("moves to the start of the neighbouring column and names it", () => {
    const { store, columns, cellIn } = twoColumns();
    expect(columns()).toEqual([
      [c1, c2],
      [c3, c4],
    ]);

    store.set(moveCellAtom, { cellId: c2, direction: "right" });
    expect(columns()).toEqual([[c1], [c2, c3, c4]]);
    expect(cellIn(c2)?.config.column).toBe(1);
    expect(cellIn(c3)?.config.column).toBeNull();

    store.set(moveCellAtom, { cellId: c2, direction: "left" });
    expect(columns()).toEqual([
      [c2, c1],
      [c3, c4],
    ]);
    expect(cellIn(c2)?.config.column).toBe(0);
  });

  it("does nothing past the last column", () => {
    const { store, model, columns } = twoColumns();
    const before = store.get(model.documentAtom);
    store.set(moveCellAtom, { cellId: c3, direction: "right" });
    expect(store.get(model.documentAtom)).toBe(before);
    expect(columns()).toEqual([
      [c1, c2],
      [c3, c4],
    ]);
  });
});

describe("sendToTopAtom and sendToBottomAtom", () => {
  it("move a cell to the ends of its column", () => {
    const { store, order, notebook } = setup({ c3: cell("c3", "z = 3") });

    store.set(sendToBottomAtom, { cellId: c1 });
    expect(order()).toEqual([c2, c3, c1]);
    expect(notebook().scrollKey).toBe(c1);

    store.set(sendToTopAtom, { cellId: c1, scroll: false });
    expect(order()).toEqual([c1, c2, c3]);
  });

  it("send a folded header with its section and leave an edge cell alone", () => {
    const { store, model, order, heading } = setup({
      c3: cell("c3", "z = 3"),
    });
    heading(c1, 1);
    store.set(collapseCellAtom, { cellId: c1 });
    const before = store.get(model.documentAtom);

    store.set(sendToTopAtom, { cellId: c1 });
    expect(store.get(model.documentAtom)).toBe(before);

    store.set(sendToBottomAtom, { cellId: c1 });
    expect(order()).toEqual([c1, c2, c3]);
  });
});

describe("drag and drop", () => {
  it("drops a cell where another cell is, in its own column", () => {
    const { store, order } = setup({ c3: cell("c3", "z = 3") });
    store.set(dropCellOverCellAtom, { cellId: c1, overCellId: c3 });
    expect(order()).toEqual([c2, c3, c1]);
    store.set(dropCellOverCellAtom, { cellId: c1, overCellId: c2 });
    expect(order()).toEqual([c1, c2, c3]);
  });

  it("drops a cell before another cell in another column", () => {
    const { store, columns, cellIn } = twoColumns();
    store.set(dropCellOverCellAtom, { cellId: c1, overCellId: c4 });
    expect(columns()).toEqual([[c2], [c3, c1, c4]]);
    expect(cellIn(c2)?.config.column).toBe(0);
    expect(cellIn(c3)?.config.column).toBe(1);
  });

  it("drops a cell at the start of a column", () => {
    const { store, columns } = twoColumns();
    const column = store.get(layoutAtom).columns[0].id;
    store.set(dropCellOverColumnAtom, { cellId: c4, columnId: column });
    expect(columns()).toEqual([[c4, c1, c2], [c3]]);
  });

  it("ignores a drop on a column that is gone", () => {
    const { store, model, columns } = twoColumns();
    const before = store.get(model.documentAtom);
    store.set(dropCellOverColumnAtom, {
      cellId: c4,
      columnId: "gone" as never,
    });
    expect(store.get(model.documentAtom)).toBe(before);
    expect(columns()).toEqual([
      [c1, c2],
      [c3, c4],
    ]);
  });
});

describe("moveCellToIndexAtom", () => {
  it("moves a cell to an index in its column or another", () => {
    const { store, columns } = twoColumns();
    const [first, second] = store.get(layoutAtom).columns.map((c) => c.id);

    store.set(moveCellToIndexAtom, { cellId: c1, columnId: first, index: 2 });
    expect(columns()).toEqual([
      [c2, c1],
      [c3, c4],
    ]);

    store.set(moveCellToIndexAtom, { cellId: c1, columnId: second, index: 1 });
    expect(columns()).toEqual([[c2], [c3, c1, c4]]);

    store.set(moveCellToIndexAtom, { cellId: c2, columnId: second, index: 99 });
    expect(columns()).toEqual([[], [c3, c1, c4, c2]]);
  });
});

describe("moveCellsRelativeToAtom", () => {
  it("moves cells after a target and records how to undo it", () => {
    const { store, order, notebook } = setup({ c3: cell("c3", "z = 3") });
    const column = store.get(layoutAtom).columns[0].id;

    store.set(moveCellsRelativeToAtom, {
      cellIds: [c1, c2],
      targetCellId: c3,
      position: "after",
      previousPlacements: [
        { columnId: column, index: 0 as CellIndex },
        { columnId: column, index: 1 as CellIndex },
      ],
    });
    expect(order()).toEqual([c3, c1, c2]);
    expect(notebook().history).toEqual([
      {
        type: "move",
        cellIds: [c1, c2],
        placements: [
          { columnId: column, index: 0 },
          { columnId: column, index: 1 },
        ],
      },
    ]);

    store.set(undoDeleteCellAtom);
    expect(order()).toEqual([c1, c2, c3]);
    expect(notebook().history).toEqual([]);
    expect(notebook().scrollKey).toBe(c1);
  });

  it("moves cells before a target, and to the end when the target moves too", () => {
    const { store, order, notebook } = setup({ c3: cell("c3", "z = 3") });

    store.set(moveCellsRelativeToAtom, {
      cellIds: [c3],
      targetCellId: c1,
      position: "before",
    });
    expect(order()).toEqual([c3, c1, c2]);
    expect(notebook().history).toEqual([]);

    store.set(moveCellsRelativeToAtom, {
      cellIds: [c3, c1],
      targetCellId: c1,
      position: "before",
    });
    expect(order()).toEqual([c2, c3, c1]);
  });
});

describe("columns", () => {
  it("adds a column after another with a new cell, and names it", () => {
    const { store, columns, notebook, cellIn } = setup();
    const [first] = store.get(layoutAtom).columns.map((c) => c.id);

    store.set(addColumnAtom, { columnId: first });

    const [left, right] = store.get(layoutAtom).columns;
    expect(left.id).toBe(first);
    expect(right.ids).toHaveLength(1);
    const id = right.ids[0];
    expect(columns()).toEqual([[c1, c2], [id]]);
    expect(cellIn(id)?.config.column).toBe(1);
    expect(store.get(columnIdsAtom)).toEqual([first, right.id]);
    expect(notebook().scrollKey).toBe(id);
  });

  it("starts a column at a cell, but not at the first cell", () => {
    const { store, model, columns, cellIn } = setup({
      c3: cell("c3", "z = 3"),
    });
    const before = store.get(model.documentAtom);

    store.set(addColumnBreakpointAtom, { cellId: c1 });
    expect(store.get(model.documentAtom)).toBe(before);

    store.set(addColumnBreakpointAtom, { cellId: c2 });
    expect(columns()).toEqual([[c1], [c2, c3]]);
    expect(cellIn(c2)?.config.column).toBe(1);
    expect(store.get(layoutAtom).columns).toHaveLength(2);
  });

  it("deletes a column into the one before it, or after it for the first", () => {
    const { store, columns, cellIn } = twoColumns();
    const [first, second] = store.get(layoutAtom).columns.map((c) => c.id);

    store.set(deleteColumnAtom, { columnId: first });
    expect(columns()).toEqual([[c1, c2, c3, c4]]);
    expect(cellIn(c3)?.config.column).toBeNull();
    expect(store.get(columnIdsAtom)).toEqual([second]);

    store.set(deleteColumnAtom, { columnId: second });
    expect(columns()).toEqual([[c1, c2, c3, c4]]);
  });

  it("merges every column into the first", () => {
    const { store, columns, cellIn } = twoColumns();
    const [first] = store.get(layoutAtom).columns.map((c) => c.id);

    store.set(mergeAllColumnsAtom);

    expect(columns()).toEqual([[c1, c2, c3, c4]]);
    expect(cellIn(c3)?.config.column).toBeNull();
    expect(store.get(layoutAtom).columns.map((c) => c.id)).toEqual([first]);
  });

  it("compacts the columns a drag left empty", () => {
    const { store, columns } = twoColumns();
    const [first, second] = store.get(layoutAtom).columns.map((c) => c.id);
    store.set(dropCellOverColumnAtom, { cellId: c3, columnId: first });
    store.set(dropCellOverColumnAtom, { cellId: c4, columnId: first });
    expect(columns()).toEqual([[c4, c3, c1, c2], []]);
    expect(store.get(layoutAtom).columns.map((c) => c.id)).toEqual([
      first,
      second,
    ]);

    store.set(compactColumnsAtom);

    expect(columns()).toEqual([[c4, c3, c1, c2]]);
    expect(store.get(columnIdsAtom)).toEqual([first]);
  });

  it("moves a column, keeping its id with it", () => {
    const { store, columns, cellIn } = twoColumns();
    const [first, second] = store.get(layoutAtom).columns.map((c) => c.id);

    store.set(moveColumnAtom, { column: first, overColumn: second });
    expect(columns()).toEqual([
      [c3, c4],
      [c1, c2],
    ]);
    expect(store.get(layoutAtom).columns.map((c) => c.id)).toEqual([
      second,
      first,
    ]);
    expect(cellIn(c3)?.config.column).toBe(0);
    expect(cellIn(c1)?.config.column).toBe(1);

    store.set(moveColumnAtom, { column: first, overColumn: "_left_" });
    expect(columns()).toEqual([
      [c1, c2],
      [c3, c4],
    ]);
    expect(store.get(layoutAtom).columns.map((c) => c.id)).toEqual([
      first,
      second,
    ]);
  });
});
