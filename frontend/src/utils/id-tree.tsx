/* Copyright 2024 Marimo. All rights reserved. */

import { arrayDelete, arrayInsert, arrayInsertMany, arrayMove } from "./arrays";
import { Memoize } from "typescript-memoize";
import { Logger } from "./Logger";
import { reorderColumnSizes } from "@/components/editor/columns/storage";

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
  @Memoize()
  geDescendantCount(): number {
    let count = 0;
    const stack = [...this.children];

    while (stack.length > 0) {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      const node = stack.pop()!;
      count++;

      // Add children to stack
      for (let i = node.children.length - 1; i >= 0; i--) {
        stack.push(node.children[i]);
      }
    }

    return count;
  }

  @Memoize()
  getDescendants(): T[] {
    const result: T[] = [];
    const stack = [...this.children];

    while (stack.length > 0) {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      const node = stack.pop()!;
      result.push(node.value);

      // Add children to stack in reverse order to maintain correct traversal order
      for (let i = node.children.length - 1; i >= 0; i--) {
        stack.push(node.children[i]);
      }
    }

    return result;
  }

  @Memoize()
  get inOrderIds(): T[] {
    const result: T[] = [];
    const queue = [...this.children];

    while (queue.length > 0) {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      const node = queue.shift()!;
      result.push(node.value);

      // Add children to queue to maintain breadth-first traversal
      queue.push(...node.children);
    }

    return result;
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

  /**
   * Create a new tree from ids, preserving structure from previous tree if possible
   */
  static fromWithPreviousShape<T>(
    ids: T[],
    previousTree?: CollapsibleTree<T>,
  ): CollapsibleTree<T> {
    if (!previousTree) {
      return CollapsibleTree.from(ids);
    }

    // Reuse the previous tree's id if possible
    const id = previousTree.id;

    // Create new tree with nothing collapsed
    let newTree = new CollapsibleTree(
      ids.map((id) => new TreeNode(id, false, [])),
      id,
    );

    // Collapse nodes that were collapsed in the previous tree
    for (const id of ids) {
      if (previousTree.isCollapsed(id)) {
        const children = previousTree._nodeMap.get(id)?.children ?? [];
        // Find the first child that is also in the new tree, going backwards
        for (let i = children.length - 1; i >= 0; i--) {
          const child = children[i];
          if (newTree._nodeMap.has(child.value)) {
            newTree = newTree.collapse(id, child.value);
            break;
          }
        }
      }
    }

    return newTree;
  }

  withNodes(nodes: Array<TreeNode<T>>): CollapsibleTree<T> {
    return new CollapsibleTree(nodes, this.id);
  }

  @Memoize()
  get topLevelIds(): T[] {
    return this.nodes.map((n) => n.value);
  }

  @Memoize()
  get inOrderIds(): T[] {
    return this.nodes.flatMap((n) => [n.value, ...n.inOrderIds]);
  }

  @Memoize()
  get idSet(): Set<T> {
    return new Set(this.inOrderIds);
  }

  get length(): number {
    return this.nodes.length;
  }

  @Memoize()
  get _nodeMap(): Map<T, TreeNode<T>> {
    const result = new Map<T, TreeNode<T>>();
    for (const node of this.nodes) {
      result.set(node.value, node);
    }
    return result;
  }

  /**
   * Get the descendants of the given node
   *
   * Only works for the top-level nodes
   */
  getDescendants(id: T): T[] {
    const node = this._nodeMap.get(id);
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
    const node = this._nodeMap.get(id);
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
    return this._nodeMap.get(id)?.geDescendantCount() ?? 0;
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

  /**
   * Create a new MultiColumn from idsList,
   * attempting to preserve structure from previous MultiColumn if possible.
   */
  static fromWithPreviousShape<T>(
    idsList: T[],
    previousShape: MultiColumn<T>,
  ): MultiColumn<T> {
    if (!previousShape) {
      return MultiColumn.from([idsList]);
    }

    // Get previous columns for reference
    const previousColumns = previousShape.getColumns();

    // Split the ids into their respective columns
    const splitIds: T[][] = Array.from(
      { length: previousColumns.length },
      () => [],
    );
    let lastUsedColumnIdx = 0;
    for (const id of idsList) {
      const column = previousColumns.findIndex((c) => c.idSet.has(id));
      if (column === -1) {
        // No column found, use the last used column
        splitIds[lastUsedColumnIdx].push(id);
      } else {
        lastUsedColumnIdx = column;
        splitIds[column].push(id);
      }
    }

    const newColumns = splitIds.map((ids, idx) =>
      CollapsibleTree.fromWithPreviousShape(ids, previousColumns[idx]),
    );

    return new MultiColumn(newColumns);
  }

  @Memoize()
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
      ...idAndColumns.map(([, column]) => (column ?? 0) + 1),
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

  @Memoize()
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

  @Memoize()
  get inOrderIds(): T[] {
    return this.columns.flatMap((c) => c.inOrderIds);
  }

  get colLength(): number {
    return this.columns.length;
  }

  @Memoize()
  get idLength(): number {
    return this.columns.reduce((acc, c) => acc + c.nodes.length, 0);
  }

  @Memoize()
  get _columnMap(): Map<CellColumnId, CollapsibleTree<T>> {
    return new Map(this.columns.map((c) => [c.id, c]));
  }

  at(idx: number): CollapsibleTree<T> | undefined {
    return this.columns[idx];
  }

  get(columnId: CellColumnId): CollapsibleTree<T> | undefined {
    return this._columnMap.get(columnId);
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

  @Memoize()
  getColumnIds(): CellColumnId[] {
    return this.columns.map((c) => c.id);
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
    // Find indices once to avoid repeated lookups
    const fromColumnIndex = this.indexOfOrThrow(fromCol);
    const toColumnIndex = this.indexOfOrThrow(toCol);

    // Only copy the columns we're modifying
    const newColumns = [...this.columns];
    const fromColumn = newColumns[fromColumnIndex];

    // Find the node once
    const nodeIndex = fromColumn.nodes.findIndex((n) => n.value === fromId);
    if (nodeIndex === -1) {
      throw new Error(`Node ${fromId} not found in column ${fromCol}`);
    }

    const node = fromColumn.nodes[nodeIndex];

    // Create new columns with the changes
    newColumns[fromColumnIndex] = fromColumn.withNodes(
      fromColumn.nodes.filter((_, i) => i !== nodeIndex),
    );

    const toColumn = newColumns[toColumnIndex];
    if (toId) {
      const toIndex = toColumn.indexOfOrThrow(toId);
      newColumns[toColumnIndex] = toColumn.withNodes(
        arrayInsert(toColumn.nodes, toIndex, node),
      );
    } else {
      newColumns[toColumnIndex] = toColumn.withNodes([node, ...toColumn.nodes]);
    }

    return new MultiColumn(newColumns);
  }

  indexOfOrThrow(id: CellColumnId): number {
    const index = this.columns.findIndex((c) => c.id === id);
    if (index === -1) {
      throw new Error(
        `Column ${id} not found. Possible values: ${this.getColumnIds().join(", ")}`,
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
    const toIdx =
      toCol === "_left_"
        ? fromIdx - 1
        : toCol === "_right_"
          ? fromIdx + 1
          : this.indexOfOrThrow(toCol);

    reorderColumnSizes(fromIdx, toIdx);
    return new MultiColumn(arrayMove([...this.columns], fromIdx, toIdx));
  }

  moveToNewColumn(cellId: T): MultiColumn<T> {
    const fromColumn = this.findWithId(cellId);

    // Create new columns array with the cell removed from its original column
    const columns = this.columns.map((c) => {
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
    // Use columnMap for faster lookup
    const column = this._columnMap.get(columnId);
    if (!column) {
      Logger.warn(`Column ${columnId} not found`);
      return this;
    }

    const newColumn = fn(column);
    if (column === newColumn) {
      return this;
    }

    const newColumns = this.columns.map((c) => {
      if (c.id === columnId) {
        return newColumn;
      }
      return c;
    });

    return new MultiColumn(newColumns);
  }

  /**
   * Apply a transformation function to all columns
   * @param fn The function to transform each column
   * @returns A new MultiColumn if any changes were made, otherwise this
   */
  transformAll(
    fn: (tree: CollapsibleTree<T>) => CollapsibleTree<T>,
  ): MultiColumn<T> {
    let didChange = false;
    
    // Apply the transformation to all columns
    const newColumns = this.columns.map((column) => {
      const newColumn = fn(column);
      if (!column.equals(newColumn)) {
        didChange = true;
      }
      return newColumn;
    });
    
    // Avoid unnecessary re-renders if nothing changed
    if (!didChange) {
      return this;
    }
    
    return new MultiColumn(newColumns);
  }
}
