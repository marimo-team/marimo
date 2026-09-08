/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { columnToFieldTypesSchema, TransformationsSchema } from "../schema";
import type { ColumnId } from "../types";

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
