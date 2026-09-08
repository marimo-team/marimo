/* Copyright 2026 Marimo. All rights reserved. */

import {
  type ColumnDef,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  getShowOnlyVisibility,
  isShowingOnly,
  useColumnVisibility,
} from "../hooks/use-column-visibility";
import { INDEX_COLUMN_NAME, SELECT_COLUMN_ID } from "../types";

type Row = Record<string, unknown>;

const TEST_COLUMNS: ColumnDef<Row>[] = [
  { id: SELECT_COLUMN_ID, accessorKey: SELECT_COLUMN_ID, enableHiding: false },
  {
    id: INDEX_COLUMN_NAME,
    accessorKey: INDEX_COLUMN_NAME,
    enableHiding: false,
  },
  { id: "customer_name", accessorKey: "customer_name" },
  { id: "cust_age", accessorKey: "cust_age" },
  { id: "order_total", accessorKey: "order_total" },
];

function createTestTable({
  initiallyHidden = [],
  nonHideable = [],
}: {
  initiallyHidden?: string[];
  nonHideable?: string[];
} = {}) {
  const { result } = renderHook(() =>
    useReactTable<Row>({
      data: [],
      columns: TEST_COLUMNS.map((column) =>
        nonHideable.includes(column.id as string)
          ? { ...column, enableHiding: false }
          : column,
      ),
      getCoreRowModel: getCoreRowModel(),
      locale: "en-US",
      initialState: {
        columnVisibility: Object.fromEntries(
          initiallyHidden.map((id) => [id, false]),
        ),
      },
    }),
  );
  return result.current;
}

describe("useColumnVisibility", () => {
  it("should initialize with correct default values", () => {
    const { result } = renderHook(() => useColumnVisibility());
    expect(result.current.columnVisibility).toEqual({});
  });

  it("should seed hidden columns as { name: false }", () => {
    const { result } = renderHook(() => useColumnVisibility(["a", "b"]));
    expect(result.current.columnVisibility).toEqual({ a: false, b: false });
  });

  it("should treat empty hidden list as a no-op", () => {
    const { result } = renderHook(() => useColumnVisibility([]));
    expect(result.current.columnVisibility).toEqual({});
  });

  it("should update visibility state via setter", () => {
    const { result } = renderHook(() => useColumnVisibility(["a"]));

    act(() => {
      result.current.setColumnVisibility({ a: true, b: false });
    });

    expect(result.current.columnVisibility).toEqual({ a: true, b: false });
  });

  it("should handle functional updates", () => {
    const { result } = renderHook(() => useColumnVisibility(["a"]));

    act(() => {
      result.current.setColumnVisibility((prev) => ({ ...prev, c: false }));
    });

    expect(result.current.columnVisibility).toEqual({ a: false, c: false });
  });
});

describe("getShowOnlyVisibility", () => {
  it("shows matching hideable columns and hides the rest", () => {
    const table = createTestTable({ initiallyHidden: ["cust_age"] });

    expect(
      getShowOnlyVisibility(table, ["customer_name", "order_total"]),
    ).toEqual({
      customer_name: true,
      cust_age: false,
      order_total: true,
    });
  });

  it("ignores non-hideable columns in the input", () => {
    const table = createTestTable({ nonHideable: ["customer_name"] });

    expect(
      getShowOnlyVisibility(table, [
        SELECT_COLUMN_ID,
        "customer_name",
        "cust_age",
      ]),
    ).toEqual({
      cust_age: true,
      order_total: false,
    });
  });

  it("hides every hideable column when the input is empty", () => {
    const table = createTestTable();

    expect(getShowOnlyVisibility(table, [])).toEqual({
      customer_name: false,
      cust_age: false,
      order_total: false,
    });
  });
});

describe("isShowingOnly", () => {
  it("returns true when visible hideable columns match the input", () => {
    const table = createTestTable({
      initiallyHidden: ["cust_age", "order_total"],
    });

    expect(isShowingOnly(table, ["customer_name"])).toBe(true);
  });

  it("returns false when extra hideable columns remain visible", () => {
    const table = createTestTable();

    expect(isShowingOnly(table, ["customer_name"])).toBe(false);
  });

  it("ignores non-hideable columns in the input", () => {
    const table = createTestTable({
      initiallyHidden: ["cust_age", "order_total"],
      nonHideable: ["customer_name"],
    });

    expect(isShowingOnly(table, [SELECT_COLUMN_ID, "customer_name"])).toBe(
      true,
    );
  });

  it("returns true when every hideable column is hidden and the input is empty", () => {
    const table = createTestTable({
      initiallyHidden: ["customer_name", "cust_age", "order_total"],
    });

    expect(isShowingOnly(table, [])).toBe(true);
  });
});
