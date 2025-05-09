/* Copyright 2024 Marimo. All rights reserved. */

import type { z } from "zod";
import type { BinSchema, ChartSchema } from "../schemas";

import { ChartType, NONE_AGGREGATION } from "../types";

import { DEFAULT_BIN_VALUE } from "../schemas";
import { isFieldSet } from "./spec";
import { COUNT_FIELD, DEFAULT_COLOR_SCHEME } from "../constants";
import type { ColorDef, OffsetDef } from "vega-lite/build/src/channeldef";
import { convertDataTypeToVega } from "./types";
import type { ColorScheme } from "vega";

export function getBinEncoding(
  binValues?: z.infer<typeof BinSchema>,
  chartType?: ChartType,
) {
  if (chartType === ChartType.HEATMAP) {
    return { maxbins: binValues?.maxbins };
  }

  if (!binValues?.binned) {
    return undefined;
  }

  return binValues.step === DEFAULT_BIN_VALUE
    ? true
    : { binned: true, step: binValues.step };
}

export function getColorInScale(formValues: z.infer<typeof ChartSchema>) {
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
  formValues: z.infer<typeof ChartSchema>,
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

  const aggregate = formValues.general.colorByColumn.aggregate;

  return {
    color: {
      field: colorByColumn.field,
      type: convertDataTypeToVega(colorByColumn.selectedDataType || "unknown"),
      scale: getColorInScale(formValues),
      aggregate: aggregate === NONE_AGGREGATION ? undefined : aggregate,
    },
  };
}

export function getOffsetEncoding(
  chartType: ChartType,
  formValues: z.infer<typeof ChartSchema>,
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
