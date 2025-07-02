/* Copyright 2024 Marimo. All rights reserved. */

import type { TopLevelSpec } from "vega-lite";
import type {
  ColorDef,
  Field,
  PolarDef,
  PositionDef,
} from "vega-lite/build/src/channeldef";
import type { Encoding } from "vega-lite/build/src/encoding";
import type { Resolve } from "vega-lite/build/src/resolve";
import type { FacetFieldDef } from "vega-lite/build/src/spec/facet";
import type { z } from "zod";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { TypedString } from "@/utils/typed";
import {
  COUNT_FIELD,
  DEFAULT_AGGREGATION,
  DEFAULT_MAX_BINS_FACET,
  DEFAULT_TIME_UNIT,
  EMPTY_VALUE,
} from "../constants";
import type {
  AxisSchema,
  BinSchema,
  ChartSchemaType,
  ColumnFacet,
  RowFacet,
} from "../schemas";
import { ChartType, type ValidAggregationFn } from "../types";
import {
  getAggregate,
  getBinEncoding,
  getColorEncoding,
  getColorInScale,
  getOffsetEncoding,
} from "./encodings";
import { getTooltips } from "./tooltips";
import {
  type BaseSpec,
  convertChartTypeToMark,
  convertDataTypeToVega,
} from "./types";

/**
 * Convert marimo chart configuration to Vega-Lite specification.
 */

export type ErrorMessage = TypedString<"ErrorMessage">;
export const X_AXIS_REQUIRED = "X-axis column is required" as ErrorMessage;
export const Y_AXIS_REQUIRED = "Y-axis column is required" as ErrorMessage;

export function createSpecWithoutData(
  chartType: ChartType,
  formValues: ChartSchemaType,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
): TopLevelSpec | ErrorMessage {
  const {
    xColumn,
    yColumn,
    colorByColumn,
    horizontal,
    stacking,
    title,
    facet,
  } = formValues.general ?? {};

  if (chartType === ChartType.PIE) {
    return getPieChartSpec(formValues, theme, width, height);
  }

  // Validate required fields
  if (!isFieldSet(xColumn?.field)) {
    return X_AXIS_REQUIRED;
  }
  if (!isFieldSet(yColumn?.field)) {
    return Y_AXIS_REQUIRED;
  }

  // Determine encoding keys based on chart type
  const xEncodingKey = "x";
  const yEncodingKey = "y";

  // Create encodings
  const xEncoding = getAxisEncoding(
    xColumn,
    formValues.xAxis?.bin,
    getFieldLabel(formValues.xAxis?.label),
    colorByColumn?.field && horizontal ? stacking : undefined,
    chartType,
  );

  let defaultYAggregation: ValidAggregationFn = DEFAULT_AGGREGATION;
  if (yColumn?.selectedDataType === "string") {
    defaultYAggregation = "count";
  }

  const yEncoding = getAxisEncoding(
    yColumn,
    formValues.yAxis?.bin,
    getFieldLabel(formValues.yAxis?.label),
    colorByColumn?.field && !horizontal ? stacking : undefined,
    chartType,
    defaultYAggregation,
  );

  const rowFacet = facet?.row.field
    ? getFacetEncoding(facet.row, chartType)
    : undefined;
  const columnFacet = facet?.column.field
    ? getFacetEncoding(facet.column, chartType)
    : undefined;

  const colorByEncoding = getColorEncoding(chartType, formValues);
  const baseSpec = getBaseSpec(
    chartType,
    formValues,
    theme,
    width,
    height,
    title,
  );
  const baseEncoding: Encoding<Field> = {
    [xEncodingKey]: horizontal ? yEncoding : xEncoding,
    [yEncodingKey]: horizontal ? xEncoding : yEncoding,
    xOffset: getOffsetEncoding(chartType, formValues),
    color: colorByEncoding,
    tooltip: getTooltips({
      formValues,
      xEncoding,
      yEncoding,
      colorByEncoding,
    }),
    ...(rowFacet && { row: rowFacet }),
    ...(columnFacet && { column: columnFacet }),
  };
  const resolve = getResolve(facet?.column, facet?.row);

  // Create the final spec for other chart types
  return {
    ...baseSpec,
    mark: { type: convertChartTypeToMark(chartType) },
    encoding: baseEncoding,
    ...resolve,
  };
}

export function augmentSpecWithData(
  spec: TopLevelSpec,
  data: object[],
): TopLevelSpec {
  return {
    ...spec,
    data: { values: data },
  };
}

export function getAxisEncoding(
  column: NonNullable<z.infer<typeof AxisSchema>>,
  binValues: z.infer<typeof BinSchema> | undefined,
  label: string | undefined,
  stack: boolean | undefined,
  chartType: ChartType,
  defaultAggregate?: ValidAggregationFn,
): PositionDef<string> {
  const selectedDataType = column.selectedDataType || "string";

  if (column.field === COUNT_FIELD) {
    return {
      aggregate: "count",
      type: "quantitative",
      bin: getBinEncoding(chartType, selectedDataType, binValues),
      title: label === COUNT_FIELD ? undefined : label,
      stack: stack,
    };
  }

  return {
    field: column.field,
    type: convertDataTypeToVega(column.selectedDataType || "unknown"),
    bin: getBinEncoding(chartType, selectedDataType, binValues),
    title: label,
    stack: stack,
    aggregate: getAggregate(
      column.aggregate,
      selectedDataType,
      defaultAggregate,
    ),
    sort: column.sort,
    timeUnit: getTimeUnit(column),
  };
}

export function getFacetEncoding(
  facet: z.infer<typeof RowFacet> | z.infer<typeof ColumnFacet>,
  chartType: ChartType,
): FacetFieldDef<Field> {
  const defaultBinValues = {
    maxbins: DEFAULT_MAX_BINS_FACET,
  };
  const binValues = getBinEncoding(
    chartType,
    facet.selectedDataType || "string",
    {
      maxbins: facet.maxbins,
      binned: facet.binned,
    },
    defaultBinValues,
  );

  return {
    field: facet.field,
    sort: facet.sort,
    timeUnit: getFacetTimeUnit(facet),
    type: convertDataTypeToVega(facet.selectedDataType || "unknown"),
    bin: binValues,
  };
}

function getPieChartSpec(
  formValues: ChartSchemaType,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
): TopLevelSpec | ErrorMessage {
  const { yColumn, colorByColumn, title } = formValues.general ?? {};

  if (!isFieldSet(colorByColumn?.field)) {
    return "Color by column is required" as ErrorMessage;
  }

  if (!isFieldSet(yColumn?.field)) {
    return "Size by column is required" as ErrorMessage;
  }

  const thetaEncoding: PolarDef<string> = getAxisEncoding(
    yColumn,
    formValues.xAxis?.bin,
    getFieldLabel(formValues.xAxis?.label),
    undefined,
    ChartType.PIE,
  );

  const colorEncoding: ColorDef<string> = {
    field: colorByColumn.field,
    type: convertDataTypeToVega(colorByColumn.selectedDataType || "unknown"),
    scale: getColorInScale(formValues),
    title: getFieldLabel(formValues.yAxis?.label),
  };

  return {
    ...getBaseSpec(ChartType.PIE, formValues, theme, width, height, title),
    mark: {
      type: convertChartTypeToMark(ChartType.PIE),
      innerRadius: formValues.style?.innerRadius,
    },
    encoding: {
      theta: thetaEncoding,
      color: colorEncoding,
      tooltip: getTooltips({
        formValues,
        xEncoding: thetaEncoding,
        yEncoding: thetaEncoding,
        colorByEncoding: colorEncoding,
      }),
    },
  };
}

function getBaseSpec(
  chartType: ChartType,
  formValues: ChartSchemaType,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
  title?: string,
): BaseSpec {
  let gridLines = formValues.style?.gridLines ?? false;
  // Scatter charts have grid lines by default
  if (chartType === ChartType.SCATTER) {
    gridLines = true;
  }

  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: theme === "dark" ? "dark" : "white",
    title: title,
    data: { values: [] },
    height: formValues.yAxis?.height ?? height,
    width: formValues.xAxis?.width ?? width,
    config: {
      axis: {
        grid: gridLines,
      },
    },
  };
}

export function isFieldSet(field: string | undefined): field is string {
  return field !== undefined && field.trim() !== EMPTY_VALUE;
}

// Returns undefined if the label is empty, as Vega-Lite will use the proper name
function getFieldLabel(label?: string): string | undefined {
  const trimmedLabel = label?.trim();
  return trimmedLabel === EMPTY_VALUE ? undefined : trimmedLabel;
}

function getTimeUnit(column: z.infer<typeof AxisSchema>) {
  if (column.selectedDataType === "temporal") {
    return column.timeUnit ?? DEFAULT_TIME_UNIT;
  }
  return undefined;
}

function getFacetTimeUnit(
  facet: z.infer<typeof RowFacet> | z.infer<typeof ColumnFacet>,
) {
  if (facet.selectedDataType === "temporal") {
    return facet.timeUnit ?? DEFAULT_TIME_UNIT;
  }
  return undefined;
}

function getResolve(
  columnFacet?: z.infer<typeof ColumnFacet>,
  rowFacet?: z.infer<typeof RowFacet>,
): { resolve: Resolve } | undefined {
  const resolveAxis: Resolve["axis"] = {};

  if (columnFacet?.linkXAxis === false) {
    resolveAxis.x = "independent";
  }

  if (rowFacet?.linkYAxis === false) {
    resolveAxis.y = "independent";
  }

  // If no independent axes, return undefined (shared)
  return Object.keys(resolveAxis).length > 0
    ? { resolve: { axis: resolveAxis } }
    : undefined;
}
