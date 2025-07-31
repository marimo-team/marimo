/* Copyright 2024 Marimo. All rights reserved. */

import type { Aggregate } from "vega-lite/build/src/aggregate";
import type { BinParams } from "vega-lite/build/src/bin";
import type { ColorDef, OffsetDef } from "vega-lite/build/src/channeldef";
import type { Scale } from "vega-lite/build/src/scale";
import type { z } from "zod";
import { COUNT_FIELD, DEFAULT_COLOR_SCHEME } from "../constants";
import type { AxisSchema, BinSchema, ChartSchemaType } from "../schemas";
import {
  type AggregationFn,
  BIN_AGGREGATION,
  ChartType,
  type ColorScheme,
  NONE_VALUE,
  type SelectableDataType,
  STRING_AGGREGATION_FNS,
  type ValidAggregationFn,
} from "../types";
import { isFieldSet } from "./spec";
import { convertDataTypeToVega } from "./types";

export function getBinEncoding(
  chartType: ChartType,
  selectedDataType: SelectableDataType,
  binValues?: z.infer<typeof BinSchema>,
  defaultBinValues?: z.infer<typeof BinSchema>,
): boolean | BinParams | undefined {
  if (chartType === ChartType.HEATMAP) {
    if (!binValues?.maxbins) {
      return undefined;
    }
    return { maxbins: binValues?.maxbins };
  }

  // Don't bin non-numeric data
  if (selectedDataType !== "number") {
    return undefined;
  }

  if (!binValues?.binned) {
    return defaultBinValues;
  }

  const binParams: BinParams = {};
  if (binValues.step !== undefined) {
    binParams.step = binValues.step;
  }
  if (binValues.maxbins !== undefined) {
    binParams.maxbins = binValues.maxbins;
  }

  if (Object.keys(binParams).length === 0) {
    return true;
  }

  return binParams;
}

export function getColorInScale(
  formValues: ChartSchemaType,
): Scale | undefined {
  const colorRange = formValues.color?.range;
  if (colorRange?.length) {
    return { range: colorRange };
  }

  const scheme = formValues.color?.scheme;
  if (scheme && scheme !== DEFAULT_COLOR_SCHEME) {
    return { scheme: scheme as ColorScheme };
  }
}

export function getColorEncoding(
  chartType: ChartType,
  formValues: ChartSchemaType,
): ColorDef<string> | undefined {
  if (chartType === ChartType.PIE) {
    return undefined;
  }

  // Choose colorByColumn if it's set, otherwise use color.field
  // Color.field can be used to set colour scheme of the charts
  let colorByColumn: z.infer<typeof AxisSchema> | undefined;
  if (isFieldSet(formValues.general?.colorByColumn?.field)) {
    colorByColumn = formValues.general?.colorByColumn;
  } else if (isFieldSet(formValues.color?.field)) {
    const field = formValues.color?.field;
    switch (field) {
      case "X":
        colorByColumn = formValues.general?.xColumn;
        break;
      case "Y":
        colorByColumn = formValues.general?.yColumn;
        break;
      case "Color":
        colorByColumn = formValues.general?.colorByColumn;
        break;
      default:
        return undefined;
    }
  } else {
    return undefined;
  }

  if (
    !colorByColumn ||
    !isFieldSet(colorByColumn.field) ||
    colorByColumn.field === NONE_VALUE
  ) {
    return undefined;
  }

  if (colorByColumn.field === COUNT_FIELD) {
    return {
      aggregate: "count",
      type: "quantitative",
    };
  }

  const colorBin = formValues.color?.bin;
  const selectedDataType = colorByColumn.selectedDataType || "string";
  const aggregate = colorByColumn?.aggregate;

  return {
    field: colorByColumn.field,
    type: convertDataTypeToVega(selectedDataType),
    scale: getColorInScale(formValues),
    aggregate: getAggregate(aggregate, selectedDataType),
    bin: getBinEncoding(chartType, selectedDataType, colorBin),
  };
}

export function getOffsetEncoding(
  chartType: ChartType,
  formValues: ChartSchemaType,
): OffsetDef<string> | undefined {
  // Offset only applies to bar charts, to unstack them
  if (
    formValues.general?.stacking ||
    !isFieldSet(formValues.general?.colorByColumn?.field) ||
    chartType !== ChartType.BAR
  ) {
    return undefined;
  }
  return { field: formValues.general?.colorByColumn?.field };
}

export function getAggregate(
  aggregate: AggregationFn | undefined,
  selectedDataType: SelectableDataType,
  defaultAggregate?: ValidAggregationFn,
): Aggregate | undefined {
  // temporal data types don't support aggregation
  if (selectedDataType === "temporal") {
    return undefined;
  }

  if (aggregate === NONE_VALUE || aggregate === BIN_AGGREGATION) {
    return undefined;
  }

  if (!aggregate) {
    return defaultAggregate ? (defaultAggregate as Aggregate) : undefined;
  }

  if (selectedDataType === "string") {
    return STRING_AGGREGATION_FNS.includes(aggregate)
      ? (aggregate as Aggregate)
      : undefined;
  }
  return aggregate as Aggregate;
}
