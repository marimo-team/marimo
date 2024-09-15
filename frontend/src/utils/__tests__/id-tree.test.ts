/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { TreeNode, CollapsibleTree } from "../id-tree";
import { beforeEach } from "vitest";

let tree: CollapsibleTree<string>;

describe("CollapsibleTree", () => {
  beforeEach(() => {
    const nodes = [
      new TreeNode("one", false, []),
      new TreeNode("two", false, []),
      new TreeNode("three", false, []),
      new TreeNode("four", false, []),
    ];
    tree = new CollapsibleTree(nodes);
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
    tree = tree.delete(1);
    expect(tree.toString()).toMatchInlineSnapshot(`
      "one
      three (collapsed)
        four
      "
    `);
  });

  it("fails to delete nodes", () => {
    expect(() => tree.delete(5)).toThrowErrorMatchingInlineSnapshot(
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
});
