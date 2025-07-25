/* Copyright 2024 Marimo. All rights reserved. */

// New spec is under a feature flag, we keep this until full migration

import { mint, orange, slate } from "@radix-ui/colors";
import type { Scale } from "vega-lite/build/src/scale";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";

export function getLegacyNumericSpec(
  column: string,
  format: string,
  base: TopLevelFacetedUnitSpec,
): TopLevelFacetedUnitSpec {
  return {
    ...base, // Assuming base contains shared configurations
    // Two layers: one with the visible bars, and one with invisible bars
    // that provide a larger tooltip area.
    // @ts-expect-error 'layer' property not in TopLevelFacetedUnitSpec
    layer: [
      {
        mark: {
          type: "bar",
          color: mint.mint11,
        },
        encoding: {
          x: {
            field: column,
            type: "quantitative",
            bin: true,
          },
          y: {
            aggregate: "count",
            type: "quantitative",
            axis: null,
          },
        },
      },

      // Tooltip layer
      {
        mark: {
          type: "bar",
          opacity: 0,
        },
        encoding: {
          x: {
            field: column,
            type: "quantitative",
            bin: true,
            axis: {
              title: null,
              labelFontSize: 8.5,
              labelOpacity: 0.5,
              labelExpr:
                "(datum.value >= 10000 || datum.value <= -10000) ? format(datum.value, '.2e') : format(datum.value, '.2~f')",
            },
          },
          y: {
            aggregate: "max",
            type: "quantitative",
            axis: null,
          },
          tooltip: [
            {
              field: column,
              type: "quantitative",
              bin: true,
              title: column,
              format: format,
            },
            {
              aggregate: "count",
              type: "quantitative",
              title: "Count",
              format: ",d",
            },
          ],
        },
      },
    ],
  };
}

export function getLegacyTemporalSpec(
  column: string,
  type: "date" | "datetime" | "time",
  base: TopLevelFacetedUnitSpec,
  scale: Scale,
): TopLevelFacetedUnitSpec {
  const format =
    type === "date"
      ? "%Y-%m-%d"
      : type === "time"
        ? "%H:%M:%S"
        : "%Y-%m-%dT%H:%M:%S";

  return {
    ...base,
    // Two layers: one with the visible bars, and one with invisible bars
    // that provide a larger tooltip area.
    // @ts-expect-error 'layer' property not in TopLevelFacetedUnitSpec
    layer: [
      {
        mark: {
          type: "bar",
          color: mint.mint11,
        },
        encoding: {
          x: {
            field: column,
            type: "temporal",
            axis: null,
            bin: true,
            scale: scale,
          },
          y: { aggregate: "count", type: "quantitative", axis: null },
          // Color nulls
          color: {
            condition: {
              test: `datum["bin_maxbins_10_${column}_range"] === "null"`,
              value: orange.orange11,
            },
            value: mint.mint11,
          },
        },
      },

      // 0 opacity full-height bars with tooltips, since it is too hard to trigger
      // the tooltip for very small bars.
      {
        mark: {
          type: "bar",
          opacity: 0,
        },
        encoding: {
          x: {
            field: column,
            type: "temporal",
            axis: null,
            bin: true,
            scale: scale,
          },
          y: { aggregate: "max", type: "quantitative", axis: null },
          tooltip: [
            {
              // Can also use column, but this is more explicit
              field: `bin_maxbins_10_${column}`,
              type: "temporal",
              format: format,
              bin: { binned: true },
              title: `${column} (start)`,
            },
            {
              field: `bin_maxbins_10_${column}_end`,
              type: "temporal",
              format: format,
              bin: { binned: true },
              title: `${column} (end)`,
            },
            {
              aggregate: "count",
              type: "quantitative",
              title: "Count",
              format: ",d",
            },
          ],
          // Color nulls
          color: {
            condition: {
              test: `datum["bin_maxbins_10_${column}_range"] === "null"`,
              value: orange.orange11,
            },
            value: mint.mint11,
          },
        },
      },
    ],
  };
}

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
