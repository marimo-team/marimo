/* Copyright 2024 Marimo. All rights reserved. */
import type { TopLevelSpec } from "vega-lite";
import type { ResolvedTheme } from "@/theme/useTheme";
import type {
  BinSchema,
  ChartSchema,
  AxisSchema,
  RowFacet,
  ColumnFacet,
} from "../schemas";
import { ChartType } from "../types";
import type { z } from "zod";
import type {
  ColorDef,
  Field,
  PolarDef,
  PositionDef,
} from "vega-lite/build/src/channeldef";
import type { ExprRef, SignalRef } from "vega";
import type { TypedString } from "@/utils/typed";
import { COUNT_FIELD, EMPTY_VALUE } from "../constants";
import type { FacetFieldDef } from "vega-lite/build/src/spec/facet";
import {
  getBinEncoding,
  getColorEncoding,
  getColorInScale,
  getOffsetEncoding,
  getAggregate,
} from "./encodings";
import { convertChartTypeToMark, convertDataTypeToVega } from "./types";
import { getTooltips } from "./tooltips";

/**
 * Convert marimo chart configuration to Vega-Lite specification.
 */

export type ErrorMessage = TypedString<"ErrorMessage">;

export function createVegaSpec(
  chartType: ChartType,
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
  // eslint-disable-next-line @typescript-eslint/no-redundant-type-constituents
): TopLevelSpec | ErrorMessage {
  const {
    xColumn,
    yColumn,
    colorByColumn,
    horizontal,
    stacking,
    title,
    facet,
  } = formValues.general;

  if (chartType === ChartType.PIE) {
    return getPieChartSpec(data, formValues, theme, width, height);
  }

  // Validate required fields
  if (!isFieldSet(xColumn?.field)) {
    return "X-axis column is required" as ErrorMessage;
  }
  if (!isFieldSet(yColumn?.field)) {
    return "Y-axis column is required" as ErrorMessage;
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

  const yEncoding = getAxisEncoding(
    yColumn,
    formValues.yAxis?.bin,
    getFieldLabel(formValues.yAxis?.label),
    colorByColumn?.field && !horizontal ? stacking : undefined,
    chartType,
  );

  const rowFacet = facet?.row.field ? getFacetEncoding(facet.row) : undefined;
  const columnFacet = facet?.column.field
    ? getFacetEncoding(facet.column)
    : undefined;

  // Create the final spec
  return {
    ...getBaseSpec(data, formValues, theme, width, height, title),
    mark: { type: convertChartTypeToMark(chartType) },
    encoding: {
      [xEncodingKey]: horizontal ? yEncoding : xEncoding,
      [yEncodingKey]: horizontal ? xEncoding : yEncoding,
      xOffset: getOffsetEncoding(chartType, formValues),
      ...getColorEncoding(chartType, formValues),
      tooltip: getTooltips(formValues),
      row: rowFacet,
      column: columnFacet,
    },
    resolve: {
      axis: {
        x: facet?.column.linkXAxis ? "shared" : "independent",
        y: facet?.row.linkYAxis ? "shared" : "independent",
      },
    },
  };
}

export function getAxisEncoding(
  column: NonNullable<z.infer<typeof AxisSchema>>,
  binValues: z.infer<typeof BinSchema> | undefined,
  label: string | undefined,
  stack: boolean | undefined,
  chartType: ChartType,
): PositionDef<string> {
  const selectedDataType = column.selectedDataType || "string";

  if (column.field === COUNT_FIELD) {
    return {
      aggregate: "count",
      type: "quantitative",
      bin: getBinEncoding(selectedDataType, binValues, chartType),
      title: label === COUNT_FIELD ? undefined : label,
      stack: stack,
    };
  }

  return {
    field: column.field,
    type: convertDataTypeToVega(column.selectedDataType || "unknown"),
    bin: getBinEncoding(selectedDataType, binValues, chartType),
    title: label,
    stack: stack,
    aggregate: getAggregate(column.aggregate, selectedDataType),
    timeUnit: getTimeUnit(column),
  };
}

export function getFacetEncoding(
  facet: z.infer<typeof RowFacet> | z.infer<typeof ColumnFacet>,
): FacetFieldDef<Field, ExprRef | SignalRef> {
  let binValues = undefined;
  // Only allow binning for number data types
  if (facet.binned && facet.selectedDataType === "number") {
    binValues = {
      maxbins: facet.maxbins,
    };
  }

  return {
    field: facet.field,
    sort: facet.sort,
    timeUnit: getTimeUnit(facet),
    type: convertDataTypeToVega(facet.selectedDataType || "unknown"),
    bin: binValues,
  };
}

function getPieChartSpec(
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
) {
  const { yColumn, colorByColumn, title } = formValues.general;

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
    ...getBaseSpec(data, formValues, theme, width, height, title),
    mark: {
      type: convertChartTypeToMark(ChartType.PIE),
      innerRadius: formValues.style?.innerRadius,
    },
    encoding: {
      theta: thetaEncoding,
      color: colorEncoding,
      tooltip: getTooltips(formValues),
    },
  };
}

function getBaseSpec(
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
  title?: string,
) {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: theme === "dark" ? "dark" : "white",
    title: title,
    data: { values: data },
    height: formValues.yAxis?.height ?? height,
    width: formValues.xAxis?.width ?? width,
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
    return column.timeUnit;
  }
  return undefined;
}
