/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { columnToFieldTypesSchema } from "../schema";

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
      ["geom", ["geometry", "geometry"]],
      ["label", ["string", "object"]],
    ]);

    expect(result).toEqual([
      ["geom", ["unknown", "geometry"]],
      ["label", ["string", "object"]],
    ]);
  });
});
