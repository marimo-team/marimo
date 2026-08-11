/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { ChartSchema } from "../schemas";

describe("ChartSchema", () => {
  it("normalizes an unrecognized axis column type", () => {
    const result = ChartSchema.parse({
      general: { xColumn: { field: "geom", type: "geometry" } },
    });

    expect(result.general?.xColumn?.type).toBe("unknown");
  });

  it("normalizes an unrecognized tooltip field type", () => {
    const result = ChartSchema.parse({
      tooltips: {
        auto: false,
        fields: [{ field: "geom", type: "geometry" }],
      },
    });

    expect(result.tooltips?.fields).toEqual([
      { field: "geom", type: "unknown" },
    ]);
  });
});
