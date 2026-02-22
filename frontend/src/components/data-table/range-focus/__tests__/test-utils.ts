/* Copyright 2026 Marimo. All rights reserved. */

import type { Cell, Column, Row, Table } from "@tanstack/react-table";
import { vi } from "vitest";
import type { SelectedCell } from "../atoms";

export function createMockCell(
  id: string,
  value: unknown,
): Cell<unknown, unknown> {
  return {
    id,
    getValue: () => value,
    column: {} as Column<unknown>,
    row: {} as Row<unknown>,
    getContext: vi.fn(),
    renderValue: vi.fn(),
  } as unknown as Cell<unknown, unknown>;
}

export function createMockColumn(id: string): Column<unknown> {
  return {
    id: id,
    getIndex: () => Number.parseInt(id, 10),
  } as unknown as Column<unknown>;
}

export function createMockRow(
  id: string,
  cells: Cell<unknown, unknown>[],
): Row<unknown> {
  return {
    id,
    index: Number.parseInt(id, 10),
    getAllCells: () => cells,
    original: {},
    depth: 0,
    subRows: [],
    getVisibleCells: vi.fn(),
    getValue: vi.fn(),
    getUniqueValues: vi.fn(),
    renderValue: vi.fn(),
  } as unknown as Row<unknown>;
}

export function createMockTable(
  rows: Row<unknown>[],
  columns: Column<unknown>[],
): Table<unknown> {
  return {
    getRow: (id: string) => rows.find((row) => row.id === id),
    getRowModel: () => ({ rows }),
    getColumn: (columnId: string) => columns.find((col) => col.id === columnId),
    getAllColumns: () => columns,
  } as unknown as Table<unknown>;
}

export function createSelectedCell(
  rowId: string,
  columnId: string,
): SelectedCell {
  return {
    rowId,
    columnId,
    cellId: `${rowId}_${columnId}`,
  };
}
