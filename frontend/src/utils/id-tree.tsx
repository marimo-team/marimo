/* Copyright 2026 Marimo. All rights reserved. */

import { Memoize } from "typescript-memoize";
import { SETUP_CELL_ID } from "@/core/cells/ids";
import { arrayDelete, arrayInsert } from "./arrays";
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
  public value: T;

  public constructor(value: T) {
    this.value = value;
  }

  public toString(): string {
    return String(this.value);
  }

  public equals(other: TreeNode<T>): boolean {
    return this.value === other.value;
  }
}

let uniqueId = 0;

export class CollapsibleTree<T> {
  public readonly nodes: TreeNode<T>[];
  public readonly id: CellColumnId;

  private constructor(nodes: TreeNode<T>[], id: CellColumnId) {
    this.nodes = nodes;
    this.id = id;
  }

  /** A column of `ids`, keeping `id` when a column is rebuilt. */
  public static from<T>(ids: T[], id?: CellColumnId): CollapsibleTree<T> {
    return new CollapsibleTree(
      ids.map((id) => new TreeNode(id)),
      id ?? (`tree_${uniqueId++}` as CellColumnId),
    );
  }

  public withNodes(nodes: TreeNode<T>[]): CollapsibleTree<T> {
    return new CollapsibleTree(nodes, this.id);
  }

  @Memoize()
  public get topLevelIds(): T[] {
    return this.nodes.map((n) => n.value);
  }

  public get inOrderIds(): T[] {
    return this.topLevelIds;
  }

  @Memoize()
  public get idSet(): Set<T> {
    return new Set(this.inOrderIds);
  }

  public get length(): number {
    return this.nodes.length;
  }

  @Memoize()
  public get _nodeMap(): Map<T, TreeNode<T>> {
    const result = new Map<T, TreeNode<T>>();
    for (const node of this.nodes) {
      result.set(node.value, node);
    }
    return result;
  }

  /**
   * Get the index of the given node, or throw
   */
  public indexOfOrThrow(id: T): CellIndex {
    const index = this.nodes.findIndex((n) => n.value === id);
    if (index === -1) {
      throw new Error(
        `Node ${id} not found in tree. Valid ids: ${this.topLevelIds}`,
      );
    }
    return index as CellIndex;
  }

  /**
   * Get the top level nodes in the given range.
   * This does not include descendants.
   */
  public slice(start: number, end: number): T[] {
    return this.nodes.slice(start, end).map((n) => n.value);
  }

  /**
   * Get the node at the given index
   */
  public at(index: number): T | undefined {
    return this.nodes.at(index)?.value;
  }

  /**
   * Get the node at the given index
   */
  public atOrThrow(index: number): T {
    const node = this.nodes.at(index);
    if (node === undefined) {
      throw new Error(`Node at index ${index} not found in tree`);
    }
    return node.value;
  }

  /**
   * Get the first node, or throw
   */
  public first(): T {
    return this.atOrThrow(0);
  }

  /**
   * Get the last node, or throw
   */
  public last(): T {
    return this.atOrThrow(this.nodes.length - 1);
  }

  /**
   * Get the next node after the given node, does not wrap.
   */
  public after(id: T): T | undefined {
    const index = this.indexOfOrThrow(id);
    if (index === this.nodes.length - 1) {
      return undefined;
    }
    return this.at(index + 1);
  }

  /**
   * Get the previous node before the given node, does not wrap.
   */
  public before(id: T): T | undefined {
    const index = this.indexOfOrThrow(id);
    if (index === 0) {
      return undefined;
    }
    return this.at(index - 1);
  }

  /**
   * Insert a node at the given index
   */
  public insert(id: T, index: number): CollapsibleTree<T> {
    return this.withNodes(arrayInsert(this.nodes, index, new TreeNode(id)));
  }

  /**
   * Insert a node at the end
   */
  public insertAtEnd(id: T): CollapsibleTree<T> {
    return this.insert(id, this.nodes.length);
  }

  /**
   * Insert a node at the start
   */
  public insertAtStart(id: T): CollapsibleTree<T> {
    return this.insert(id, 0);
  }

  public deleteAtIndex(idx: number): CollapsibleTree<T> {
    this.atOrThrow(idx);
    return this.withNodes(arrayDelete(this.nodes, idx));
  }

  public delete(id: T): CollapsibleTree<T> {
    const index = this.indexOfOrThrow(id);
    return this.deleteAtIndex(index);
  }

  public equals(other: CollapsibleTree<T>): boolean {
    return (
      this.nodes.length === other.nodes.length &&
      this.nodes.every((n, i) => n.value === other.nodes[i].value)
    );
  }

  public toString(): string {
    return this.nodes.map((node) => `${node.toString()}\n`).join("");
  }
}

export class MultiColumn<T> {
  private readonly columns: readonly CollapsibleTree<T>[];

  public constructor(columns: readonly CollapsibleTree<T>[]) {
    this.columns = columns;

    // Ensure there is always at least one column
    if (columns.length === 0) {
      this.columns = [CollapsibleTree.from([])];
    }
  }

  public static from<T>(idsList: T[][]): MultiColumn<T> {
    return new MultiColumn(idsList.map((ids) => CollapsibleTree.from(ids)));
  }

  /**
   * Create a new MultiColumn from idsList,
   * attempting to preserve structure from previous MultiColumn if possible.
   */
  public static fromWithPreviousShape<T>(
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
      CollapsibleTree.from(ids, previousColumns[idx].id),
    );

    return new MultiColumn(newColumns);
  }

  @Memoize()
  public isEmpty(): boolean {
    if (this.columns.length === 0) {
      return true;
    }
    return this.columns.every((c) => c.nodes.length === 0);
  }

  public static fromIdsAndColumns<T>(
    idAndColumns: [T, number | undefined | null][],
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
  public get topLevelIds(): T[][] {
    return this.columns.map((c) => c.topLevelIds);
  }

  public get iterateTopLevelIds(): Iterable<T> {
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
  public get inOrderIds(): T[] {
    return this.columns.flatMap((c) => c.inOrderIds);
  }

  public get colLength(): number {
    return this.columns.length;
  }

  @Memoize()
  public get idLength(): number {
    return this.columns.reduce((acc, c) => acc + c.nodes.length, 0);
  }

  @Memoize()
  public get _columnMap(): Map<CellColumnId, CollapsibleTree<T>> {
    return new Map(this.columns.map((c) => [c.id, c]));
  }

  public at(idx: number): CollapsibleTree<T> | undefined {
    return this.columns[idx];
  }

  public get(columnId: CellColumnId): CollapsibleTree<T> | undefined {
    return this._columnMap.get(columnId);
  }

  public atOrThrow(idx: number): CollapsibleTree<T> {
    const column = this.columns[idx];
    if (!column) {
      throw new Error(`Column ${idx} not found`);
    }
    return column;
  }

  public hasOnlyOneColumn(): boolean {
    return this.columns.length === 1;
  }

  public getColumns(): readonly CollapsibleTree<T>[] {
    return this.columns;
  }

  public hasOnlyOneId(): boolean {
    return this.idLength === 1;
  }

  @Memoize()
  public getColumnIds(): CellColumnId[] {
    return this.columns.map((c) => c.id);
  }

  public indexOf(column: CollapsibleTree<T>): number {
    return this.columns.indexOf(column);
  }

  public indexOfOrThrow(id: CellColumnId): number {
    const index = this.columns.findIndex((c) => c.id === id);
    if (index === -1) {
      throw new Error(
        `Column ${id} not found. Possible values: ${this.getColumnIds().join(", ")}`,
      );
    }
    return index;
  }

  public findWithId(id: T): CollapsibleTree<T> {
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
  public transformWithCellId(
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

  public setupCellExists(): boolean {
    return this.columns.some((c) => c.topLevelIds.includes(SETUP_CELL_ID as T));
  }

  public insertId(id: T, col: CellColumnId, index: CellIndex): MultiColumn<T> {
    return this.transform(col, (c) => c.insert(id, index));
  }

  /**
   * Transform the column with the given column id
   */
  public transform(
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
  public transformAll(
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

export const visibleForTesting = {
  reset: () => {
    uniqueId = 0;
  },
};
