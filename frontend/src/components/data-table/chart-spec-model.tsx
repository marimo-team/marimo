/* Copyright 2024 Marimo. All rights reserved. */

import { mint, slate } from "@radix-ui/colors";
import type { TopLevelSpec } from "vega-lite";
import type { StringFieldDef } from "vega-lite/build/src/channeldef";
// @ts-expect-error vega-typings does not include formats
import { formats } from "vega-loader";
import { asRemoteURL } from "@/core/runtime/config";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { arrow } from "@/plugins/impl/vega/formats";
import { parseCsvData } from "@/plugins/impl/vega/loader";
import { logNever } from "@/utils/assertNever";
import {
  byteStringToBinary,
  extractBase64FromDataURL,
  isDataURLString,
  typedAtob,
} from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import {
  getLegacyNumericSpec,
  getLegacyTemporalSpec,
} from "./legacy-chart-spec";
import type {
  BinValues,
  ColumnHeaderStats,
  ColumnName,
  FieldTypes,
  ValueCounts,
} from "./types";

// We rely on vega's built-in binning to determine bar widths.
const MAX_BAR_HEIGHT = 20; // px

// Arrow formats have a magic number at the beginning of the file.
const ARROW_MAGIC_NUMBER = "ARROW1";

// register arrow reader under type 'arrow'
formats("arrow", arrow);

export class ColumnChartSpecModel<T> {
  private columnStats = new Map<ColumnName, ColumnHeaderStats>();
  private columnBinValues = new Map<ColumnName, BinValues>();
  private columnValueCounts = new Map<ColumnName, ValueCounts>();

  public static readonly EMPTY = new ColumnChartSpecModel(
    [],
    {},
    {},
    {},
    {},
    {
      includeCharts: false,
      usePreComputedValues: false,
    },
  );

  private dataSpec: TopLevelSpec["data"];
  private sourceName: "data_0" | "source_0";

  constructor(
    private readonly data: T[] | string,
    private readonly fieldTypes: FieldTypes,
    readonly stats: Record<ColumnName, ColumnHeaderStats>,
    readonly binValues: Record<ColumnName, BinValues>,
    readonly valueCounts: Record<ColumnName, ValueCounts>,
    private readonly opts: {
      includeCharts: boolean;
      usePreComputedValues?: boolean;
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
        this.dataSpec = { url: asRemoteURL(this.data).href };
        this.sourceName = "source_0";
      } else if (isDataURLString(this.data)) {
        this.sourceName = "data_0";
        const base64 = extractBase64FromDataURL(this.data);
        const decoded = typedAtob(base64);

        if (decoded.startsWith(ARROW_MAGIC_NUMBER)) {
          this.dataSpec = {
            values: byteStringToBinary(decoded),
            // @ts-expect-error vega-typings does not include arrow format
            format: { type: "arrow" },
          };
        } else {
          // Assume it's a CSV string
          this.parseCsv(decoded);
        }
      } else {
        // Assume it's a CSV string
        this.parseCsv(this.data);
        this.sourceName = "data_0";
      }
    } else {
      this.dataSpec = { values: this.data };
      this.sourceName = "source_0";
    }

    this.columnBinValues = new Map(Object.entries(binValues));
    this.columnStats = new Map(Object.entries(stats));
    this.columnValueCounts = new Map(Object.entries(valueCounts));
  }

  public getColumnStats(column: string) {
    return this.columnStats.get(column);
  }

  public getHeaderSummary(column: string) {
    return {
      stats: this.columnStats.get(column),
      type: this.fieldTypes[column],
      spec: this.opts.includeCharts ? this.getVegaSpec(column) : undefined,
    };
  }

  private parseCsv(data: string) {
    this.dataSpec = {
      values: parseCsvData(data) as T[],
    };
  }

  private getVegaSpec(column: string): TopLevelFacetedUnitSpec | null {
    if (!this.data) {
      return null;
    }

    const usePreComputedValues = this.opts.usePreComputedValues;
    const binValues = this.columnBinValues.get(column);
    const hasBinValues = binValues && binValues.length > 0;
    const valueCounts = this.columnValueCounts.get(column);
    const hasValueCounts = valueCounts && valueCounts.length > 0;

    let data = this.dataSpec as TopLevelFacetedUnitSpec["data"];
    if (usePreComputedValues) {
      if (hasBinValues) {
        data = { values: binValues, name: "bin_values" };
      } else if (hasValueCounts) {
        data = { values: valueCounts, name: "value_counts" };
      }
    }

    const base: TopLevelFacetedUnitSpec = {
      data,
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
    } as TopLevelFacetedUnitSpec;
    const type = this.fieldTypes[column];

    // https://github.com/vega/altair/blob/32990a597af7c09586904f40b3f5e6787f752fa5/doc/user_guide/encodings/index.rst#escaping-special-characters-in-column-names
    // escape periods in column names
    column = column.replaceAll(".", "\\.");
    // escape brackets in column names
    column = column.replaceAll("[", "\\[").replaceAll("]", "\\]");
    // escape colons in column names
    column = column.replaceAll(":", "\\:");

    const scale = this.getScale();

    switch (type) {
      case "date":
      case "datetime":
      case "time": {
        if (!usePreComputedValues || !hasValueCounts) {
          return getLegacyTemporalSpec(column, type, base, scale);
        }

        // TODO: This chart raises a warning on hover - WARN: Infinite extent for field "value": [Infinity, -Infinity]
        const xField = "value";
        const yField = "count";

        const tooltips: Array<StringFieldDef<string>> = [
          {
            field: xField,
            title: column,
            ...getPartialTimeTooltip(valueCounts),
          },
          {
            field: yField,
            type: "quantitative",
            title: "Count",
            format: ",d",
          },
        ];

        // If there is only one value, we show bar chart instead
        if (valueCounts.length === 1) {
          return {
            ...base,
            mark: {
              type: "bar",
              color: mint.mint11,
            },
            encoding: {
              x: {
                field: xField,
                axis: null,
                scale: scale,
              },
              y: {
                field: yField,
                type: "quantitative",
                axis: null,
              },
              tooltip: tooltips,
            },
          };
        }

        return {
          ...base,
          encoding: {
            x: {
              field: xField,
              type: "temporal",
              axis: null,
              scale: scale,
            },
          },
          // @ts-expect-error 'layer' property not in TopLevelFacetedUnitSpec
          layer: [
            {
              encoding: {
                y: {
                  field: yField,
                  type: "quantitative",
                  axis: null,
                },
              },
              layer: [
                {
                  mark: {
                    type: "area",
                    line: {
                      color: mint.mint11,
                    },
                    color: {
                      x1: 1,
                      y1: 1,
                      x2: 1,
                      y2: 0,
                      gradient: "linear",
                      stops: [
                        {
                          offset: 0,
                          color: mint.mint10,
                        },
                        {
                          offset: 0.6,
                          color: mint.mint11,
                        },
                        {
                          offset: 1,
                          color: mint.mint11,
                        },
                      ],
                    },
                  },
                },
                {
                  transform: [{ filter: { param: "hover", empty: false } }],
                  mark: "point",
                  encoding: {
                    size: {
                      value: 20,
                    },
                  },
                },
              ],
            },
            // Vertical rule line
            {
              mark: "rule",
              encoding: {
                opacity: {
                  condition: { value: 0.3, param: "hover", empty: false },
                  value: 0,
                },
                tooltip: tooltips,
              },
              params: [
                {
                  name: "hover",
                  select: {
                    type: "point",
                    fields: [xField],
                    nearest: true,
                    on: "pointerover",
                    clear: "pointerout",
                  },
                },
              ],
            },
          ],
        };
      }
      case "integer":
      case "number": {
        // Create a histogram spec that properly handles null values
        const format = type === "integer" ? ",d" : ".2f";

        if (!usePreComputedValues || !hasBinValues) {
          return getLegacyNumericSpec(column, format, base);
        }

        const stats = this.columnStats.get(column);

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
                stroke: mint.mint11,
                strokeWidth: 0,
              },
              params: [
                {
                  name: "hover",
                  select: {
                    type: "point",
                    on: "mouseover",
                    clear: "mouseout",
                  },
                },
              ],
              encoding: {
                x: {
                  field: "bin_start",
                  type: "quantitative",
                  bin: { binned: true, step: 2 },
                },
                x2: {
                  field: "bin_end",
                  axis: null,
                },
                y: {
                  field: "count",
                  type: "quantitative",
                  axis: null,
                },
                strokeWidth: {
                  condition: {
                    param: "hover",
                    empty: false,
                    value: 0.5,
                  },
                  value: 0,
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
                  field: "bin_start",
                  type: "quantitative",
                  bin: { binned: true, step: 2 },
                  axis: {
                    title: null,
                    labelFontSize: 8.5,
                    labelOpacity: 0.5,
                    labelExpr:
                      "(datum.value >= 10000 || datum.value <= -10000) ? format(datum.value, '.2e') : format(datum.value, '.2~f')",
                    // TODO: Tick count provides a better UI, but it did not work
                    values: [
                      stats?.min,
                      stats?.p25,
                      stats?.median,
                      stats?.p75,
                      stats?.p95,
                      stats?.max,
                    ].filter((value): value is number => value !== undefined),
                  },
                },
                x2: {
                  field: "bin_end",
                },
                y: {
                  aggregate: "max",
                  type: "quantitative",
                  axis: null,
                },
                tooltip: [
                  {
                    field: "bin_range",
                    type: "nominal",
                    title: column,
                  },
                  {
                    field: "count",
                    type: "quantitative",
                    title: "Count",
                    format: ",d",
                  },
                ],
              },
              transform: [
                {
                  calculate: `format(datum.bin_start, '${format}') + ' - ' + format(datum.bin_end, '${format}')`,
                  as: "bin_range",
                },
              ],
            },
          ],
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

const readableTimeFormat = "%-I:%M:%S %p"; // e.g., 1:02:30 AM (no leading zero on hour)

function getPartialTimeTooltip(
  values: ValueCounts,
): Partial<StringFieldDef<string>> {
  if (values.length === 0) {
    return {};
  }

  // Find non-null value
  const value = values.find((v) => v.value !== null)?.value;
  if (!value) {
    return {};
  }

  // If value is a year (2019, 2020, etc), we return empty as it bugs out when we return a time unit
  if (typeof value === "number" && value.toString().length === 4) {
    return {};
  }

  // If value is just time (00:00:00, 01:00:00, etc)
  if (typeof value === "string" && value.length === 8) {
    return {
      type: "temporal",
      timeUnit: "hoursminutesseconds",
      format: readableTimeFormat,
    };
  }

  // If value is a date (2019-01-01, 2020-01-01, etc)
  if (typeof value === "string" && value.length === 10) {
    return {
      type: "temporal",
      timeUnit: "yearmonthdate",
    };
  }

  // If value is a datetime (2019-01-01 00:00:00, 2020-01-01 00:00:00, 2023-05-15T01:00:00 etc)
  if (typeof value === "string" && value.length === 19) {
    const minimumValue = value; // non-null value
    const maximumValue = values[values.length - 1].value;

    try {
      const minimumDate = new Date(minimumValue);
      const maximumDate = new Date(maximumValue as string);
      const timeDifference = maximumDate.getTime() - minimumDate.getTime();

      // If time difference is less than 1 day, we use hoursminutesseconds
      if (timeDifference < 1000 * 60 * 60 * 24) {
        return {
          type: "temporal",
          timeUnit: "hoursminutesseconds",
          format: readableTimeFormat,
        };
      }
    } catch (error) {
      Logger.debug("Error parsing date", error);
    }

    return {
      type: "temporal",
      timeUnit: "yearmonthdatehoursminutes",
    };
  }

  Logger.debug("Unknown time unit", value);

  return {
    type: "temporal",
    timeUnit: "yearmonthdate",
  };
}
