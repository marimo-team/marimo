/* Copyright 2024 Marimo. All rights reserved. */

import { arrayDelete, arrayInsert, arrayInsertMany, arrayMove } from "./arrays";
import { Memoize } from "typescript-memoize";
import { Logger } from "./Logger";

/**
 * Branded number to help with type safety
 */
export type CellColumnIndex = number & { __brand: "CellColumnIndex" };

/**
 * Branded string to help with type safety
 */
export type CellColumnId = string & { __brand: "CellColumnId" };
/**
 * Weakly-branded number, since making `__brand` required causes type errors
 */
export type CellIndex = number & { __brand?: "CellIndex" };

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
  geDescendantCount(): number {
    return this.children.reduce(
      (acc, child) => acc + 1 + child.geDescendantCount(),
      0,
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

let uniqueId = 0;

export class CollapsibleTree<T> {
  private constructor(
    public readonly nodes: Array<TreeNode<T>>,
    public readonly id: CellColumnId,
  ) {}

  static from<T>(ids: T[]): CollapsibleTree<T> {
    const id = `tree_${uniqueId++}` as CellColumnId;
    return new CollapsibleTree(
      ids.map((id) => new TreeNode(id, false, [])),
      id,
    );
  }

  withNodes(nodes: Array<TreeNode<T>>): CollapsibleTree<T> {
    return new CollapsibleTree(nodes, this.id);
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
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
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
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
      );
      return false;
    }
    return node.isCollapsed;
  }

  /**
   * Get the index of the given node, or throw
   */
  indexOfOrThrow(id: T): CellIndex {
    const index = this.nodes.findIndex((n) => n.value === id);
    if (index === -1) {
      throw new Error(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
      );
    }
    return index as CellIndex;
  }

  /**
   * Move the given node to the front
   */
  moveToFront(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return this.withNodes(arrayMove(this.nodes, index, 0));
  }

  /**
   * Move the given node to the back
   */
  moveToBack(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return this.withNodes(arrayMove(this.nodes, index, this.nodes.length - 1));
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

    const nodes = [...this.nodes];
    const node = nodes[nodeIndex];
    if (node.isCollapsed) {
      throw new Error(`Node ${id} is already collapsed`);
    }

    // Fold the next nodes into the current node
    const children = nodes.splice(nodeIndex + 1, untilIndex - nodeIndex);
    nodes[nodeIndex] = new TreeNode(node.value, true, children);

    return this.withNodes(nodes);
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

    let nodes = [...this.nodes];
    const node = nodes[nodeIndex];
    if (!node.isCollapsed) {
      throw new Error(`Node ${id} is already expanded`);
    }

    nodes[nodeIndex] = new TreeNode(node.value, false, []);
    nodes = arrayInsertMany(nodes, nodeIndex + 1, node.children);

    return this.withNodes(nodes);
  }

  /**
   * Move a node from one index to another
   */
  move(fromIdx: number, toIdx: number): CollapsibleTree<T> {
    return this.withNodes(arrayMove(this.nodes, fromIdx, toIdx));
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
    return this.withNodes(
      arrayInsert(this.nodes, index, new TreeNode(id, false, [])),
    );
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
  deleteAtIndex(idx: number): CollapsibleTree<T> {
    const id = this.atOrThrow(idx);
    let tree = this.withNodes(this.nodes);
    try {
      tree = tree.expand(id);
    } catch {
      // Don't care if its not expanded
    }
    return this.withNodes(arrayDelete(tree.nodes, idx));
  }

  delete(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return this.deleteAtIndex(index);
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
    let result = this.withNodes(this.nodes);
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

  /**
   * Split the tree into two trees
   * @param id the id of the node to split at
   * @returns a tuple of the left and right trees
   */
  split(id: T): [CollapsibleTree<T>, CollapsibleTree<T> | undefined] {
    const index = this.nodes.findIndex((n) => n.value === id);
    if (index === -1) {
      throw new Error(`Node ${id} not found in tree`);
    }
    const leftNodes = this.nodes.slice(0, index);
    const rightNodes = this.nodes.slice(index);
    if (leftNodes.length === 0) {
      return [CollapsibleTree.from<T>([]), this.withNodes(rightNodes)];
    }
    const left = this.withNodes(leftNodes);
    const right = CollapsibleTree.from<T>([]).withNodes(rightNodes);
    return [left, right];
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
  constructor(private readonly columns: ReadonlyArray<CollapsibleTree<T>>) {
    // Ensure there is always at least one column
    if (columns.length === 0) {
      this.columns = [CollapsibleTree.from([])];
    }
  }

  static from<T>(idsList: T[][]): MultiColumn<T> {
    return new MultiColumn(idsList.map((ids) => CollapsibleTree.from(ids)));
  }

  isEmpty(): boolean {
    if (this.columns.length === 0) {
      return true;
    }
    return this.columns.every((c) => c.nodes.length === 0);
  }

  static fromIdsAndColumns<T>(
    idAndColumns: Array<[T, number | undefined | null]>,
  ): MultiColumn<T> {
    // If column is undefined, use the previous column
    // Ensure there is always at least one column
    const numColumns = Math.max(
      1,
      ...idAndColumns.map(([_, column]) => (column ?? 0) + 1),
    );
    const idsList: T[][] = Array.from({ length: numColumns }, () => []);

    let prevColumn = 0;
    for (const [id, column] of idAndColumns) {
      // Avoid negative column indices
      if (column === undefined || column === null || column < 0) {
        idsList[prevColumn].push(id);
      } else {
        idsList[column].push(id);
        prevColumn = column;
      }
    }

    return MultiColumn.from(idsList);
  }

  get topLevelIds(): T[][] {
    return this.columns.map((c) => c.topLevelIds);
  }

  get iterateTopLevelIds(): Iterable<T> {
    const columns = this.columns;

    function* iter() {
      for (const column of columns) {
        for (const id of column.topLevelIds) {
          yield id;
        }
      }
    }

    return iter();
  }

  get inOrderIds(): T[] {
    return this.columns.flatMap((c) => c.inOrderIds);
  }

  get colLength(): number {
    return this.columns.length;
  }

  get idLength(): number {
    return this.columns.reduce((acc, c) => acc + c.nodes.length, 0);
  }

  at(idx: number): CollapsibleTree<T> | undefined {
    return this.columns[idx];
  }

  get(columnId: CellColumnId): CollapsibleTree<T> | undefined {
    return this.columns.find((c) => c.id === columnId);
  }

  atOrThrow(idx: number): CollapsibleTree<T> {
    const column = this.columns[idx];
    if (!column) {
      throw new Error(`Column ${idx} not found`);
    }
    return column;
  }

  hasOnlyOneColumn(): boolean {
    return this.columns.length === 1;
  }

  getColumns(): ReadonlyArray<CollapsibleTree<T>> {
    return this.columns;
  }

  hasOnlyOneId(): boolean {
    return this.idLength === 1;
  }

  indexOf(column: CollapsibleTree<T>): number {
    return this.columns.indexOf(column);
  }

  addColumn(columnId: CellColumnId, initialIds: T[] = []): MultiColumn<T> {
    return new MultiColumn(
      this.columns.flatMap((c) => {
        if (c.id === columnId) {
          return [c, CollapsibleTree.from(initialIds)];
        }
        return [c];
      }),
    );
  }

  insertBreakpoint(cellId: T): MultiColumn<T> {
    const column = this.findWithId(cellId);
    const [left, right] = column.split(cellId);
    const newColumns = this.columns.flatMap((c) => {
      if (c === column) {
        return [left, right].filter(Boolean);
      }
      return [c];
    });
    return new MultiColumn(newColumns);
  }

  delete(columnId: CellColumnId): MultiColumn<T> {
    // Move cells to preceding column
    // If its the first column, move the cells to the next column

    // Noop if there is only one column
    if (this.columns.length <= 1) {
      return this;
    }

    const columnIndex = this.indexOfOrThrow(columnId);
    const targetColumnIndex = columnIndex === 0 ? 1 : columnIndex - 1;

    const columns = [...this.columns];
    const column = columns[columnIndex];
    columns[targetColumnIndex] = column.withNodes([
      ...columns[targetColumnIndex].nodes,
      ...column.nodes,
    ]);
    columns.splice(columnIndex, 1);
    return new MultiColumn(columns);
  }

  mergeAllColumns(): MultiColumn<T> {
    if (this.columns.length <= 1) {
      return this;
    }

    const nodes = this.columns.flatMap((c) => c.nodes);
    const firstColumn = this.columns[0];
    return new MultiColumn([firstColumn.withNodes(nodes)]);
  }

  moveWithinColumn(
    col: CellColumnId,
    fromIdx: CellIndex,
    toIdx: CellIndex,
  ): MultiColumn<T> {
    return this.transform(col, (c) => {
      return c.move(fromIdx, toIdx);
    });
  }

  moveAcrossColumns(
    fromCol: CellColumnId,
    fromId: T,
    toCol: CellColumnId,
    toId: T | undefined,
  ): MultiColumn<T> {
    const columns = [...this.columns];

    const fromColumnIndex = this.columns.findIndex((c) => c.id === fromCol);
    // Full node, not just the top level id
    const node = columns[fromColumnIndex].nodes.find((n) => n.value === fromId);
    if (!node) {
      throw new Error(`Node ${fromId} not found in column ${fromCol}`);
    }

    return new MultiColumn(
      columns.map((c, i) => {
        if (c.id === fromCol) {
          // We don't use delete since we want to remove the node and it's children
          return c.withNodes(c.nodes.filter((n) => n.value !== fromId));
        }
        if (c.id === toCol) {
          if (!toId) {
            return c.withNodes(arrayInsert(c.nodes, 0, node));
          }
          return c.withNodes(
            arrayInsert(c.nodes, c.indexOfOrThrow(toId), node),
          );
        }
        return c;
      }),
    );
  }

  indexOfOrThrow(id: CellColumnId): number {
    const index = this.columns.findIndex((c) => c.id === id);
    if (index === -1) {
      throw new Error(
        `Column ${id} not found. Possible values: ${this.columns
          .map((c) => c.id)
          .join(", ")}`,
      );
    }
    return index;
  }

  moveColumn(
    fromCol: CellColumnId,
    toCol: CellColumnId | "_left_" | "_right_",
  ): MultiColumn<T> {
    if (fromCol === toCol) {
      return this;
    }
    const fromIdx = this.indexOfOrThrow(fromCol);
    if (toCol === "_left_") {
      return new MultiColumn(
        arrayMove([...this.columns], fromIdx, fromIdx - 1),
      );
    }
    if (toCol === "_right_") {
      return new MultiColumn(
        arrayMove([...this.columns], fromIdx, fromIdx + 1),
      );
    }
    const toIdx = this.indexOfOrThrow(toCol);
    return new MultiColumn(arrayMove([...this.columns], fromIdx, toIdx));
  }

  moveToNewColumn(cellId: T): MultiColumn<T> {
    const fromColumn = this.findWithId(cellId);
    let columns = [...this.columns];
    // Delete from existing column
    columns = columns.map((c) => {
      if (c.id === fromColumn.id) {
        return c.delete(cellId);
      }
      return c;
    });

    // Insert into new column
    const newColumn = CollapsibleTree.from([cellId]);
    return new MultiColumn([...columns, newColumn]);
  }

  findWithId(id: T): CollapsibleTree<T> {
    const found = this.columns.find((c) => {
      return c.inOrderIds.includes(id);
    });
    if (!found) {
      Logger.log(
        `Possible values: ${this.columns.map((c) => c.inOrderIds).join(", ")}`,
      );
      throw new Error(`Cell ${id} not found in any column`);
    }
    return found;
  }

  /**
   * Transform the column containing the given cell id
   * @param id the id of the cell to transform
   * @param fn the function to transform the column
   * @returns new MultiColumn with the transformed column
   * If the column was not updated, we return the object.
   */
  transformWithCellId(
    id: T,
    fn: (tree: CollapsibleTree<T>) => CollapsibleTree<T>,
  ): MultiColumn<T> {
    let didChange = false;

    const columns = this.columns.map((c) => {
      if (c.inOrderIds.includes(id)) {
        const newColumn = fn(c);
        if (c !== newColumn) {
          didChange = true;
        }
        return newColumn;
      }
      return c;
    });

    // Avoid unnecessary re-renders
    if (!didChange) {
      return this;
    }

    return new MultiColumn(columns);
  }

  insertId(id: T, col: CellColumnId, index: CellIndex): MultiColumn<T> {
    return this.transform(col, (c) => c.insert(id, index));
  }

  deleteById(cellId: T): MultiColumn<T> {
    return this.transformWithCellId(cellId, (c) => c.delete(cellId));
  }

  compact(): MultiColumn<T> {
    // Don't compact if there's only one column
    if (this.columns.length === 1) {
      return this;
    }
    // If no need to compact, return the same tree
    // to avoid unnecessary re-renders
    const someEmpty = this.columns.some((c) => c.nodes.length === 0);
    if (!someEmpty) {
      return this;
    }

    return new MultiColumn(this.columns.filter((c) => c.nodes.length > 0));
  }

  /**
   * Transform the column with the given column id
   */
  transform(
    columnId: CellColumnId,
    fn: (tree: CollapsibleTree<T>) => CollapsibleTree<T>,
  ): MultiColumn<T> {
    return new MultiColumn(
      this.columns.map((c) => {
        if (c.id === columnId) {
          return fn(c);
        }
        return c;
      }),
    );
  }
}
