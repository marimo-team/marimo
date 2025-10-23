/* Copyright 2024 Marimo. All rights reserved. */

import { mint, slate } from "@radix-ui/colors";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";

export function getLegacyBooleanSpec(
  column: string,
  base: TopLevelFacetedUnitSpec,
  barHeight: number,
): TopLevelFacetedUnitSpec {
  return {
    ...base,
    mark: { type: "bar", color: mint.mint11 },
    encoding: {
      y: {
        field: column,
        type: "nominal",
        axis: {
          labelExpr:
            "datum.label === 'true' || datum.label === 'True'  ? 'True' : 'False'",
          tickWidth: 0,
          title: null,
          labelColor: slate.slate9,
        },
      },
      x: {
        aggregate: "count",
        type: "quantitative",
        axis: null,
        scale: { type: "linear" },
      },
      tooltip: [
        { field: column, type: "nominal", title: "Value" },
        {
          aggregate: "count",
          type: "quantitative",
          title: "Count",
          format: ",d",
        },
      ],
    },
    layer: [
      {
        mark: {
          type: "bar",
          color: mint.mint11,
          height: barHeight,
        },
      },
      {
        mark: {
          type: "text",
          align: "left",
          baseline: "middle",
          dx: 3,
          color: slate.slate9,
        },
        encoding: {
          text: {
            aggregate: "count",
            type: "quantitative",
          },
        },
      },
    ],
  } as TopLevelFacetedUnitSpec; // "layer" not in TopLevelFacetedUnitSpec
}
