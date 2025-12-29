/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import type { ColumnDataTypes, ColumnId } from "../../types";
import { getEffectiveColumns } from "../getEffectiveColumns";

describe("getEffectiveColumns", () => {
  const originalColumns: ColumnDataTypes = new Map([
    ["id" as ColumnId, "int64"],
    ["name" as ColumnId, "string"],
    ["value" as ColumnId, "float64"],
  ]);

  // Helper to create field types in the backend format
  const createFieldTypes = (
    cols: [string, string][],
  ): FieldTypesWithExternalType => {
    return cols.map(([name, dataType]) => [
      name,
      [dataType, dataType],
    ]) as FieldTypesWithExternalType;
  };

  it("returns original columns when columnTypesPerStep is undefined", () => {
    const result = getEffectiveColumns(originalColumns, undefined, 0);
    expect(result).toBe(originalColumns);
  });

  it("returns original columns when columnTypesPerStep is empty", () => {
    const result = getEffectiveColumns(originalColumns, [], 0);
    expect(result).toBe(originalColumns);
  });

  it("returns original columns when selectedTransform is undefined", () => {
    const columnTypesPerStep = [
      createFieldTypes([
        ["id", "int64"],
        ["name", "string"],
      ]),
    ];
    const result = getEffectiveColumns(
      originalColumns,
      columnTypesPerStep,
      undefined,
    );
    // Should use index 0 (original columns from backend)
    expect(result.size).toBe(2);
    expect(result.get("id" as ColumnId)).toBe("int64");
    expect(result.get("name" as ColumnId)).toBe("string");
  });

  it("returns columns at the correct step index", () => {
    const columnTypesPerStep = [
      // Step 0: original
      createFieldTypes([
        ["id", "int64"],
        ["name", "string"],
        ["value", "float64"],
      ]),
      // Step 1: after first transform (renamed 'name' to 'title')
      createFieldTypes([
        ["id", "int64"],
        ["title", "string"],
        ["value", "float64"],
      ]),
      // Step 2: after second transform (selected only id and title)
      createFieldTypes([
        ["id", "int64"],
        ["title", "string"],
      ]),
    ];

    // When editing transform 0, should see original columns (step 0)
    const result0 = getEffectiveColumns(originalColumns, columnTypesPerStep, 0);
    expect(result0.size).toBe(3);
    expect(result0.has("name" as ColumnId)).toBe(true);

    // When editing transform 1, should see columns after transform 0 (step 1)
    const result1 = getEffectiveColumns(originalColumns, columnTypesPerStep, 1);
    expect(result1.size).toBe(3);
    expect(result1.has("title" as ColumnId)).toBe(true);
    expect(result1.has("name" as ColumnId)).toBe(false);

    // When editing transform 2, should see columns after transform 1 (step 2)
    const result2 = getEffectiveColumns(originalColumns, columnTypesPerStep, 2);
    expect(result2.size).toBe(2);
    expect(result2.has("value" as ColumnId)).toBe(false);
  });

  it("clamps to max valid index when selectedTransform exceeds array length", () => {
    const columnTypesPerStep = [
      createFieldTypes([
        ["id", "int64"],
        ["name", "string"],
      ]),
      createFieldTypes([
        ["id", "int64"],
        ["renamed", "string"],
      ]),
    ];

    // selectedTransform = 5, but only 2 steps available
    // Should clamp to index 1 (last available)
    const result = getEffectiveColumns(originalColumns, columnTypesPerStep, 5);
    expect(result.size).toBe(2);
    expect(result.has("renamed" as ColumnId)).toBe(true);
  });

  it("handles pivot transform with dynamic column names", () => {
    const columnTypesPerStep = [
      // Step 0: original
      createFieldTypes([
        ["product", "string"],
        ["color", "string"],
        ["sales", "int64"],
      ]),
      // Step 1: after pivot on 'color' with values 'red', 'blue'
      createFieldTypes([
        ["product", "string"],
        ["sales_red_sum", "int64"],
        ["sales_blue_sum", "int64"],
      ]),
    ];

    const result = getEffectiveColumns(originalColumns, columnTypesPerStep, 1);
    expect(result.size).toBe(3);
    expect(result.has("product" as ColumnId)).toBe(true);
    expect(result.has("sales_red_sum" as ColumnId)).toBe(true);
    expect(result.has("sales_blue_sum" as ColumnId)).toBe(true);
    expect(result.has("color" as ColumnId)).toBe(false);
    expect(result.has("sales" as ColumnId)).toBe(false);
  });
});
