/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { columnToFieldTypesSchema, TransformationsSchema } from "../schema";
import type { ColumnId } from "../types";

describe("pending transforms", () => {
  it.each([
    { type: "group_by", column_ids: [] },
    {
      type: "pivot",
      column_ids: ["col"],
      index_column_ids: [],
      value_column_ids: [],
    },
    { type: "column_conversion", column_id: "col" },
    { type: "explode_columns", column_ids: [] },
    { type: "unique", column_ids: [] },
    { type: "aggregate", column_ids: [] },
    { type: "select_columns", column_ids: [] },
    { type: "sample_rows" },
    { type: "filter_rows", where: [] },
    { type: "group_by" },
    { type: "explode_columns" },
    { type: "unique" },
    { type: "aggregate" },
    { type: "select_columns" },
    { type: "pivot", index_column_ids: ["index"] },
  ])("rejects incomplete $type", (transform) => {
    expect(
      TransformationsSchema.safeParse({ transforms: [transform] }).success,
    ).toBe(false);
  });

  it.each([
    { type: "group_by", column_ids: ["col"], aggregation_column_ids: [] },
    {
      type: "pivot",
      column_ids: ["col"],
      index_column_ids: ["index"],
      value_column_ids: [],
    },
    {
      type: "pivot",
      column_ids: ["col"],
      index_column_ids: [],
      value_column_ids: ["value"],
    },
  ])("accepts configured $type", (transform) => {
    expect(
      TransformationsSchema.safeParse({ transforms: [transform] }).success,
    ).toBe(true);
  });
});

describe("columnToFieldTypesSchema", () => {
  it("keeps known field types", () => {
    const result = columnToFieldTypesSchema.parse([
      ["count", ["integer", "int64"]],
      ["label", ["string", "object"]],
    ]);

    expect(result).toEqual([
      ["count", ["integer", "int64"]],
      ["label", ["string", "object"]],
    ]);
  });

  it("normalizes an unrecognized field type without discarding other fields", () => {
    const result = columnToFieldTypesSchema.parse([
      ["geom", ["bogus_type", "geometry"]],
      ["label", ["string", "object"]],
    ]);

    expect(result).toEqual([
      ["geom", ["unknown", "geometry"]],
      ["label", ["string", "object"]],
    ]);
  });

  it("keeps the geometry field type", () => {
    const result = columnToFieldTypesSchema.parse([
      ["geom", ["geometry", "geometry"]],
    ]);

    expect(result).toEqual([["geom", ["geometry", "geometry"]]]);
  });
});

describe("FilterRowsTransformSchema", () => {
  const condition = {
    column_id: "col" as ColumnId,
    operator: "in" as const,
    value: ["a"],
    type: "condition" as const,
    negate: false,
  };

  it("does not wrap where in a FilterGroup", () => {
    const result = TransformationsSchema.parse({
      transforms: [
        {
          type: "filter_rows",
          operation: "keep_rows",
          where: [condition],
        },
      ],
    });

    expect(result).toEqual({
      transforms: [
        {
          type: "filter_rows",
          operation: "keep_rows",
          where: [condition],
        },
      ],
    });
  });
});
