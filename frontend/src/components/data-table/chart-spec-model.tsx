/* Copyright 2024 Marimo. All rights reserved. */
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { mint, orange, slate } from "@radix-ui/colors";
import type { ColumnHeaderSummary, FieldTypes } from "./types";
import { asURL } from "@/utils/url";

const MAX_BAR_HEIGHT = 24; // px
const MAX_BAR_WIDTH = 28; // px
const CONTAINER_WIDTH = 120; // px
const PAD = 1; // px
const VARIABLE_WIDTH = `min(${MAX_BAR_WIDTH}, ${CONTAINER_WIDTH} / length(data('source_0')) - ${PAD})`;

const scale = {
  align: 0,
  paddingInner: 0,
  paddingOuter: {
    expr: "length(data('source_0')) == 2 ? 1 : length(data('source_0')) == 3 ? 0.5 : length(data('source_0')) == 4 ? 0 : 0",
  },
};

export class ColumnChartSpecModel<T> {
  private columnSummaries = new Map<string | number, ColumnHeaderSummary>();

  public static readonly EMPTY = new ColumnChartSpecModel([], {}, [], {
    includeCharts: false,
  });

  constructor(
    private readonly data: T[] | string,
    private readonly fieldTypes: FieldTypes,
    readonly summaries: ColumnHeaderSummary[],
    private readonly opts: {
      includeCharts: boolean;
    },
  ) {
    this.columnSummaries = new Map(summaries.map((s) => [s.column, s]));
  }

  public getHeaderSummary(column: string) {
    return {
      summary: this.columnSummaries.get(column),
      type: this.fieldTypes[column],
      spec: this.opts.includeCharts ? this.getVegaSpec(column) : undefined,
    };
  }

  private getVegaSpec<T>(column: string): TopLevelFacetedUnitSpec | null {
    if (!this.data) {
      return null;
    }
    if (typeof this.data !== "string") {
      return null;
    }

    const base: Omit<TopLevelFacetedUnitSpec, "mark"> = {
      data: {
        url: asURL(this.data).href,
      } as TopLevelFacetedUnitSpec["data"],
      background: "transparent",
      config: {
        view: {
          stroke: "transparent",
        },
        axis: {
          domain: false,
        },
      },
      height: 100,
    };
    const type = this.fieldTypes[column];

    switch (type) {
      case "date":
        return {
          ...base,
          mark: {
            type: "bar",
            color: mint.mint11,
            width: { expr: VARIABLE_WIDTH },
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
            tooltip: [
              {
                field: column,
                type: "temporal",
                format: "%Y-%m-%d",
                bin: true,
                title: column,
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
        };
      case "integer":
      case "number": {
        const format = type === "integer" ? ",d" : ".2f";
        return {
          ...base,
          mark: {
            type: "bar",
            color: mint.mint11,
            size: { expr: VARIABLE_WIDTH },
            align: "right",
          },
          encoding: {
            x: {
              field: column,
              type: "nominal",
              axis: null,
              bin: true,
              scale: scale,
            },
            y: {
              aggregate: "count",
              type: "quantitative",
              axis: null,
              scale: { type: "linear" },
            },
            tooltip: [
              {
                field: column,
                type: "nominal",
                format: format,
                bin: true,
                title: column,
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
        };
      }
      case "boolean":
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
                height: MAX_BAR_HEIGHT,
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
      case "unknown":
      case "string":
        return null;
      default:
        return null;
    }
  }
}
