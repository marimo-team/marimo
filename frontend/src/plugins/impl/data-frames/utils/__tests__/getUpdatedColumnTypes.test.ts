/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { getUpdatedColumnTypes } from "../getUpdatedColumnTypes";
import type { TransformType } from "../../schema";
import type { ColumnId } from "../../types";

const INITIAL_COLUMN_TYPES = new Map<ColumnId, string>([
  ["col1" as ColumnId, "str"],
  [2 as ColumnId, "bool"],
  ["col3" as ColumnId, "int"],
]);

const Transforms = {
  COLUMN_CONVERSION: {
    type: "column_conversion",
    column_id: "col1" as ColumnId,
    data_type: "bool",
    errors: "ignore",
  } satisfies TransformType,
  RENAME_COLUMN: {
    type: "rename_column",
    column_id: 2 as ColumnId,
    new_column_id: "newCol2" as ColumnId,
  } satisfies TransformType,
  GROUP_BY: {
    type: "group_by",
    column_ids: ["col1", "col3"] as ColumnId[],
    aggregation: "max",
    drop_na: true,
  } satisfies TransformType,
  GROUP_BY_CHAINED: {
    type: "group_by",
    column_ids: ["newCol2"] as ColumnId[],
    aggregation: "max",
    drop_na: true,
  } satisfies TransformType,
  AGGREGATE: {
    type: "aggregate",
    column_ids: ["col1"] as ColumnId[],
    aggregations: ["max"],
  } satisfies TransformType,
  AGGREGATE_CHAINED: {
    type: "aggregate",
    column_ids: ["col1", "col3"] as ColumnId[],
    aggregations: ["max"],
  } satisfies TransformType,
  SELECT_COLUMNS: {
    type: "select_columns",
    column_ids: ["col1", 2] as ColumnId[],
  } satisfies TransformType,
  EXPLODE_COLUMNS: {
    type: "explode_columns",
    column_ids: ["col1", 2] as ColumnId[],
  } satisfies TransformType,
  EXPAND_DICT: {
    type: "expand_dict",
    column_id: "col1" as ColumnId,
  } satisfies TransformType,
  UNIQUE: {
    type: "unique",
    column_ids: ["col1"] as ColumnId[],
    keep: "first",
  } satisfies TransformType,
};

describe("getUpdatedColumnTypes", () => {
  it("should update column types for column conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.COLUMN_CONVERSION],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "bool",
        2 => "bool",
        "col3" => "int",
      }
    `);
  });

  it("should update column types for rename conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.RENAME_COLUMN],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "str",
        "col3" => "int",
        "newCol2" => "bool",
      }
    `);
  });

  it("should update column types for group-by conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.GROUP_BY],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        2 => "bool",
      }
    `);
  });

  it("should update column types for aggregate conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.AGGREGATE],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "str",
      }
    `);
  });

  it("should update column types for select-columns conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.SELECT_COLUMNS],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "str",
        2 => "bool",
      }
    `);
  });

  it("should update column types for explode-columns conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.EXPLODE_COLUMNS],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "str",
        2 => "bool",
        "col3" => "int",
      }
    `);
  });

  it("should update column types for expand-dict conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.EXPAND_DICT],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "str",
        2 => "bool",
        "col3" => "int",
      }
    `);
  });

  it("should update column types for unique conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.UNIQUE],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "str",
        2 => "bool",
        "col3" => "int",
      }
    `);
  });

  it("can chain multiple transforms", () => {
    const result = getUpdatedColumnTypes(
      [
        Transforms.COLUMN_CONVERSION,
        Transforms.RENAME_COLUMN,
        Transforms.GROUP_BY_CHAINED,
        Transforms.AGGREGATE_CHAINED,
      ],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      Map {
        "col1" => "bool",
        "col3" => "int",
      }
    `);
  });
});
