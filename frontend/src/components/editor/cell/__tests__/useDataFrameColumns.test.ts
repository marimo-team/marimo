/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DataTable } from "@/core/kernel/messages";
import { useDataFrameColumns } from "../useDataFrameColumns";

// Mock the jotai module
vi.mock("jotai", async () => {
  const actual = await vi.importActual("jotai");
  return {
    ...actual,
    useAtomValue: vi.fn(),
  };
});

describe("useDataFrameColumns", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return empty array when no tables exist", async () => {
    const { useAtomValue } = await import("jotai");
    vi.mocked(useAtomValue).mockReturnValue([]);

    const { result } = renderHook(() => useDataFrameColumns());

    expect(result.current).toEqual([]);
  });

  it("should filter local tables with variable names", async () => {
    const { useAtomValue } = await import("jotai");
    const mockTables: DataTable[] = [
      {
        name: "table1",
        source_type: "local",
        variable_name: "df1",
        num_rows: 100,
        num_columns: 5,
        columns: [
          { name: "col1", type: "int64", external_type: "int64" },
          { name: "col2", type: "float64", external_type: "float64" },
        ],
      } as DataTable,
      {
        name: "table2",
        source_type: "duckdb",
        variable_name: "df2",
        num_rows: 50,
        num_columns: 3,
        columns: [],
      } as DataTable,
    ];

    vi.mocked(useAtomValue).mockReturnValue(mockTables);

    const { result } = renderHook(() => useDataFrameColumns());

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("df1");
    expect(result.current[0].columns).toHaveLength(2);
  });

  it("should exclude tables without variable names", async () => {
    const { useAtomValue } = await import("jotai");
    const mockTables: DataTable[] = [
      {
        name: "table1",
        source_type: "local",
        variable_name: null,
        columns: [],
      } as DataTable,
    ];

    vi.mocked(useAtomValue).mockReturnValue(mockTables);

    const { result } = renderHook(() => useDataFrameColumns());

    expect(result.current).toEqual([]);
  });

  it("should generate correct table descriptions", async () => {
    const { useAtomValue } = await import("jotai");
    const mockTables: DataTable[] = [
      {
        name: "table1",
        source_type: "local",
        variable_name: "df1",
        num_rows: 100,
        num_columns: 5,
        columns: [],
      } as DataTable,
      {
        name: "table2",
        source_type: "local",
        variable_name: "df2",
        num_rows: 50,
        num_columns: null,
        columns: [],
      } as DataTable,
    ];

    vi.mocked(useAtomValue).mockReturnValue(mockTables);

    const { result } = renderHook(() => useDataFrameColumns());

    expect(result.current[0].value).toBe("100 rows x 5 columns");
    expect(result.current[1].value).toBe("50 rows");
  });

  it("should sort dataframes by name", async () => {
    const { useAtomValue } = await import("jotai");
    const mockTables: DataTable[] = [
      {
        name: "table3",
        source_type: "local",
        variable_name: "zdf",
        columns: [],
      } as DataTable,
      {
        name: "table1",
        source_type: "local",
        variable_name: "adf",
        columns: [],
      } as DataTable,
      {
        name: "table2",
        source_type: "local",
        variable_name: "mdf",
        columns: [],
      } as DataTable,
    ];

    vi.mocked(useAtomValue).mockReturnValue(mockTables);

    const { result } = renderHook(() => useDataFrameColumns());

    expect(result.current).toHaveLength(3);
    expect(result.current[0].name).toBe("adf");
    expect(result.current[1].name).toBe("mdf");
    expect(result.current[2].name).toBe("zdf");
  });

  it("should include column information", async () => {
    const { useAtomValue } = await import("jotai");
    const mockTables: DataTable[] = [
      {
        name: "table1",
        source_type: "local",
        variable_name: "df",
        columns: [
          { name: "id", type: "int64", external_type: "INT64" },
          { name: "name", type: "string", external_type: "VARCHAR" },
          { name: "price", type: "float64", external_type: "DOUBLE" },
        ],
      } as DataTable,
    ];

    vi.mocked(useAtomValue).mockReturnValue(mockTables);

    const { result } = renderHook(() => useDataFrameColumns());

    expect(result.current[0].columns).toHaveLength(3);
    expect(result.current[0].columns[0].name).toBe("id");
    expect(result.current[0].columns[1].name).toBe("name");
    expect(result.current[0].columns[2].name).toBe("price");
  });

  it("should handle tables with no columns", async () => {
    const { useAtomValue } = await import("jotai");
    const mockTables: DataTable[] = [
      {
        name: "table1",
        source_type: "local",
        variable_name: "df",
        columns: undefined,
      } as DataTable,
    ];

    vi.mocked(useAtomValue).mockReturnValue(mockTables);

    const { result } = renderHook(() => useDataFrameColumns());

    expect(result.current[0].columns).toEqual([]);
  });
});
