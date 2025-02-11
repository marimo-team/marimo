/* Copyright 2024 Marimo. All rights reserved. */
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { mint, orange, slate } from "@radix-ui/colors";
import type { ColumnHeaderSummary, FieldTypes } from "./types";
import { asURL } from "@/utils/url";
import { parseCsvData } from "@/plugins/impl/vega/loader";
import { logNever } from "@/utils/assertNever";
import type { TopLevelSpec } from "vega-lite";

const MAX_BAR_HEIGHT = 24; // px
const MAX_BAR_WIDTH = 28; // px
const CONTAINER_WIDTH = 120; // px
const PAD = 1; // px

export class ColumnChartSpecModel<T> {
  private columnSummaries = new Map<string | number, ColumnHeaderSummary>();

  public static readonly EMPTY = new ColumnChartSpecModel([], {}, [], {
    includeCharts: false,
  });

  private dataSpec: TopLevelSpec["data"];
  private sourceName: "data_0" | "source_0";

  constructor(
    private readonly data: T[] | string,
    private readonly fieldTypes: FieldTypes,
    readonly summaries: ColumnHeaderSummary[],
    private readonly opts: {
      includeCharts: boolean;
    },
  ) {
    // Data may come in from a few different sources:
    // - A URL
    // - A CSV data URI (e.g. "data:text/csv;base64,...")
    // - A CSV string (e.g. "a,b,c\n1,2,3\n4,5,6")
    // - An array of objects
    // For each case, we need to set up the data spec and source name appropriately.
    // If its a file, the source name will be "source_0", otherwise it will be "data_0".
    // We have a few snapshot tests to ensure that the spec is correct for each case.
    if (typeof this.data === "string") {
      if (this.data.startsWith("./@file") || this.data.startsWith("/@file")) {
        this.dataSpec = {
          url: asURL(this.data).href,
        };
        this.sourceName = "data_0"; // This is data_0 because the data gets loaded before passing to Vega
      } else if (this.data.startsWith("data:text/csv;base64,")) {
        const decoded = atob(this.data.split(",")[1]);
        this.dataSpec = {
          values: parseCsvData(decoded) as T[],
        };
        this.sourceName = "data_0";
      } else {
        // Assume it's a CSV string
        this.dataSpec = {
          values: parseCsvData(this.data) as T[],
        };
        this.sourceName = "data_0";
      }
    } else {
      this.dataSpec = {
        values: this.data,
      };
      this.sourceName = "source_0";
    }

    this.columnSummaries = new Map(summaries.map((s) => [s.column, s]));
  }

  public getHeaderSummary(column: string) {
    return {
      summary: this.columnSummaries.get(column),
      type: this.fieldTypes[column],
      spec: this.opts.includeCharts ? this.getVegaSpec(column) : undefined,
    };
  }

  private getVegaSpec<_T>(column: string): TopLevelFacetedUnitSpec | null {
    if (!this.data) {
      return null;
    }
    const base: Omit<TopLevelFacetedUnitSpec, "mark"> = {
      data: this.dataSpec as TopLevelFacetedUnitSpec["data"],
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

    // https://github.com/vega/altair/blob/32990a597af7c09586904f40b3f5e6787f752fa5/doc/user_guide/encodings/index.rst#escaping-special-characters-in-column-names
    // escape periods in column names
    column = column.replaceAll(".", "\\.");
    // escape brackets in column names
    column = column.replaceAll("[", "\\[").replaceAll("]", "\\]");
    // escape colons in column names
    column = column.replaceAll(":", "\\:");

    const scale = this.getScale();
    const variableWidth = `min(${MAX_BAR_WIDTH}, ${CONTAINER_WIDTH} / length(data('${this.sourceName}')) - ${PAD})`;

    switch (type) {
      case "date":
      case "datetime":
      case "time":
        return {
          ...base,
          mark: {
            type: "bar",
            color: mint.mint11,
            width: { expr: variableWidth },
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
                format:
                  type === "date"
                    ? "%Y-%m-%d"
                    : type === "time"
                      ? "%H:%M:%S"
                      : "%Y-%m-%dT%H:%M:%S",
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
            size: { expr: variableWidth },
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
        logNever(type);
        return null;
    }
  }

  private getScale() {
    return {
      align: 0,
      paddingInner: 0,
      paddingOuter: {
        expr: `length(data('${this.sourceName}')) == 2 ? 1 : length(data('${this.sourceName}')) == 3 ? 0.5 : length(data('${this.sourceName}')) == 4 ? 0 : 0`,
      },
    };
  }
}
