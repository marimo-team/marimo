/* Copyright 2024 Marimo. All rights reserved. */
import { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { VegaType } from "@/plugins/impl/vega/vega-loader";
import { mint, orange, slate } from "@radix-ui/colors";
import { ColumnHeaderSummary } from "./types";

export class ColumnChartSpecModel<T> {
  private columnSummaries = new Map<string | number, ColumnHeaderSummary>();

  public static readonly EMPTY = new ColumnChartSpecModel([], {}, [], {
    includeCharts: false,
  });

  constructor(
    private readonly data: T[],
    private readonly fieldTypes: Record<string, VegaType>,
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
    const base: Omit<TopLevelFacetedUnitSpec, "mark"> = {
      data: {
        name: "values",
      },
      datasets: {
        values: this.data,
      },
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
          mark: { type: "bar", color: mint.mint11 },
          encoding: {
            x: { field: column, type: "temporal", axis: null, bin: true },
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
          mark: { type: "bar", color: mint.mint11 },
          encoding: {
            x: { field: column, type: "nominal", axis: null, bin: true },
            y: {
              aggregate: "count",
              type: "quantitative",
              axis: null,
              scale: { type: "symlog" },
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
                labelExpr: "datum.label === 'true' ? 'True' : 'False'",
                tickWidth: 0,
                title: null,
                labelColor: slate.slate9,
              },
            },
            x: {
              aggregate: "count",
              type: "quantitative",
              axis: null,
              scale: { type: "symlog" },
            },
            tooltip: [
              { field: column, type: "nominal", format: ",d", title: "Value" },
              {
                aggregate: "count",
                type: "quantitative",
                title: "Count",
                format: ",d",
              },
            ],
          },
        };
      case "unknown":
      case "string":
        return null;
      default:
        return null;
    }
  }
}
