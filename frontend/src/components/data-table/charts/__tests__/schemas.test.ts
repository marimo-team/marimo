/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { ChartSchema } from "../schemas";

describe("ChartSchema", () => {
  it.each(["hours", "yearmonthdatehours"] as const)(
    "preserves the %s time unit in saved chart configurations",
    (timeUnit) => {
      const column = {
        field: "timestamp",
        selectedDataType: "temporal",
        sort: "ascending",
        timeUnit,
      };
      const config = {
        general: {
          xColumn: { ...column, aggregate: "none" },
          yColumn: { ...column, aggregate: "none" },
          facet: {
            row: { ...column, linkYAxis: true, binned: true, maxbins: 6 },
            column: { ...column, linkXAxis: true, binned: true, maxbins: 6 },
          },
        },
        tooltips: { auto: true, fields: [] },
      };

      expect(ChartSchema.parse(config)).toEqual(config);
    },
  );

  it("keeps a known axis column type", () => {
    const result = ChartSchema.parse({
      general: { xColumn: { field: "count", type: "integer" } },
    });

    expect(result.general?.xColumn?.type).toBe("integer");
  });

  it("normalizes an unrecognized axis column type", () => {
    const result = ChartSchema.parse({
      general: { xColumn: { field: "geom", type: "bogus_type" } },
    });

    expect(result.general?.xColumn?.type).toBe("unknown");
  });

  it("normalizes an unrecognized tooltip field type", () => {
    const result = ChartSchema.parse({
      tooltips: {
        auto: false,
        fields: [{ field: "geom", type: "bogus_type" }],
      },
    });

    expect(result.tooltips?.fields).toEqual([
      { field: "geom", type: "unknown" },
    ]);
  });

  it("keeps geometry axis and tooltip field types", () => {
    const result = ChartSchema.parse({
      general: { xColumn: { field: "geom", type: "geometry" } },
      tooltips: {
        auto: false,
        fields: [{ field: "geom", type: "geometry" }],
      },
    });

    expect(result.general?.xColumn?.type).toBe("geometry");
    expect(result.tooltips?.fields).toEqual([
      { field: "geom", type: "geometry" },
    ]);
  });
});
