/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import {
  CollapsibleTree,
  MultiColumn,
  type CellColumnId,
  type CellIndex,
} from "../id-tree";
import { beforeEach } from "vitest";

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

  it("collapses nodes correctly with no end", () => {
    const collapsedTree = tree.collapse("two", undefined);
    expect(collapsedTree.nodes[1].isCollapsed).toBe(true);
    expect(collapsedTree.isCollapsed("two")).toBe(true);
    expect(collapsedTree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three
			  four
			"
		`);
  });

  it("collapses nodes correctly with an 'until' in the middle", () => {
    const collapsedTree = tree.collapse("two", "three");
    expect(collapsedTree.nodes[1].isCollapsed).toBe(true);
    expect(collapsedTree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three
			four
			"
		`);
  });

  it("collapses nodes correctly with an 'until' at the end", () => {
    const collapsedTree = tree.collapse("two", "four");
    expect(collapsedTree.nodes[1].isCollapsed).toBe(true);
    expect(collapsedTree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three
			  four
			"
		`);
  });

  it("collapses nodes correctly if just the last node", () => {
    const collapsedTree = tree.collapse("four", undefined);
    expect(collapsedTree.nodes[3].isCollapsed).toBe(true);
    expect(collapsedTree.toString()).toMatchInlineSnapshot(`
			"one
			two
			three
			four (collapsed)
			"
		`);
  });

  it("collapses nodes correctly if just the first node", () => {
    const collapsedTree = tree.collapse("one", undefined);
    expect(collapsedTree.nodes[0].isCollapsed).toBe(true);
    expect(collapsedTree.toString()).toMatchInlineSnapshot(`
			"one (collapsed)
			  two
			  three
			  four
			"
		`);
  });

  it("can double collapse", () => {
    const collapsedTree = tree
      .collapse("three", undefined)
      .collapse("two", undefined);
    expect(collapsedTree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three (collapsed)
			    four
			"
		`);
  });

  it("failures to collapse", () => {
    expect(() =>
      tree.collapse("five", undefined),
    ).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node five not found in tree. Valid ids: one,two,three,four]",
    );
    expect(() =>
      tree.collapse("one", "five"),
    ).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node five not found in tree]",
    );
    expect(() =>
      tree.collapse("two", "one"),
    ).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node one is before node two]",
    );

    expect(() => {
      tree = tree.collapse("two", undefined);
      tree = tree.collapse("two", undefined);
    }).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node two is already collapsed]",
    );
  });

  it("expands nodes correctly", () => {
    const collapsed = tree.collapse("two", undefined);
    expect(collapsed.nodes[1].isCollapsed).toBe(true);
    const expandedTree = collapsed.expand("two");
    expect(expandedTree.nodes[1].isCollapsed).toBe(false);
    expect(expandedTree.toString()).toMatchInlineSnapshot(`
			"one
			two
			three
			four
			"
		`);
  });

  it("fails to expand", () => {
    expect(() => tree.expand("five")).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node five not found in tree. Valid ids: one,two,three,four]",
    );
    expect(() => {
      tree.expand("one");
      tree.expand("one");
    }).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node one is already expanded]",
    );
  });

  it("moves nodes correctly", () => {
    const movedTree = tree.move(0, 1);
    expect(movedTree.toString()).toMatchInlineSnapshot(`
      "two
      one
      three
      four
      "
    `);
  });

  it("moves a collapsed node correctly", () => {
    const collapsed = tree.collapse("two", "three");
    expect(collapsed.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three
			four
			"
		`);
    const movedTree = collapsed.move(1, 2);
    expect(movedTree.toString()).toMatchInlineSnapshot(`
			"one
			four
			two (collapsed)
			  three
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

  it("counts children correctly", () => {
    expect(tree.getCount("who")).toBe(0);
    expect(tree.getCount("one")).toBe(0);
    // Collapse three and get count
    tree = tree.collapse("three", undefined);
    expect(tree.getCount("three")).toBe(1);
    // Collapse two and get count
    tree = tree.collapse("two", undefined);
    expect(tree.getCount("two")).toBe(2);
  });

  it("finds deep correctly", () => {
    expect(tree.find("three")).toEqual(["three"]);
    tree = tree.collapse("three", undefined).collapse("two", undefined);
    expect(tree.find("three")).toEqual(["two", "three"]);
    expect(tree.find("four")).toEqual(["two", "three", "four"]);
    expect(tree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three (collapsed)
			    four
			"
		`);
  });

  it("finds and expands correctly at a leaf", () => {
    tree = tree.collapse("three", undefined).collapse("two", undefined);
    expect(tree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three (collapsed)
			    four
			"
		`);
    const prevTree = tree;
    tree = tree.findAndExpandDeep("four");
    expect(tree.toString()).toMatchInlineSnapshot(`
      "one
      two
      three
      four
      "
    `);
    // doesn't mutate
    expect(prevTree.toString()).not.toEqual(tree.toString());
  });

  it("finds and expands correctly at a non-leaf", () => {
    tree = tree.collapse("three", undefined).collapse("two", undefined);
    expect(tree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three (collapsed)
			    four
			"
		`);
    const prevTree = tree;
    tree = tree.findAndExpandDeep("three");
    expect(tree.toString()).toMatchInlineSnapshot(`
      "one
      two
      three
      four
      "
    `);
    // doesn't mutate
    expect(prevTree.toString()).not.toEqual(tree.toString());
  });

  it("can delete nodes", () => {
    tree = tree.collapse("three", undefined).collapse("two", undefined);
    expect(tree.toString()).toMatchInlineSnapshot(`
			"one
			two (collapsed)
			  three (collapsed)
			    four
			"
		`);
    tree = tree.deleteAtIndex(1);
    expect(tree.toString()).toMatchInlineSnapshot(`
      "one
      three (collapsed)
        four
      "
    `);
  });

  it("fails to delete nodes", () => {
    expect(() => tree.deleteAtIndex(5)).toThrowErrorMatchingInlineSnapshot(
      "[Error: Node at index 5 not found in tree]",
    );
  });

  it("top-level ids are correct", () => {
    expect(tree.topLevelIds).toMatchInlineSnapshot(`
			[
			  "one",
			  "two",
			  "three",
			  "four",
			]
		`);

    const collapsed = tree.collapse("two", undefined);
    expect(collapsed.topLevelIds).toMatchInlineSnapshot(`
			[
			  "one",
			  "two",
			]
		`);
  });

  it("in order ids are correct", () => {
    expect(tree.inOrderIds).toMatchInlineSnapshot(`
      [
        "one",
        "two",
        "three",
        "four",
      ]
    `);

    const collapsed = tree.collapse("two", undefined);

    // Not mutable
    expect(tree.inOrderIds).toEqual(tree.inOrderIds);

    expect(collapsed.inOrderIds).toMatchInlineSnapshot(`
      [
        "one",
        "two",
        "three",
        "four",
      ]
    `);
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

  it("length is correct", () => {
    expect(tree.length).toBe(4);

    const collapsed = tree.collapse("two", undefined);
    expect(collapsed.length).toBe(2);
  });

  it("moves to front and back correctly", () => {
    tree = tree.collapse("three", undefined).moveToBack("three");
    expect(tree.toString()).toMatchInlineSnapshot(`
      "one
      two
      three (collapsed)
        four
      "
    `);

    tree = tree.moveToFront("two");
    expect(tree.toString()).toMatchInlineSnapshot(`
      "two
      one
      three (collapsed)
        four
      "
    `);
  });

  it("getDescendants correctly", () => {
    expect(tree.getDescendants("two")).toEqual([]);
    expect(tree.getDescendants("who")).toEqual([]);

    tree = tree.collapse("three", undefined).collapse("two", undefined);
    expect(tree.getDescendants("two")).toMatchInlineSnapshot(`
      [
        "three",
        "four",
      ]
    `);

    // We only get descendants of the top level
    expect(tree.getDescendants("three")).toMatchInlineSnapshot("[]");
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

  it("handles delete with expand", () => {
    tree = tree.collapse("B", "D");
    tree = tree.deleteAtIndex(1);
    expect(tree.topLevelIds).toEqual(["A", "C", "D"]);
  });

  it("finds nodes correctly", () => {
    tree = tree.collapse("B", "D");
    expect(tree.find("C")).toEqual(["B", "C"]);
    expect(tree.find("E")).toEqual([]);
  });

  it("handles equality check", () => {
    const tree2 = CollapsibleTree.from(["A", "B", "C", "D"]);
    expect(tree.equals(tree2)).toBe(true);
    tree2.collapse("B", "C");
    expect(tree.equals(tree2)).toBe(true);
  });

  it("handles getCount correctly", () => {
    tree = tree.collapse("B", "D");
    expect(tree.getCount("A")).toBe(0);
    expect(tree.getCount("B")).toBe(2);
    expect(tree.getCount("C")).toBe(0);
  });

  it("handles findAndExpandDeep", () => {
    tree = tree.collapse("B", "D");
    tree = tree.findAndExpandDeep("C");
    expect(tree.topLevelIds).toEqual(["A", "B", "C", "D"]);
  });

  it("handles multiple collapses and expands", () => {
    tree = tree.collapse("B", "C").collapse("A", "D");
    expect(tree.topLevelIds).toEqual(["A"]);
    tree = tree.expand("A").expand("B");
    expect(tree.topLevelIds).toEqual(["A", "B", "C", "D"]);
  });

  it("handles edge cases for first and last", () => {
    expect(tree.first()).toBe("A");
    expect(tree.last()).toBe("D");
    tree = CollapsibleTree.from([]);
    expect(() => tree.first()).toThrow();
    expect(() => tree.last()).toThrow();
  });

  it("handles inOrderIds with nested structure", () => {
    tree = tree.collapse("B", "C");
    expect(tree.inOrderIds).toEqual(["A", "B", "C", "D"]);
  });

  it("handles moving within bounds", () => {
    tree = tree.move(0, 2);
    expect(tree.topLevelIds).toEqual(["B", "C", "A", "D"]);
  });

  it("handles moving out of bounds", () => {
    tree = tree.move(0, 10);
    expect(tree.topLevelIds).toEqual(["B", "C", "D", "A"]);
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
    const idAndColumns: Array<[string, number | undefined | null]> = [
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

  it("moves within a column", () => {
    const moved = multiColumn.moveWithinColumn(
      columnIds[0],
      0 as CellIndex,
      2 as CellIndex,
    );
    expect(moved.topLevelIds[0]).toEqual(["A2", "A3", "A1"]);
  });

  it("moves across columns", () => {
    const moved = multiColumn.moveAcrossColumns(
      columnIds[0],
      "A1",
      columnIds[1],
      "B1",
    );
    expect(moved.topLevelIds).toEqual([
      ["A2", "A3"],
      ["A1", "B1", "B2"],
      ["C1", "C2", "C3", "C4"],
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

  it("moves to a new column", () => {
    const newColumn = multiColumn.moveToNewColumn("B1");
    expect(newColumn.colLength).toBe(4);
    expect(newColumn.topLevelIds).toEqual([
      ["A1", "A2", "A3"],
      ["B2"],
      ["C1", "C2", "C3", "C4"],
      ["B1"],
    ]);
  });

  it("gets column with id", () => {
    const column = multiColumn.findWithId("B2");
    expect(multiColumn.indexOf(column)).toBe(1);
    expect(column.topLevelIds).toEqual(["B1", "B2"]);
  });

  it("transforms by id", () => {
    const transformed = multiColumn.transformWithCellId("B1", (tree) =>
      tree.moveToFront("B2"),
    );
    expect(transformed.topLevelIds[1]).toEqual(["B2", "B1"]);
  });

  it("inserts an id", () => {
    const inserted = multiColumn.insertId("D1", columnIds[1], 1 as CellIndex);
    expect(inserted.topLevelIds[1]).toEqual(["B1", "D1", "B2"]);
  });

  it("deletes by id", () => {
    const deleted = multiColumn.deleteById("B1");
    expect(deleted.topLevelIds[1]).toEqual(["B2"]);
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
    expect(() => multiColumn.delete("123" as CellColumnId)).toThrow();
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
    expect(() => multiColumn.atOrThrow(5)).toThrow();
  });

  it("handles moving the last item in a column", () => {
    const multiColumn = MultiColumn.from([["A1", "A2"], ["B1"]]);
    const columnIds = multiColumn.getColumns().map((c) => c.id);
    const moved = multiColumn.moveAcrossColumns(
      columnIds[1],
      "B1",
      columnIds[0],
      "A2",
    );
    expect(moved.topLevelIds).toEqual([["A1", "B1", "A2"], []]);
    expect(moved.colLength).toBe(2);
  });

  it("handles moving all items from a column", () => {
    const multiColumn = MultiColumn.from([
      ["A1", "A2"],
      ["B1", "B2"],
    ]);
    const columnIds = multiColumn.getColumns().map((c) => c.id);
    let moved = multiColumn.moveAcrossColumns(
      columnIds[1],
      "B1",
      columnIds[0],
      "A2",
    );
    moved = moved.moveAcrossColumns(columnIds[1], "B2", columnIds[0], "A2");
    expect(moved.topLevelIds).toEqual([["A1", "B1", "B2", "A2"], []]);
    expect(moved.colLength).toBe(2);
  });

  it("handles inserting at out-of-bounds indices", () => {
    const multiColumn = MultiColumn.from([["A1"], ["B1"]]);
    const columnId = multiColumn.atOrThrow(1).id;
    const inserted = multiColumn.insertId("C1", columnId, 10 as CellIndex);
    expect(inserted.topLevelIds).toEqual([["A1"], ["B1", "C1"]]);
  });

  it("handles collapsing and expanding in multi-column setup", () => {
    let multiColumn = MultiColumn.from([
      ["A1", "A2", "A3"],
      ["B1", "B2"],
    ]);
    multiColumn = multiColumn.transformWithCellId("A1", (tree) =>
      tree.collapse("A1", "A3"),
    );
    expect(multiColumn.topLevelIds).toEqual([["A1"], ["B1", "B2"]]);
    multiColumn = multiColumn.transformWithCellId("A1", (tree) =>
      tree.expand("A1"),
    );
    expect(multiColumn.topLevelIds).toEqual([
      ["A1", "A2", "A3"],
      ["B1", "B2"],
    ]);
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

  it("handles nested collapses and expands", () => {
    let multiColumn = MultiColumn.from([["A1", "A2", "A3", "A4", "A5"]]);
    multiColumn = multiColumn.transformWithCellId("A1", (tree) =>
      tree.collapse("A2", "A4"),
    );
    multiColumn = multiColumn.transformWithCellId("A1", (tree) =>
      tree.collapse("A1", undefined),
    );
    expect(multiColumn.topLevelIds).toEqual([["A1"]]);
    multiColumn = multiColumn.transformWithCellId("A1", (tree) =>
      tree.expand("A1"),
    );
    expect(multiColumn.topLevelIds).toEqual([["A1", "A2", "A5"]]);
    multiColumn = multiColumn.transformWithCellId("A1", (tree) =>
      tree.expand("A2"),
    );
    expect(multiColumn.topLevelIds).toEqual([["A1", "A2", "A3", "A4", "A5"]]);
  });

  it("handles moving to a new column when it's the last item", () => {
    let multiColumn = MultiColumn.from([["A1"], ["B1"]]);
    multiColumn = multiColumn.moveToNewColumn("B1");
    expect(multiColumn.colLength).toBe(3);
    expect(multiColumn.topLevelIds).toEqual([["A1"], [], ["B1"]]);
  });

  it("handles deleting the last item in a column", () => {
    let multiColumn = MultiColumn.from([["A1"], ["B1"], ["C1"]]);
    multiColumn = multiColumn.deleteById("B1");
    expect(multiColumn.colLength).toBe(3);
    expect(multiColumn.topLevelIds).toEqual([["A1"], [], ["C1"]]);
  });

  it("handles multiple operations in sequence", () => {
    let multiColumn = MultiColumn.from([
      ["A1", "A2"],
      ["B1", "B2"],
      ["C1", "C2"],
    ]);
    const columnIds = multiColumn.getColumns().map((c) => c.id);
    multiColumn = multiColumn.moveAcrossColumns(
      columnIds[0],
      "A2",
      columnIds[1],
      "B1",
    );
    expect(multiColumn.topLevelIds).toEqual([
      ["A1"],
      ["A2", "B1", "B2"],
      ["C1", "C2"],
    ]);
    multiColumn = multiColumn.insertId("D1", columnIds[2], 1 as CellIndex);
    expect(multiColumn.topLevelIds).toEqual([
      ["A1"],
      ["A2", "B1", "B2"],
      ["C1", "D1", "C2"],
    ]);
    multiColumn = multiColumn.deleteById("B1");
    expect(multiColumn.topLevelIds).toEqual([
      ["A1"],
      ["A2", "B2"],
      ["C1", "D1", "C2"],
    ]);
    multiColumn = multiColumn.moveColumn(columnIds[0], columnIds[2]);
    expect(multiColumn.topLevelIds).toEqual([
      ["A2", "B2"],
      ["C1", "D1", "C2"],
      ["A1"],
    ]);
    multiColumn = multiColumn.compact();
    expect(multiColumn.topLevelIds).toEqual([
      ["A2", "B2"],
      ["C1", "D1", "C2"],
      ["A1"],
    ]);
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
      tree.moveToFront("B2"),
    );
    expect(transformed.topLevelIds[1]).toEqual(["B2", "B1"]);
  });

  it("handles transform method with non-existent column id", () => {
    const transformed = multiColumn.transform(
      "non-existent-id" as CellColumnId,
      (tree) => tree.moveToFront("B2"),
    );
    const columns1 = multiColumn.getColumns();
    const columns2 = transformed.getColumns();
    const allEqual = columns1.every((c, i) => c.equals(columns2[i]));
    expect(allEqual).toBe(true);
    expect(transformed).toBe(multiColumn);
  });

  it("handles moving across columns with undefined toId", () => {
    const moved = multiColumn.moveAcrossColumns(
      columnIds[0],
      "A1",
      columnIds[1],
      undefined,
    );
    expect(moved.topLevelIds).toEqual([
      ["A2", "A3"],
      ["A1", "B1", "B2"],
      ["C1", "C2", "C3", "C4"],
    ]);
  });

  it("handles moving across columns to an empty column", () => {
    const emptyColumnMultiColumn = multiColumn
      .deleteById("B1")
      .deleteById("B2");
    const moved = emptyColumnMultiColumn.moveAcrossColumns(
      columnIds[0],
      "A1",
      columnIds[1],
      undefined,
    );
    expect(moved.topLevelIds).toEqual([
      ["A2", "A3"],
      ["A1"],
      ["C1", "C2", "C3", "C4"],
    ]);
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
