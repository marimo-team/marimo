/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import { SETUP_CELL_ID } from "@/core/cells/ids";
import {
  type CellColumnId,
  type CellIndex,
  CollapsibleTree,
  MultiColumn,
} from "../id-tree";

let tree: CollapsibleTree<string>;

describe("CollapsibleTree", () => {
  beforeEach(() => {
    tree = CollapsibleTree.from(["one", "two", "three", "four"]);
  });

  it("initializes correctly", () => {
    expect(tree.toString()).toMatchInlineSnapshot(`
			"one
			two
			three
			four
			"
		`);
  });

  it("inserts nodes correctly", () => {
    tree = tree.insert("newNode", 1);
    expect(tree.toString()).toMatchInlineSnapshot(`
			"one
			newNode
			two
			three
			four
			"
		`);

    tree = tree.insert("newNode2", tree.length - 1);
    expect(tree.toString()).toMatchInlineSnapshot(`
      "one
      newNode
      two
      three
      newNode2
      four
      "
    `);

    tree = tree.insert("newNode3", 10_000);
    expect(tree.toString()).toMatchInlineSnapshot(`
      "one
      newNode
      two
      three
      newNode2
      four
      newNode3
      "
    `);
  });

  it("can delete non-collapsed nodes without throwing", () => {
    // Deleting a non-collapsed node should not throw
    // (previously this would throw "Node is already expanded" internally)
    const result = tree.deleteAtIndex(1);
    expect(result.toString()).toMatchInlineSnapshot(`
      "one
      three
      four
      "
    `);
  });

  it("fails to delete nodes", () => {
    expect(() => tree.deleteAtIndex(5)).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node at index 5 not found in tree]",
    );
  });

  it("atOrThrow throws if not found", () => {
    expect(() => tree.atOrThrow(5)).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node at index 5 not found in tree]",
    );
  });

  it("first and last are correct", () => {
    expect(tree.first()).toBe("one");
    expect(tree.last()).toBe("four");
  });

  it("handles slice correctly", () => {
    // Normal slice in middle
    expect(tree.slice(1, 3)).toEqual(["two", "three"]);

    // Slice from beginning
    expect(tree.slice(0, 2)).toEqual(["one", "two"]);

    // Slice to end
    expect(tree.slice(2, 4)).toEqual(["three", "four"]);

    // Slice entire array
    expect(tree.slice(0, 4)).toEqual(["one", "two", "three", "four"]);

    // Slice with out-of-bounds end
    expect(tree.slice(2, 10)).toEqual(["three", "four"]);

    // Slice with negative start (should work like normal array slice)
    expect(tree.slice(-2, 4)).toEqual(["three", "four"]);

    // Slice with start > end (should return empty array)
    expect(tree.slice(3, 1)).toEqual([]);

    // Slice with same start and end
    expect(tree.slice(2, 2)).toEqual([]);

    // Slice single element
    expect(tree.slice(1, 2)).toEqual(["two"]);
  });

  it("handles after correctly", () => {
    // Normal case - get next node
    expect(tree.after("one")).toBe("two");
    expect(tree.after("two")).toBe("three");
    expect(tree.after("three")).toBe("four");

    // Edge case - last node should return undefined
    expect(tree.after("four")).toBeUndefined();

    // Edge case - non-existent node should throw
    expect(() => tree.after("nonexistent")).toThrow(
      "Node nonexistent not found in tree. Valid ids: one,two,three,four",
    );
  });

  it("handles before correctly", () => {
    // Normal case - get previous node
    expect(tree.before("two")).toBe("one");
    expect(tree.before("three")).toBe("two");
    expect(tree.before("four")).toBe("three");

    // Edge case - first node should return undefined
    expect(tree.before("one")).toBeUndefined();

    // Edge case - non-existent node should throw
    expect(() => tree.before("nonexistent")).toThrow(
      "Node nonexistent not found in tree. Valid ids: one,two,three,four",
    );
  });

  it("handles slice on empty tree", () => {
    const emptyTree = CollapsibleTree.from([]);
    expect(emptyTree.slice(0, 1)).toEqual([]);
    expect(emptyTree.slice(0, 0)).toEqual([]);
  });

  it("handles after/before on single element tree", () => {
    const singleTree = CollapsibleTree.from(["single"]);
    expect(singleTree.after("single")).toBeUndefined();
    expect(singleTree.before("single")).toBeUndefined();
  });

  it("handles split correctly", () => {
    const [left, right] = tree.split("two");
    expect(left.toString()).toMatchInlineSnapshot(`
      "one
      "
    `);
    expect(right?.toString()).toMatchInlineSnapshot(`
      "two
      three
      four
      "
    `);
  });

  it("handles split at the beginning", () => {
    const [left, right] = tree.split("one");
    expect(left.toString()).toMatchInlineSnapshot(`
      ""
    `);
    expect(right?.toString()).toMatchInlineSnapshot(`
      "one
      two
      three
      four
      "
    `);
  });

  it("handles split at the end", () => {
    const [left, right] = tree.split("four");
    expect(left.toString()).toMatchInlineSnapshot(`
      "one
      two
      three
      "
    `);
    expect(right?.toString()).toMatchInlineSnapshot(`
      "four
      "
    `);
  });

  it("throws when splitting on non-existent node", () => {
    expect(() => tree.split("five")).toThrow("Node five not found in tree");
  });
});

describe("CollapsibleTree edge cases", () => {
  let tree: CollapsibleTree<string>;

  beforeEach(() => {
    tree = CollapsibleTree.from(["A", "B", "C", "D"]);
  });

  it("handles insert at start and end", () => {
    tree = tree.insertAtStart("Z");
    expect(tree.topLevelIds).toEqual(["Z", "A", "B", "C", "D"]);
    tree = tree.insertAtEnd("Y");
    expect(tree.topLevelIds).toEqual(["Z", "A", "B", "C", "D", "Y"]);
  });

  it("handles edge cases for first and last", () => {
    expect(tree.first()).toBe("A");
    expect(tree.last()).toBe("D");
    tree = CollapsibleTree.from([]);
    expect(() => tree.first()).toThrow("Node at index 0 not found in tree");
    expect(() => tree.last()).toThrow("Node at index -1 not found in tree");
  });
});

describe("MultiColumn", () => {
  let multiColumn: MultiColumn<string>;
  let columnIds: CellColumnId[];

  beforeEach(() => {
    multiColumn = MultiColumn.from([
      ["A1", "A2", "A3"],
      ["B1", "B2"],
      ["C1", "C2", "C3", "C4"],
    ]);

    columnIds = multiColumn.getColumns().map((c) => c.id);
  });

  it("initializes correctly", () => {
    expect(multiColumn.colLength).toBe(3);
    expect(multiColumn.idLength).toBe(9);
    expect(multiColumn.topLevelIds).toEqual([
      ["A1", "A2", "A3"],
      ["B1", "B2"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("creates from empty array", () => {
    const emptyMultiColumn = MultiColumn.from([]);
    expect(emptyMultiColumn.colLength).toBe(1);
    expect(emptyMultiColumn.idLength).toBe(0);
    expect(emptyMultiColumn.isEmpty()).toBe(true);
  });

  it("creates from ids and columns", () => {
    const idAndColumns: [string, number | undefined | null][] = [
      ["A1", 0],
      ["A2", 0],
      ["B1", 1],
      ["C1", 2],
      ["C2", undefined],
      ["D1", null],
      ["E1", -1],
    ];
    const fromIdsAndColumns = MultiColumn.fromIdsAndColumns(idAndColumns);
    expect(fromIdsAndColumns.colLength).toBe(3);
    expect(fromIdsAndColumns.topLevelIds).toEqual([
      ["A1", "A2"],
      ["B1"],
      ["C1", "C2", "D1", "E1"],
    ]);
  });

  it("iterates top-level ids", () => {
    const ids = [...multiColumn.iterateTopLevelIds];
    expect(ids).toEqual(["A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C4"]);
  });

  it("gets in-order ids", () => {
    expect(multiColumn.inOrderIds).toEqual([
      "A1",
      "A2",
      "A3",
      "B1",
      "B2",
      "C1",
      "C2",
      "C3",
      "C4",
    ]);
  });

  it("checks if it has only one column", () => {
    expect(multiColumn.hasOnlyOneColumn()).toBe(false);
    const singleColumn = MultiColumn.from([["A1", "A2"]]);
    expect(singleColumn.hasOnlyOneColumn()).toBe(true);
  });

  it("checks if it has only one id", () => {
    expect(multiColumn.hasOnlyOneId()).toBe(false);
    const singleId = MultiColumn.from([["A1"], ["B1"], ["C1"]]);
    expect(singleId.hasOnlyOneId()).toBe(false);
    const singleIdSingleColumn = MultiColumn.from([["A1"]]);
    expect(singleIdSingleColumn.hasOnlyOneId()).toBe(true);
  });

  it("adds a column", () => {
    const columnId = multiColumn.getColumns()[0].id;
    const newMultiColumn = multiColumn.addColumn(columnId);
    expect(newMultiColumn.colLength).toBe(4);
    expect(newMultiColumn.topLevelIds[1]).toEqual([]);
  });

  it("inserts a breakpoint", () => {
    const withBreakpoint = multiColumn.insertBreakpoint("C3");
    expect(withBreakpoint.colLength).toBe(4);
    expect(withBreakpoint.topLevelIds).toEqual([
      ["A1", "A2", "A3"],
      ["B1", "B2"],
      ["C1", "C2"],
      ["C3", "C4"],
    ]);
  });

  it("deletes a column", () => {
    const withoutBreakpoint = multiColumn.delete(columnIds[1]);
    expect(withoutBreakpoint.colLength).toBe(2);
    expect(withoutBreakpoint.topLevelIds).toEqual([
      ["A1", "A2", "A3", "B1", "B2"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("deletes a column with only one column", () => {
    const singleColumn = MultiColumn.from([["A1", "A2"]]);
    const deleted = singleColumn.delete(columnIds[0]);
    expect(deleted.colLength).toBe(1);
    expect(deleted.topLevelIds).toEqual([["A1", "A2"]]);
  });

  it("deletes the first column", () => {
    const deleted = multiColumn.delete(columnIds[0]);
    expect(deleted.colLength).toBe(2);
    expect(deleted.topLevelIds).toEqual([
      ["B1", "B2", "A1", "A2", "A3"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("merges all columns", () => {
    const merged = multiColumn.mergeAllColumns();
    expect(merged.colLength).toBe(1);
    expect(merged.topLevelIds).toEqual([
      ["A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C4"],
    ]);
  });

  it("moves a column", () => {
    const moved = multiColumn.moveColumn(columnIds[0], columnIds[2]);
    expect(moved.topLevelIds).toEqual([
      ["B1", "B2"],
      ["C1", "C2", "C3", "C4"],
      ["A1", "A2", "A3"],
    ]);
  });

  it("moves a column before", () => {
    const moved = multiColumn.moveColumn(columnIds[1], columnIds[0]);
    expect(moved.topLevelIds).toEqual([
      ["B1", "B2"],
      ["A1", "A2", "A3"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("moves to the left", () => {
    const moved = multiColumn.moveColumn(columnIds[1], "_left_");
    expect(moved.topLevelIds).toEqual([
      ["B1", "B2"],
      ["A1", "A2", "A3"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("moves to the right", () => {
    const moved = multiColumn.moveColumn(columnIds[1], "_right_");
    expect(moved.topLevelIds).toEqual([
      ["A1", "A2", "A3"],
      ["C1", "C2", "C3", "C4"],
      ["B1", "B2"],
    ]);
  });

  it("gets column with id", () => {
    const column = multiColumn.findWithId("B2");
    expect(multiColumn.indexOf(column)).toBe(1);
    expect(column.topLevelIds).toEqual(["B1", "B2"]);
  });

  it("transforms by id", () => {
    const transformed = multiColumn.transformWithCellId("B1", (tree) =>
      tree.delete("B1"),
    );
    expect(transformed.topLevelIds[1]).toEqual(["B2"]);
  });

  it("transforms all columns", () => {
    const transformed = multiColumn.transformAll((tree) =>
      tree.insertAtStart("NEW"),
    );
    expect(transformed.topLevelIds).toEqual([
      ["NEW", "A1", "A2", "A3"],
      ["NEW", "B1", "B2"],
      ["NEW", "C1", "C2", "C3", "C4"],
    ]);
  });

  it("inserts an id", () => {
    const inserted = multiColumn.insertId("D1", columnIds[1], 1 as CellIndex);
    expect(inserted.topLevelIds[1]).toEqual(["B1", "D1", "B2"]);
  });

  it("compacts", () => {
    const withEmpty = MultiColumn.from([["A1"], [], ["C1"], []]);
    const compacted = withEmpty.compact();
    expect(compacted.colLength).toBe(2);
    expect(compacted.topLevelIds).toEqual([["A1"], ["C1"]]);
  });

  it("handles errors", () => {
    expect(() => multiColumn.findWithId("Z1")).toThrow(
      "Cell Z1 not found in any column",
    );
    expect(multiColumn.colLength).toBeGreaterThan(2);
    expect(() => multiColumn.delete("123" as CellColumnId)).toThrow(
      /Column 123 not found/,
    );
  });

  it("checks if it's empty", () => {
    expect(multiColumn.isEmpty()).toBe(false);
    const emptyMultiColumn = MultiColumn.from([[]]);
    expect(emptyMultiColumn.isEmpty()).toBe(true);
  });

  it("gets columns", () => {
    const columns = multiColumn.getColumns();
    expect(columns.length).toBe(3);
    expect(columns[0].topLevelIds).toEqual(["A1", "A2", "A3"]);
  });

  it("gets index of a column", () => {
    const column = multiColumn.atOrThrow(1);
    const index = multiColumn.indexOf(column);
    expect(index).toBe(1);
  });

  it("handles at and atOrThrow", () => {
    expect(multiColumn.at(1)?.topLevelIds).toEqual(["B1", "B2"]);
    expect(multiColumn.atOrThrow(1).topLevelIds).toEqual(["B1", "B2"]);
    expect(multiColumn.at(5)).toBeUndefined();
    expect(() => multiColumn.atOrThrow(5)).toThrow("Column 5 not found");
  });

  it("handles inserting at out-of-bounds indices", () => {
    const multiColumn = MultiColumn.from([["A1"], ["B1"]]);
    const columnId = multiColumn.atOrThrow(1).id;
    const inserted = multiColumn.insertId("C1", columnId, 10 as CellIndex);
    expect(inserted.topLevelIds).toEqual([["A1"], ["B1", "C1"]]);
  });

  it("handles moving a column to its own position", () => {
    const multiColumn = MultiColumn.from([["A1"], ["B1"], ["C1"]]);
    const moved = multiColumn.moveColumn(columnIds[1], columnIds[1]);
    expect(moved.topLevelIds).toEqual([["A1"], ["B1"], ["C1"]]);
  });

  it("handles compacting when all columns are empty", () => {
    const multiColumn = MultiColumn.from([[], [], []]);
    const compacted = multiColumn.compact();
    expect(compacted.colLength).toBe(1);
    expect(compacted.isEmpty()).toBe(true);
  });

  it("handles transformById when id is not found", () => {
    const multiColumn = MultiColumn.from([["A1"], ["B1"]]);
    const transformed = multiColumn.transformWithCellId("C1", (tree) =>
      tree.insertAtEnd("C2"),
    );
    expect(transformed).toBe(multiColumn);
  });

  it("handles multiple operations in sequence", () => {
    let multiColumn = MultiColumn.from([
      ["A1", "A2"],
      ["B1", "B2"],
      ["C1", "C2"],
    ]);
    const columnIds = multiColumn.getColumns().map((c) => c.id);
    multiColumn = multiColumn.insertId("D1", columnIds[2], 1 as CellIndex);
    expect(multiColumn.topLevelIds).toEqual([
      ["A1", "A2"],
      ["B1", "B2"],
      ["C1", "D1", "C2"],
    ]);
    multiColumn = multiColumn.transformWithCellId("B1", (tree) =>
      tree.delete("B1"),
    );
    expect(multiColumn.topLevelIds).toEqual([
      ["A1", "A2"],
      ["B2"],
      ["C1", "D1", "C2"],
    ]);
    multiColumn = multiColumn.moveColumn(columnIds[0], columnIds[2]);
    expect(multiColumn.topLevelIds).toEqual([
      ["B2"],
      ["C1", "D1", "C2"],
      ["A1", "A2"],
    ]);
    multiColumn = multiColumn.compact();
    expect(multiColumn.topLevelIds).toEqual([
      ["B2"],
      ["C1", "D1", "C2"],
      ["A1", "A2"],
    ]);
  });

  it("handles setup cell existence", () => {
    const multiColumn = MultiColumn.from([["A1"], ["B1"], ["C1"]]);
    const columnIds = multiColumn.getColumnIds();
    expect(multiColumn.setupCellExists()).toBe(false);
    const multiColumn2 = multiColumn.insertId(SETUP_CELL_ID, columnIds[0], 0);
    expect(multiColumn2.setupCellExists()).toBe(true);
    const multiColumn3 = multiColumn2.transformWithCellId(
      SETUP_CELL_ID,
      (tree) => tree.delete(SETUP_CELL_ID),
    );
    expect(multiColumn3.setupCellExists()).toBe(false);
  });

  it("handles get method", () => {
    const column = multiColumn.get(columnIds[1]);
    expect(column?.topLevelIds).toEqual(["B1", "B2"]);
  });

  it("handles get method with non-existent column id", () => {
    const column = multiColumn.get("non-existent-id" as CellColumnId);
    expect(column).toBeUndefined();
  });

  it("handles indexOfOrThrow method", () => {
    expect(multiColumn.indexOfOrThrow(columnIds[1])).toBe(1);
  });

  it("handles indexOfOrThrow method with non-existent column id", () => {
    expect(() =>
      multiColumn.indexOfOrThrow("non-existent-id" as CellColumnId),
    ).toThrow("Column non-existent-id not found. Possible values: ");
  });

  it("handles transform method", () => {
    const transformed = multiColumn.transform(columnIds[1], (tree) =>
      tree.delete("B1"),
    );
    expect(transformed.topLevelIds[1]).toEqual(["B2"]);
  });

  it("handles transform method with non-existent column id", () => {
    const transformed = multiColumn.transform(
      "non-existent-id" as CellColumnId,
      (tree) => tree.delete("B2"),
    );
    const columns1 = multiColumn.getColumns();
    const columns2 = transformed.getColumns();
    const allEqual = columns1.every((c, i) => c.equals(columns2[i]));
    expect(allEqual).toBe(true);
    expect(transformed).toBe(multiColumn);
  });

  it("handles inserting a breakpoint at the start of a column", () => {
    const withBreakpoint = multiColumn.insertBreakpoint("A1");
    expect(withBreakpoint.colLength).toBe(4);
    expect(withBreakpoint.topLevelIds).toEqual([
      [],
      ["A1", "A2", "A3"],
      ["B1", "B2"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("handles inserting a breakpoint at the end of a column", () => {
    const withBreakpoint = multiColumn.insertBreakpoint("A3");
    expect(withBreakpoint.colLength).toBe(4);
    expect(withBreakpoint.topLevelIds).toEqual([
      ["A1", "A2"],
      ["A3"],
      ["B1", "B2"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("handles inserting a breakpoint in a single-item column", () => {
    const singleItemColumn = MultiColumn.from([["A1"], ["B1"], ["C1"]]);
    const withBreakpoint = singleItemColumn.insertBreakpoint("B1");
    expect(withBreakpoint.colLength).toBe(4);
    expect(withBreakpoint.topLevelIds).toEqual([["A1"], [], ["B1"], ["C1"]]);
  });
});
