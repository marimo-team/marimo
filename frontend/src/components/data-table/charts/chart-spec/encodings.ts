/* Copyright 2024 Marimo. All rights reserved. */

import type { z } from "zod";
import type { BinSchema, ChartSchemaType } from "../schemas";

import {
  type AggregationFn,
  BIN_AGGREGATION,
  ChartType,
  NONE_AGGREGATION,
  STRING_AGGREGATION_FNS,
  type SelectableDataType,
} from "../types";

import { isFieldSet } from "./spec";
import { COUNT_FIELD, DEFAULT_COLOR_SCHEME } from "../constants";
import type { ColorDef, OffsetDef } from "vega-lite/build/src/channeldef";
import { convertDataTypeToVega } from "./types";
import type { ColorScheme } from "vega";
import type { Aggregate } from "vega-lite/build/src/aggregate";
import type { BinParams } from "vega-lite/build/src/bin";
import type { Scale } from "vega-lite/build/src/scale";

export function getBinEncoding(
  chartType: ChartType,
  selectedDataType: SelectableDataType,
  binValues?: z.infer<typeof BinSchema>,
): boolean | BinParams | undefined {
  if (chartType === ChartType.HEATMAP) {
    if (!binValues?.maxbins) {
      return undefined;
    }
    return { maxbins: binValues?.maxbins };
  }

  if (!binValues?.binned) {
    return undefined;
  }

  // Don't bin non-numeric data
  if (selectedDataType !== "number") {
    return undefined;
  }

  const binParams: BinParams = {};
  if (binValues.step) {
    binParams.step = binValues.step;
  }
  if (binValues.maxbins) {
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
  if (
    chartType === ChartType.PIE ||
    !isFieldSet(formValues.general?.colorByColumn?.field)
  ) {
    return undefined;
  }

  const colorByColumn = formValues.general.colorByColumn;
  if (colorByColumn.field === COUNT_FIELD) {
    return {
      aggregate: "count",
      type: "quantitative",
    };
  }

  const colorBin = formValues.color?.bin;
  const selectedDataType = colorByColumn.selectedDataType || "string";
  const aggregate = formValues.general.colorByColumn.aggregate;

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
): Aggregate | undefined {
  // temporal data types don't support aggregation
  if (selectedDataType === "temporal") {
    return undefined;
  }

  if (
    aggregate === NONE_AGGREGATION ||
    aggregate === BIN_AGGREGATION ||
    !aggregate
  ) {
    return undefined;
  }

  if (selectedDataType === "string") {
    return STRING_AGGREGATION_FNS.includes(aggregate)
      ? (aggregate as Aggregate)
      : undefined;
  }
  return aggregate as Aggregate;
}
