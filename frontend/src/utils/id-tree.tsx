/* Copyright 2024 Marimo. All rights reserved. */

import { arrayMove } from "@dnd-kit/sortable";
import { arrayDelete, arrayInsert, arrayInsertMany } from "./arrays";
import { Memoize } from "typescript-memoize";
import { Logger } from "./Logger";

/**
 * Tree data structure for handling ids with nested children
 */
export class TreeNode<T> {
  constructor(
    public value: T,
    public isCollapsed: boolean,
    public children: Array<TreeNode<T>>,
  ) {}

  /**
   * Recursively count the number of nodes in the tree
   */
  getChildCount(): number {
    return this.children.reduce(
      (acc, child) => acc + 1 + child.getChildCount(),
      0,
    );
  }

  get inOrderIds(): T[] {
    return this.children.flatMap((c) => [c.value, ...c.inOrderIds]);
  }

  toString(): string {
    if (this.isCollapsed) {
      return `${this.value} (collapsed)`;
    }
    return String(this.value);
  }
}

export class CollapsibleTree<T> {
  constructor(public nodes: Array<TreeNode<T>>) {}

  static from<T>(ids: T[]): CollapsibleTree<T> {
    return new CollapsibleTree(ids.map((id) => new TreeNode(id, false, [])));
  }

  get topLevelIds(): T[] {
    return this.nodes.map((n) => n.value);
  }

  @Memoize()
  get inOrderIds(): T[] {
    return this.nodes.flatMap((n) => [n.value, ...n.inOrderIds]);
  }

  get length(): number {
    return this.nodes.length;
  }

  isCollapsed(id: T): boolean {
    const node = this.nodes.find((n) => n.value === id);
    if (!node) {
      Logger.warn(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
      );
      return false;
    }
    return node.isCollapsed;
  }

  indexOfOrThrow(id: T): number {
    const index = this.nodes.findIndex((n) => n.value === id);
    if (index === -1) {
      throw new Error(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
      );
    }
    return index;
  }

  moveToFront(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return new CollapsibleTree(arrayMove(this.nodes, index, 0));
  }

  moveToBack(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return new CollapsibleTree(
      arrayMove(this.nodes, index, this.nodes.length - 1),
    );
  }

  /**
   * Collapse everything past the given node @param id
   * until @param until or the end of the tree
   */
  collapse(id: T, until: T | undefined): CollapsibleTree<T> {
    const nodeIndex = this.nodes.findIndex((n) => n.value === id);
    if (nodeIndex === -1) {
      throw new Error(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
      );
    }

    const untilIndex =
      until === undefined
        ? this.nodes.length
        : this.nodes.findIndex((n) => n.value === until);

    if (untilIndex === -1) {
      throw new Error(`Node ${until} not found in tree`);
    }
    if (untilIndex < nodeIndex) {
      throw new Error(`Node ${until} is before node ${id}`);
    }

    const node = this.nodes[nodeIndex];
    if (node.isCollapsed) {
      throw new Error(`Node ${id} is already collapsed`);
    }

    // Fold the next nodes into the current node
    node.children = this.nodes.splice(nodeIndex + 1, untilIndex - nodeIndex);
    node.isCollapsed = true;

    return new CollapsibleTree(this.nodes);
  }

  /**
   * Expand a node and all of its children
   */
  expand(id: T): CollapsibleTree<T> {
    const nodeIndex = this.nodes.findIndex((n) => n.value === id);
    if (nodeIndex === -1) {
      throw new Error(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
      );
    }

    const node = this.nodes[nodeIndex];
    if (!node.isCollapsed) {
      throw new Error(`Node ${id} is already expanded`);
    }

    node.isCollapsed = false;
    this.nodes = arrayInsertMany(this.nodes, nodeIndex + 1, node.children);
    node.children = [];

    return new CollapsibleTree(this.nodes);
  }

  /**
   * Move a node from one index to another
   */
  move(fromIdx: number, toIdx: number): CollapsibleTree<T> {
    this.nodes = arrayMove(this.nodes, fromIdx, toIdx);
    return new CollapsibleTree(this.nodes);
  }

  at(index: number): T | undefined {
    return this.nodes.at(index)?.value;
  }

  atOrThrow(index: number): T {
    const node = this.nodes.at(index);
    if (node === undefined) {
      throw new Error(`Node at index ${index} not found in tree`);
    }
    return node.value;
  }

  first(): T {
    return this.atOrThrow(0);
  }

  last(): T {
    return this.atOrThrow(this.nodes.length - 1);
  }

  /**
   * Insert a node at the given index
   */
  insert(id: T, index: number): CollapsibleTree<T> {
    this.nodes = arrayInsert(this.nodes, index, new TreeNode(id, false, []));
    return new CollapsibleTree(this.nodes);
  }

  insertAtEnd(id: T): CollapsibleTree<T> {
    return this.insert(id, this.nodes.length);
  }

  insertAtStart(id: T): CollapsibleTree<T> {
    return this.insert(id, 0);
  }

  /**
   * Delete a node, expand if it was collapsed
   */
  delete(idx: number): CollapsibleTree<T> {
    const id = this.atOrThrow(idx);
    try {
      this.expand(id);
    } catch {
      // Don't care if its not expanded
    }
    return new CollapsibleTree(arrayDelete(this.nodes, idx));
  }

  /**
   * Get the number of nodes in the tree, not-including the given node
   */
  getCount(id: T): number {
    return this.nodes.find((n) => n.value === id)?.getChildCount() ?? 0;
  }

  /**
   * Find and expand the node and all of its children
   */
  findAndExpandDeep(id: T): CollapsibleTree<T> {
    const found = this.find(id);
    for (const node of found) {
      try {
        this.expand(node);
      } catch {
        // Don't care if its the last node and its not expanded
      }
    }

    return new CollapsibleTree(this.nodes);
  }

  /**
   * Find a node, returning the path to it
   * With the last element being the node itself
   */
  find(id: T): T[] {
    // We need to recursively find the node
    function findNode(nodes: Array<TreeNode<T>>, path: T[]): T[] {
      for (const node of nodes) {
        if (node.value === id) {
          return [...path, id];
        }
        const result = findNode(node.children, [...path, node.value]);
        if (result.length > 0) {
          return result;
        }
      }
      return [];
    }

    return findNode(this.nodes, []);
  }

  toString(): string {
    let depth = 0;
    let result = "";
    const asString = (nodes: Array<TreeNode<T>>) => {
      for (const node of nodes) {
        result += `${" ".repeat(depth * 2)}${node.toString()}\n`;
        depth += 1;
        asString(node.children);
        depth -= 1;
      }
    };
    asString(this.nodes);
    return result;
  }
}
