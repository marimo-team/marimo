/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { getUpdatedColumnTypes } from "../getUpdatedColumnTypes";
import { TransformType } from "../../schema";

const INITIAL_COLUMN_TYPES = {
  col1: "str",
  col2: "bool",
  col3: "int",
};

const Transforms = {
  COLUMN_CONVERSION: {
    type: "column_conversion",
    column_id: "col1",
    data_type: "bool",
    errors: "ignore",
  } satisfies TransformType,
  RENAME_COLUMN: {
    type: "rename_column",
    column_id: "col2",
    new_column_id: "newCol2",
  } satisfies TransformType,
  GROUP_BY: {
    type: "group_by",
    column_ids: ["col1", "col3"],
    aggregation: "max",
    drop_na: true,
  } satisfies TransformType,
  GROUP_BY_CHAINED: {
    type: "group_by",
    column_ids: ["newCol2"],
    aggregation: "max",
    drop_na: true,
  } satisfies TransformType,
  AGGREGATE: {
    type: "aggregate",
    column_ids: ["col1"],
    aggregations: ["max"],
  } satisfies TransformType,
  AGGREGATE_CHAINED: {
    type: "aggregate",
    column_ids: ["col1", "col3"],
    aggregations: ["max"],
  } satisfies TransformType,
  SELECT_COLUMNS: {
    type: "select_columns",
    column_ids: ["col1", "col2"],
  } satisfies TransformType,
};

describe("getUpdatedColumnTypes", () => {
  it("should update column types for column conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.COLUMN_CONVERSION],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      {
        "col1": "bool",
        "col2": "bool",
        "col3": "int",
      }
    `);
  });

  it("should update column types for rename conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.RENAME_COLUMN],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      {
        "col1": "str",
        "col3": "int",
        "newCol2": "bool",
      }
    `);
  });

  it("should update column types for group-by conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.GROUP_BY],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      {
        "col2": "bool",
      }
    `);
  });

  it("should update column types for aggregate conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.AGGREGATE],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      {
        "col1": "str",
      }
    `);
  });

  it("should update column types for select-columns conversion", () => {
    const result = getUpdatedColumnTypes(
      [Transforms.SELECT_COLUMNS],
      INITIAL_COLUMN_TYPES,
    );
    expect(result).toMatchInlineSnapshot(`
      {
        "col1": "str",
        "col2": "bool",
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
      {
        "col1": "bool",
        "col3": "int",
      }
    `);
  });
});
