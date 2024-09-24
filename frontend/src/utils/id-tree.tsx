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
    public children: Array<TreeNode<T>>
  ) {}

  /**
   * Recursively count the number of nodes in the tree
   */
  geDescendantCount(): number {
    return this.children.reduce(
      (acc, child) => acc + 1 + child.geDescendantCount(),
      0
    );
  }

  getDescendants(): T[] {
    return this.children.flatMap((c) => [c.value, ...c.getDescendants()]);
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

  equals(other: TreeNode<T>): boolean {
    return this.value === other.value;
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

  /**
   * Get the descendants of the given node
   *
   * Only works for the top-level nodes
   */
  getDescendants(id: T): T[] {
    const node = this.nodes.find((n) => n.value === id);
    if (!node) {
      Logger.warn(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`
      );
      return [];
    }
    return node.getDescendants();
  }

  /**
   * Check if the given node is collapsed
   *
   * Only works for the top-level nodes
   */
  isCollapsed(id: T): boolean {
    const node = this.nodes.find((n) => n.value === id);
    if (!node) {
      Logger.warn(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`
      );
      return false;
    }
    return node.isCollapsed;
  }

  /**
   * Get the index of the given node, or throw
   */
  indexOfOrThrow(id: T): number {
    const index = this.nodes.findIndex((n) => n.value === id);
    if (index === -1) {
      throw new Error(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`
      );
    }
    return index;
  }

  /**
   * Move the given node to the front
   */
  moveToFront(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return new CollapsibleTree(arrayMove(this.nodes, index, 0));
  }

  /**
   * Move the given node to the back
   */
  moveToBack(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return new CollapsibleTree(
      arrayMove(this.nodes, index, this.nodes.length - 1)
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
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`
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

    const nodes = [...this.nodes];
    const node = nodes[nodeIndex];
    if (node.isCollapsed) {
      throw new Error(`Node ${id} is already collapsed`);
    }

    // Fold the next nodes into the current node
    const children = nodes.splice(nodeIndex + 1, untilIndex - nodeIndex);
    nodes[nodeIndex] = new TreeNode(node.value, true, children);

    return new CollapsibleTree(nodes);
  }

  /**
   * Expand a node and all of its children
   */
  expand(id: T): CollapsibleTree<T> {
    const nodeIndex = this.nodes.findIndex((n) => n.value === id);
    if (nodeIndex === -1) {
      throw new Error(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`
      );
    }

    let nodes = [...this.nodes];
    const node = nodes[nodeIndex];
    if (!node.isCollapsed) {
      throw new Error(`Node ${id} is already expanded`);
    }

    nodes[nodeIndex] = new TreeNode(node.value, false, []);
    nodes = arrayInsertMany(nodes, nodeIndex + 1, node.children);

    return new CollapsibleTree(nodes);
  }

  /**
   * Move a node from one index to another
   */
  move(fromIdx: number, toIdx: number): CollapsibleTree<T> {
    this.nodes = arrayMove(this.nodes, fromIdx, toIdx);
    return new CollapsibleTree(this.nodes);
  }

  /**
   * Get the node at the given index
   */
  at(index: number): T | undefined {
    return this.nodes.at(index)?.value;
  }

  /**
   * Get the node at the given index
   */
  atOrThrow(index: number): T {
    const node = this.nodes.at(index);
    if (node === undefined) {
      throw new Error(`Node at index ${index} not found in tree`);
    }
    return node.value;
  }

  /**
   * Get the first node, or throw
   */
  first(): T {
    return this.atOrThrow(0);
  }

  /**
   * Get the last node, or throw
   */
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

  /**
   * Insert a node at the end
   */
  insertAtEnd(id: T): CollapsibleTree<T> {
    return this.insert(id, this.nodes.length);
  }

  /**
   * Insert a node at the start
   */
  insertAtStart(id: T): CollapsibleTree<T> {
    return this.insert(id, 0);
  }

  /**
   * Delete a node, expand if it was collapsed
   */
  delete(idx: number): CollapsibleTree<T> {
    const id = this.atOrThrow(idx);
    let tree = new CollapsibleTree(this.nodes);
    try {
      tree = tree.expand(id);
    } catch {
      // Don't care if its not expanded
    }
    return new CollapsibleTree(arrayDelete(tree.nodes, idx));
  }

  /**
   * Get the number of nodes in the tree, not-including the given node
   */
  getCount(id: T): number {
    return this.nodes.find((n) => n.value === id)?.geDescendantCount() ?? 0;
  }

  /**
   * Find and expand the node and all of its children
   */
  findAndExpandDeep(id: T): CollapsibleTree<T> {
    const found = this.find(id);
    if (found.length === 0) {
      return this;
    }
    let result = new CollapsibleTree<T>(this.nodes);
    for (const node of found) {
      try {
        result = result.expand(node);
      } catch {
        // Don't care if its the last node and its not expanded
      }
    }

    return result;
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

  equals(other: CollapsibleTree<T>): boolean {
    return (
      this.nodes.length === other.nodes.length &&
      this.nodes.every((n, i) => n.value === other.nodes[i].value)
    );
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

export class MultiColumn<T> {
  constructor(public columns: Array<CollapsibleTree<T>>) {}

  static from<T>(ids: T[][]): MultiColumn<T> {
    return new MultiColumn(ids.map((id) => CollapsibleTree.from(id)));
  }

  get topLevelIds(): T[][] {
    return this.columns.map((c) => c.topLevelIds);
  }

  get inOrderIds(): T[] {
    return this.columns.flatMap((c) => c.inOrderIds);
  }

  get colLength(): number {
    return this.columns.length;
  }

  addColumn(): MultiColumn<T> {
    return new MultiColumn([...this.columns, CollapsibleTree.from([])]);
  }

  insertBreakpoint(columnIndex: number, cellIndex: number): MultiColumn<T> {
    const column = this.columns[columnIndex];
    const newColumn = new CollapsibleTree(column.nodes.splice(cellIndex));
    const columns = [...this.columns];
    columns[columnIndex] = new CollapsibleTree(column.nodes);
    columns.splice(columnIndex + 1, 0, newColumn);
    return new MultiColumn(columns);
  }

  moveWithinColumn(
    col: number,
    fromIdx: number,
    toIdx: number
  ): MultiColumn<T> {
    const columns = [...this.columns];
    const id = columns[col].atOrThrow(fromIdx);
    columns[col] = columns[col].delete(fromIdx).insert(id, toIdx);
    return new MultiColumn(columns);
  }

  moveAcrossColumns(
    fromCol: number,
    fromIdx: number,
    toCol: number,
    toIdx: number
  ): MultiColumn<T> {
    const columns = [...this.columns];
    const id = columns[fromCol].atOrThrow(fromIdx);
    columns[fromCol] = columns[fromCol].delete(fromIdx);
    columns[toCol] = columns[toCol].insert(id, toIdx);
    return new MultiColumn(columns);
  }

  moveColumn(fromCol: number, toCol: number): MultiColumn<T> {
    const id = this.columns[fromCol].first();
    const newFromTree = this.columns[fromCol].delete(0);
    const newToTree = newFromTree.insertAtStart(id);
    const columns = [...this.columns];
    columns[fromCol] = newFromTree;
    columns[toCol] = newToTree;
    return new MultiColumn(columns);
  }

  getColumnWithId(id: T): [CollapsibleTree<T>, number] {
    const index = this.columns.findIndex((c) => c.topLevelIds.includes(id));
    const column = this.columns[index];
    if (!column) {
      throw new Error(
        `Column with id ${id} not found in tree. 
        Valid ids: ${this.topLevelIds}`
      );
    }
    return [column, index];
  }

  insertId(col: number, id: T, index: number): MultiColumn<T> {
    const column = this.columns[col];
    const columns = [...this.columns];
    columns[col] = column.insert(id, index);
    return new MultiColumn([...columns]);
  }

  deleteId(id: T): MultiColumn<T> {
    const [column, columnIndex] = this.getColumnWithId(id);
    const cellIndex = column.indexOfOrThrow(id);
    const newColumn = column.delete(cellIndex);
    const columns = [...this.columns];
    columns[columnIndex] = newColumn;
    return new MultiColumn(columns);
  }
}
