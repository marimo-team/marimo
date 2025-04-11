/* Copyright 2024 Marimo. All rights reserved. */

import type { TopLevelSpec } from "vega-lite";
import { ChartType } from "./storage";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { DataType } from "@/core/kernel/messages";
import {
  type BinSchema,
  DEFAULT_AGGREGATION,
  DEFAULT_BIN_VALUE,
  NONE_GROUP_BY,
  type ChartSchema,
  DEFAULT_COLOR_SCHEME,
} from "./chart-schemas";
import type { z } from "zod";
import type { Mark } from "@/plugins/impl/vega/types";
import { logNever } from "@/utils/assertNever";
import type { Type } from "vega-lite/build/src/type";
import type {
  ColorDef,
  OffsetDef,
  PolarDef,
  PositionDef,
  StringFieldDef,
} from "vega-lite/build/src/channeldef";
import type { ColorScheme } from "vega";

export function createVegaSpec(
  chartType: ChartType,
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
): TopLevelSpec | null {
  let xAxisLabel = formValues.general.xColumn?.field;
  let yAxisLabel = formValues.general.yColumn?.field;

  if (
    formValues.general.yColumn?.agg &&
    formValues.general.yColumn.agg !== DEFAULT_AGGREGATION
  ) {
    yAxisLabel = `${formValues.general.yColumn.agg.toUpperCase()}(${yAxisLabel})`;
  }

  if (formValues.xAxis?.label && formValues.xAxis.label.trim() !== "") {
    xAxisLabel = formValues.xAxis.label;
  }

  if (formValues.yAxis?.label && formValues.yAxis.label.trim() !== "") {
    yAxisLabel = formValues.yAxis.label;
  }

  const xEncodingKey = chartType === ChartType.PIE ? "theta" : "x";
  const yEncodingKey = chartType === ChartType.PIE ? "color" : "y";

  const groupByFieldExists =
    formValues.general.groupByColumn?.field !== NONE_GROUP_BY;

  const shouldApplyStackingToX =
    groupByFieldExists && formValues.general.horizontal;
  const shouldApplyStackingToY =
    groupByFieldExists && !formValues.general.horizontal;

  const xEncoding: PositionDef<string> | PolarDef<string> = {
    field: formValues.general.xColumn?.field,
    type: convertDataTypeToVegaType(
      formValues.general.xColumn?.type ?? "unknown",
    ),
    bin: getBin(formValues.xAxis?.bin),
    title: xAxisLabel,
    stack: shouldApplyStackingToX ? formValues.general.stacking : undefined,
  };

  const colorInScale = getColorInScale(formValues);

  const yEncoding: PositionDef<string> | PolarDef<string> = {
    field: formValues.general.yColumn?.field,
    type: convertDataTypeToVegaType(
      formValues.general.yColumn?.type ?? "unknown",
    ),
    bin: getBin(formValues.yAxis?.bin),
    title: yAxisLabel,
    // If color encoding is used as y, we can define the scheme here
    scale:
      colorInScale && yEncodingKey === "color"
        ? { ...colorInScale }
        : undefined,
    stack: shouldApplyStackingToY ? formValues.general.stacking : undefined,
  };

  const schema: TopLevelSpec = {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: theme === "dark" ? "dark" : "white",
    title: formValues.general.title,
    data: {
      values: data,
    },
    height: height,
    width: width,
    mark: {
      type: convertChartTypeToMark(chartType),
    },
    encoding: {
      [xEncodingKey]: formValues.general.horizontal ? yEncoding : xEncoding,
      [yEncodingKey]: formValues.general.horizontal ? xEncoding : yEncoding,
      xOffset: getOffset(chartType, formValues),
      ...getColor(chartType, formValues),
      tooltip: getTooltips(formValues),
    },
  };
  return schema;
}

// color can be used for grouping
// it can also conflict with the color (y) encoding for pie charts, so we return undefined
function getColor(
  chartType: ChartType,
  formValues: z.infer<typeof ChartSchema>,
) {
  if (
    chartType === ChartType.PIE ||
    formValues.general.groupByColumn?.field === NONE_GROUP_BY
  ) {
    return undefined;
  }

  const colorDef: ColorDef<string> = {
    field: formValues.general.groupByColumn?.field,
    type: convertDataTypeToVegaType(
      formValues.general.groupByColumn?.type ?? "unknown",
    ),
    scale: {
      ...getColorInScale(formValues),
    },
  };

  return {
    color: colorDef,
  };
}

function getColorInScale(formValues: z.infer<typeof ChartSchema>) {
  const colorRange = formValues.color?.range;
  if (colorRange && colorRange.length > 0) {
    return {
      range: colorRange,
    };
  }

  const scheme = formValues.color?.scheme;
  if (scheme === DEFAULT_COLOR_SCHEME) {
    return undefined;
  }
  return {
    scheme: scheme as ColorScheme,
  };
}

function getOffset(
  chartType: ChartType,
  formValues: z.infer<typeof ChartSchema>,
): OffsetDef<string> | undefined {
  if (
    formValues.general.stacking ||
    formValues.general.groupByColumn?.field === NONE_GROUP_BY ||
    chartType === ChartType.PIE
  ) {
    return undefined;
  }
  return {
    field:
      formValues.general.groupByColumn?.field === NONE_GROUP_BY
        ? undefined
        : formValues.general.groupByColumn?.field,
  };
}

function getBin(binValues?: z.infer<typeof BinSchema>) {
  if (binValues?.binned) {
    if (binValues.step === DEFAULT_BIN_VALUE) {
      return true;
    }

    return {
      binned: true,
      step: binValues.step,
    };
  }
}

function getTooltips(formValues: z.infer<typeof ChartSchema>) {
  return formValues.general.tooltips?.map(
    (tooltip): StringFieldDef<string> => ({
      field: tooltip.field,
      aggregate: (() => {
        if (tooltip.field !== formValues.general.yColumn?.field) {
          return undefined;
        }
        return formValues.general.yColumn?.agg === DEFAULT_AGGREGATION
          ? undefined
          : formValues.general.yColumn?.agg;
      })(),
      format: getTooltipFormat(tooltip.type),
    }),
  );
}

function getTooltipFormat(dataType: DataType): string | undefined {
  switch (dataType) {
    case "integer":
      return ",d";
    case "number":
      return ".2f";
    default:
      return undefined;
  }
}

function convertDataTypeToVegaType(dataType: DataType): Type {
  switch (dataType) {
    case "number":
    case "integer":
      return "quantitative";
    case "string":
      return "nominal";
    case "boolean":
      return "nominal";
    case "date":
    case "datetime":
    case "time":
      return "temporal";
    case "unknown":
      return "nominal";
    default:
      logNever(dataType);
      return "nominal";
  }
}

function convertChartTypeToMark(chartType: ChartType): Mark {
  switch (chartType) {
    case ChartType.PIE:
      return "arc";
    case ChartType.SCATTER:
      return "point";
    default:
      return chartType;
  }
}
