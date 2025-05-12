/* Copyright 2024 Marimo. All rights reserved. */

import type { z } from "zod";
import type { BinSchema, ChartSchemaType } from "../schemas";

import { ChartType, NONE_AGGREGATION, type SelectableDataType } from "../types";

import { DEFAULT_BIN_SIZE } from "../constants";
import { isFieldSet } from "./spec";
import { COUNT_FIELD, DEFAULT_COLOR_SCHEME } from "../constants";
import type { ColorDef, OffsetDef } from "vega-lite/build/src/channeldef";
import { convertDataTypeToVega } from "./types";
import type { ColorScheme } from "vega";

export function getBinEncoding(
  selectedDataType: SelectableDataType,
  binValues?: z.infer<typeof BinSchema>,
  chartType?: ChartType,
) {
  if (chartType === ChartType.HEATMAP) {
    return { maxbins: binValues?.maxbins };
  }

  if (!binValues?.binned) {
    return undefined;
  }

  // Don't bin non-numeric data
  if (selectedDataType !== "number") {
    return undefined;
  }

  const binstep =
    binValues.step === DEFAULT_BIN_SIZE ? undefined : binValues.step;
  const binmaxbins =
    binValues.maxbins === DEFAULT_BIN_SIZE ? undefined : binValues.maxbins;

  return { bin: true, step: binstep, maxbins: binmaxbins };
}

export function getColorInScale(formValues: ChartSchemaType) {
  const colorRange = formValues.color?.range;
  if (colorRange?.length) {
    return { range: colorRange };
  }

  const scheme = formValues.color?.scheme;
  return scheme === DEFAULT_COLOR_SCHEME
    ? undefined
    : { scheme: scheme as ColorScheme };
}

export function getColorEncoding(
  chartType: ChartType,
  formValues: ChartSchemaType,
): { color?: ColorDef<string> } | undefined {
  if (
    chartType === ChartType.PIE ||
    !isFieldSet(formValues.general.colorByColumn?.field)
  ) {
    return undefined;
  }

  const colorByColumn = formValues.general.colorByColumn;
  if (colorByColumn.field === COUNT_FIELD) {
    return {
      color: {
        aggregate: "count",
        type: "quantitative",
      },
    };
  }

  const colorBin = formValues.color?.bin;
  const selectedDataType = colorByColumn.selectedDataType || "string";
  const aggregate = formValues.general.colorByColumn.aggregate;

  return {
    color: {
      field: colorByColumn.field,
      type: convertDataTypeToVega(selectedDataType),
      scale: getColorInScale(formValues),
      aggregate: aggregate === NONE_AGGREGATION ? undefined : aggregate,
      bin: getBinEncoding(selectedDataType, colorBin, chartType),
    },
  };
}

export function getOffsetEncoding(
  chartType: ChartType,
  formValues: ChartSchemaType,
): OffsetDef<string> | undefined {
  // Offset only applies to bar charts, to unstack them
  if (
    formValues.general.stacking ||
    !isFieldSet(formValues.general.colorByColumn?.field) ||
    chartType !== ChartType.BAR
  ) {
    return undefined;
  }
  return { field: formValues.general.colorByColumn?.field };
}
