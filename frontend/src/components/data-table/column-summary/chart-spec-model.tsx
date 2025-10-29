/* Copyright 2024 Marimo. All rights reserved. */

import { mint, orange, slate } from "@radix-ui/colors";
import type { TopLevelSpec } from "vega-lite";
import type { StringFieldDef } from "vega-lite/types_unstable/channeldef.js";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { logNever } from "@/utils/assertNever";
import type {
  BinValues,
  ColumnHeaderStats,
  ColumnName,
  FieldTypes,
  ValueCounts,
} from "../types";
import {
  getDataSpecAndSourceName,
  getLegacyBooleanSpec,
  getLegacyNumericSpec,
  getLegacyTemporalSpec,
  getScale,
} from "./legacy-chart-spec";
import { calculateBinStep, getPartialTimeTooltip } from "./utils";

// We rely on vega's built-in binning to determine bar widths.
const MAX_BAR_HEIGHT = 20; // px

// If we are concatenating charts, we need to specify each chart's height and width.
const CONCAT_CHART_HEIGHT = 30;
const CONCAT_CHART_WIDTH = 70;
const CONCAT_NULL_BAR_WIDTH = 5;

const BAR_COLOR = mint.mint11;
const UNHOVERED_BAR_OPACITY = 0.6;
const NULL_BAR_COLOR = orange.orange11;

export class ColumnChartSpecModel<T> {
  private columnStats = new Map<ColumnName, Partial<ColumnHeaderStats>>();
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
    },
  );

  private dataSpec: TopLevelSpec["data"];

  // Legacy data spec for fallback
  private legacyDataSpec: TopLevelSpec["data"];
  private legacySourceName: "data_0" | "source_0";

  private readonly fieldTypes: FieldTypes;
  readonly stats: Record<ColumnName, Partial<ColumnHeaderStats>>;
  readonly binValues: Record<ColumnName, BinValues>;
  readonly valueCounts: Record<ColumnName, ValueCounts>;
  private readonly opts: {
    includeCharts: boolean;
  };

  constructor(
    data: T[] | string,
    fieldTypes: FieldTypes,
    stats: Record<ColumnName, Partial<ColumnHeaderStats>>,
    binValues: Record<ColumnName, BinValues>,
    valueCounts: Record<ColumnName, ValueCounts>,
    opts: {
      includeCharts: boolean;
    },
  ) {
    this.fieldTypes = fieldTypes;
    this.stats = stats;
    this.binValues = binValues;
    this.valueCounts = valueCounts;
    this.opts = opts;

    this.columnBinValues = new Map(Object.entries(binValues));
    this.columnValueCounts = new Map(Object.entries(valueCounts));
    this.columnStats = new Map(Object.entries(stats));

    const { dataSpec, sourceName } = getDataSpecAndSourceName(data);
    this.dataSpec = dataSpec;
    this.legacyDataSpec = dataSpec;
    this.legacySourceName = sourceName;
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

  private createBase(data: TopLevelSpec["data"]): TopLevelFacetedUnitSpec {
    return {
      background: "transparent",
      data,
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
  }

  private getVegaSpec(column: string): TopLevelFacetedUnitSpec | null {
    const binValues = this.columnBinValues.get(column);
    const valueCounts = this.columnValueCounts.get(column);
    const hasValueCounts = valueCounts && valueCounts.length > 0;

    let data = this.dataSpec as TopLevelFacetedUnitSpec["data"];
    const stats = this.columnStats.get(column);

    if (hasValueCounts) {
      data = { values: valueCounts, name: "value_counts" };
    } else {
      // Bin values can be empty if all values are nulls
      if (stats?.nulls) {
        binValues?.push({
          bin_start: null,
          bin_end: null,
          count: stats.nulls as number,
        });
      }
      data = { values: binValues, name: "bin_values" };
    }

    const base = this.createBase(data);
    const type = this.fieldTypes[column];

    // https://github.com/vega/altair/blob/32990a597af7c09586904f40b3f5e6787f752fa5/doc/user_guide/encodings/index.rst#escaping-special-characters-in-column-names
    // escape periods in column names
    column = column.replaceAll(".", "\\.");
    // escape brackets in column names
    column = column.replaceAll("[", "\\[").replaceAll("]", "\\]");
    // escape colons in column names
    column = column.replaceAll(":", "\\:");

    switch (type) {
      case "date":
      case "datetime":
      case "time": {
        if (!binValues) {
          const legacyBase = this.createBase(this.legacyDataSpec);
          const scale = getScale(this.legacySourceName);
          return getLegacyTemporalSpec(column, type, legacyBase, scale);
        }

        const tooltip = getPartialTimeTooltip(binValues || []);
        const singleValue = binValues?.length === 1;

        // Single value charts can be displayed as a full bar
        if (singleValue) {
          return {
            ...base,
            mark: { type: "bar", color: BAR_COLOR },
            encoding: {
              x: {
                field: "bin_start",
                type: "nominal",
                axis: null,
              },
              y: {
                field: "count",
                type: "quantitative",
                axis: null,
              },
              tooltip: [
                {
                  field: "bin_start",
                  type: "temporal",
                  ...tooltip,
                  title: `${column} (start)`,
                },
                {
                  field: "bin_end",
                  type: "temporal",
                  ...tooltip,
                  title: `${column} (end)`,
                },
              ],
            },
          };
        }

        const histogram: TopLevelFacetedUnitSpec = {
          // @ts-expect-error 'layer' property not in TopLevelFacetedUnitSpec
          layer: [
            {
              mark: {
                type: "bar",
                color: BAR_COLOR,
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
                  type: "ordinal",
                  axis: null,
                },
                y: {
                  field: "count",
                  type: "quantitative",
                  axis: null,
                },
                color: {
                  condition: {
                    test: "datum['bin_start'] === null && datum['bin_end'] === null",
                    value: NULL_BAR_COLOR,
                  },
                  value: BAR_COLOR,
                },
                opacity: {
                  condition: [
                    {
                      param: "hover",
                      value: 1,
                    },
                  ],
                  value: UNHOVERED_BAR_OPACITY,
                },
              },
            },

            // Invisible tooltip layer
            {
              mark: {
                type: "bar",
                opacity: 0,
                // Wider bars to cover gaps between bars, prevents flickering when hovering over bars
                width: { band: 1.2 },
              },
              encoding: {
                x: {
                  field: "bin_start",
                  type: "ordinal",
                  axis: null,
                },
                y: {
                  aggregate: "max",
                  type: "quantitative",
                  axis: null,
                },
                tooltip: [
                  {
                    field: "bin_start",
                    type: "temporal",
                    ...tooltip,
                    title: `${column} (start)`,
                  },
                  {
                    field: "bin_end",
                    type: "temporal",
                    ...tooltip,
                    title: `${column} (end)`,
                  },
                  {
                    field: "count",
                    type: "quantitative",
                    title: "Count",
                    format: ",d",
                  },
                ],
              },
            },
          ],
        };

        return {
          ...base,
          ...histogram,
        };
      }
      case "integer":
      case "number": {
        // Create a histogram spec that properly handles null values
        const format = type === "integer" ? ",d" : ".2f";

        if (!binValues) {
          const legacyBase = this.createBase(this.legacyDataSpec);
          return getLegacyNumericSpec(column, format, legacyBase);
        }

        const binStep = calculateBinStep(binValues || []);

        const histogram: TopLevelFacetedUnitSpec = {
          height: CONCAT_CHART_HEIGHT,
          width: CONCAT_CHART_WIDTH,
          // @ts-expect-error 'layer' property not in TopLevelFacetedUnitSpec
          layer: [
            {
              mark: {
                type: "bar",
                color: BAR_COLOR,
              },
              encoding: {
                x: {
                  field: "bin_start",
                  type: "quantitative",
                  bin: { binned: true, step: binStep },
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
                opacity: {
                  condition: [
                    {
                      param: "hover",
                      value: 1,
                    },
                  ],
                  value: UNHOVERED_BAR_OPACITY,
                },
              },
            },

            // Tooltip layer
            {
              mark: {
                type: "bar",
                opacity: 0,
              },
              params: [
                {
                  name: "hover",
                  select: {
                    type: "point",
                    on: "mouseover",
                    clear: "mouseout",
                    nearest: true, // Nearest avoids flickering when hovering over bars, but it's not perfect
                  },
                },
              ],
              encoding: {
                x: {
                  field: "bin_start",
                  type: "quantitative",
                  bin: { binned: true, step: binStep },
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

        const nullBar: TopLevelFacetedUnitSpec = {
          height: CONCAT_CHART_HEIGHT,
          width: CONCAT_NULL_BAR_WIDTH,
          // @ts-expect-error 'layer' property not in TopLevelFacetedUnitSpec
          layer: [
            {
              mark: {
                type: "bar",
                color: NULL_BAR_COLOR,
              },
              encoding: {
                x: {
                  field: "bin_start",
                  type: "nominal",
                  axis: null,
                },
                y: {
                  field: "count",
                  type: "quantitative",
                  axis: null,
                },
              },
            },
            {
              mark: {
                type: "bar",
                opacity: 0,
              },
              encoding: {
                x: {
                  field: "bin_start",
                  type: "nominal",
                  axis: null,
                },
                y: {
                  aggregate: "max",
                  type: "quantitative",
                  axis: null,
                },
                tooltip: [
                  {
                    field: "count",
                    type: "quantitative",
                    title: "nulls",
                    format: ",d",
                  },
                ],
              },
            },
          ],
          transform: [
            {
              filter:
                "datum['bin_start'] === null && datum['bin_end'] === null",
            },
          ],
        };

        let chart: TopLevelFacetedUnitSpec = histogram;
        let numericBase = base;

        if (stats?.nulls) {
          numericBase = {
            ...base,
            config: {
              ...base.config,
              concat: {
                spacing: 0,
              },
            },
            // So that the null bar and the histogram share the same y-axis
            resolve: {
              scale: {
                y: "shared",
              },
            },
          };
          chart = {
            // @ts-expect-error 'hconcat' property not in TopLevelFacetedUnitSpec
            hconcat: [nullBar, histogram],
          };
        }

        return {
          ...numericBase, // Assuming base contains shared configurations
          ...chart,
        };
      }
      case "boolean": {
        if (!stats?.true || !stats?.false) {
          return getLegacyBooleanSpec(column, base, MAX_BAR_HEIGHT);
        }

        const BAR_HEIGHT = stats?.nulls ? 11 : MAX_BAR_HEIGHT;

        const values = [
          { value: "true", count: stats.true },
          { value: "false", count: stats.false },
        ];
        if (stats?.nulls) {
          values.push({ value: "null", count: stats.nulls });
        }

        let countTooltip: StringFieldDef<string> = {
          field: "count",
          type: "quantitative",
          format: ",d",
        };
        let transform: TopLevelFacetedUnitSpec["transform"] = [];

        const total =
          Number(stats.total) ||
          Number(stats.true) + Number(stats.false) + Number(stats.nulls);

        if (!Number.isNaN(total)) {
          countTooltip = {
            field: "count_with_percent",
            type: "nominal",
            title: "Count",
          };
          transform = [
            {
              calculate: `format(datum.count, ',d') + ' (' + format(datum.count / ${total} * 100, '.1f') + '%)'`,
              as: "count_with_percent",
            },
          ];
        }

        return {
          ...base,
          data: {
            values,
            name: "boolean_values",
          },
          mark: {
            type: "bar",
            color: BAR_COLOR,
          },
          encoding: {
            y: {
              field: "value",
              type: "nominal",
              sort: ["true", "false", "null"],
              scale: stats?.nulls ? { paddingInner: 1 } : undefined,
              axis: {
                labelExpr:
                  "datum.label === 'true' || datum.label === 'True'  ? 'True' : datum.label === 'false' || datum.label === 'False' ? 'False' : 'Null'",
                tickWidth: 0,
                title: null,
                labelColor: slate.slate9,
              },
            },
            x: {
              field: "count",
              type: "quantitative",
              axis: null,
              scale: { type: "linear" },
            },
            color: {
              field: "value",
              type: "nominal",
              scale: {
                domain: ["true", "false", "null"],
                range: [BAR_COLOR, BAR_COLOR, NULL_BAR_COLOR],
              },
              legend: null,
            },
            tooltip: [
              { field: "value", type: "nominal", title: column },
              countTooltip,
            ],
          },
          transform,
          layer: [
            {
              mark: {
                type: "bar",
                color: BAR_COLOR,
                height: BAR_HEIGHT,
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
                  field: "count",
                  type: "quantitative",
                  format: ",d",
                },
              },
            },
          ],
        } as TopLevelFacetedUnitSpec; // "layer" not in TopLevelFacetedUnitSpec
      }
      case "string": {
        if (!hasValueCounts) {
          return null;
        }

        const total =
          Number(stats?.total) ||
          valueCounts.reduce((acc, curr) => acc + curr.count, 0);

        const xStartField = "xStart";
        const xEndField = "xEnd";
        const xMidField = "xMid";
        const yField = "value";

        // Calculate xStart and xEnd for each value count
        const newValueCounts: {
          count: number;
          value: string;
          xStart: number;
          xEnd: number;
          xMid: number;
          proportion: number;
        }[] = [];
        let xStart = 0;
        for (const valueCount of valueCounts) {
          const xEnd = xStart + valueCount.count;
          const xMid = (xStart + xEnd) / 2;
          const proportion = (xEnd - xStart) / total;

          newValueCounts.push({
            count: valueCount.count,
            value: valueCount.value,
            xStart,
            xEnd,
            xMid,
            proportion,
          });
          xStart = xEnd;
        }

        // Add a transform to calculate the percentage for each value
        const percentField = "percent";
        const transforms: TopLevelFacetedUnitSpec["transform"] = [
          {
            calculate: total ? `datum.count / ${total}` : "0",
            as: percentField,
          },
        ];

        // Pill-like bar
        const barChart: Omit<TopLevelFacetedUnitSpec, "data"> = {
          mark: {
            type: "bar",
            // cornerRadiusEnd: 10,
            // cornerRadius: 10,
          },
          params: [
            {
              name: "hover_bar",
              select: {
                type: "point",
                on: "mouseover",
                clear: "mouseout",
              },
            },
          ],
          encoding: {
            x: {
              field: xStartField,
              type: "quantitative",
              axis: null,
            },
            x2: {
              field: xEndField,
              type: "quantitative",
            },
            color: {
              condition: {
                test: `datum.${yField} == "None" || datum.${yField} == "null"`,
                value: NULL_BAR_COLOR,
              },
              value: BAR_COLOR,
            },
            opacity: {
              condition: [
                {
                  param: "hover_bar",
                  value: 1,
                },
              ],
              value: UNHOVERED_BAR_OPACITY,
            },
            tooltip: [
              {
                field: yField,
                type: "nominal",
                title: column,
              },
              {
                field: "count_with_percent",
                type: "nominal",
                title: "Count",
              },
            ],
          },
          transform: [
            // Display count and percent together
            {
              calculate: `format(datum.count, ',d') + ' (' + format(datum.count / ${total} * 100, '.1f') + '%)'`,
              as: "count_with_percent",
            },
          ],
        };

        // Text layer with clipping based on bar width
        const textChart: Omit<TopLevelFacetedUnitSpec, "data"> = {
          mark: {
            type: "text",
            color: "white",
            fontSize: 8.5,
            ellipsis: " ", // Don't add ... after clipping
            clip: true,
          },
          encoding: {
            x: {
              field: xMidField,
              type: "quantitative",
              axis: null,
            },
            text: {
              field: "clipped_text",
            },
          },
          transform: [
            {
              calculate: `datum.proportion > 0.5 ? slice(datum.${yField}, 0, 8) : datum.proportion > 0.2 ? slice(datum.${yField}, 0, 3) : datum.proportion > 0.1 ? slice(datum.${yField}, 0, 1) : ''`,
              as: "clipped_text",
            },
          ],
        };

        return {
          ...base,
          data: {
            values: newValueCounts,
            name: "value_counts",
          },
          // @ts-expect-error 'layer' property not in TopLevelFacetedUnitSpec
          layer: [barChart, textChart],
          transform: transforms,
        };
      }
      case "unknown":
        return null;
      default:
        logNever(type);
        return null;
    }
  }
}
