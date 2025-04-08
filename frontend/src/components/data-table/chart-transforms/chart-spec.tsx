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
} from "./chart-schemas";
import type { z } from "zod";
import type { Mark } from "@/plugins/impl/vega/types";
import { logNever } from "@/utils/assertNever";
import type { Type } from "vega-lite/build/src/type";

export function createVegaSpec(
  chartType: ChartType,
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number,
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

  const xEncoding = {
    field: formValues.general.xColumn?.field,
    type: convertDataTypeToVegaType(
      formValues.general.xColumn?.type ?? "unknown",
    ),
    bin: formValues.xAxis?.bin ? getBin(formValues.xAxis.bin) : undefined,
    title: xAxisLabel,
  };

  const yEncoding = {
    field: formValues.general.yColumn?.field,
    type: convertDataTypeToVegaType(
      formValues.general.yColumn?.type ?? "unknown",
    ),
    bin: formValues.yAxis?.bin ? getBin(formValues.yAxis.bin) : undefined,
    title: yAxisLabel,
  };

  let xOffset: object | undefined;
  if (formValues.general.stacking) {
    xOffset = {
      field:
        formValues.general.groupByColumn?.field === NONE_GROUP_BY
          ? undefined
          : formValues.general.groupByColumn?.field,
    };
  }

  return {
    $schema: "https://vega.github.io/schema/vega-lite/v6.json",
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
      xOffset: xOffset,
      ...getGroupBy(chartType, formValues),
      tooltip: getTooltips(formValues),
    },
  };
}

// groupBy can conflict with the color encoding for pie charts
function getGroupBy(
  chartType: ChartType,
  formValues: z.infer<typeof ChartSchema>,
) {
  if (
    chartType === ChartType.PIE ||
    formValues.general.groupByColumn?.field === NONE_GROUP_BY
  ) {
    return undefined;
  }

  return {
    color: {
      field: formValues.general.groupByColumn?.field,
      type: convertDataTypeToVegaType(
        formValues.general.groupByColumn?.type ?? "unknown",
      ),
    },
  };
}

function getBin(binValues: z.infer<typeof BinSchema>) {
  if (binValues.binned) {
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
  return formValues.general.tooltips?.map((tooltip) => ({
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
  }));
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
