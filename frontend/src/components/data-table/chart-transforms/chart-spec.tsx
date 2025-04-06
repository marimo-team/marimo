/* Copyright 2024 Marimo. All rights reserved. */

import type { TopLevelSpec } from "vega-lite";
import { ChartType } from "./storage";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { DataType } from "@/core/kernel/messages";
import type { ChartSchema } from "./chart-schemas";
import type { z } from "zod";
import type { Mark } from "@/plugins/impl/vega/types";
import { logNever } from "@/utils/assertNever";
import type { Type } from "vega-lite/build/src/type";
import { capitalize } from "lodash-es";

export const DEFAULT_AGGREGATION = "default";

export function createVegaSpec(
  chartType: ChartType,
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number,
  height: number,
): TopLevelSpec {
  let xAxisLabel = formValues.general.xColumn?.field;
  let yAxisLabel = formValues.general.yColumn?.field;

  if (formValues.general.yColumn?.agg) {
    yAxisLabel = `${capitalize(formValues.general.yColumn.agg)} of ${yAxisLabel}`;
  }

  if (formValues.xAxis?.label && formValues.xAxis.label.trim() !== "") {
    xAxisLabel = formValues.xAxis.label;
  }

  if (formValues.yAxis?.label && formValues.yAxis.label.trim() !== "") {
    yAxisLabel = formValues.yAxis.label;
  }

  const xEncodingKey = chartType === ChartType.PIE ? "theta" : "x";
  const yEncodingKey = chartType === ChartType.PIE ? "color" : "y";

  return {
    $schema: "https://vega.github.io/schema/vega-lite/v6.json",
    background: theme === "dark" ? "dark" : "white",
    data: {
      values: data,
    },
    height: height,
    width: width,
    mark: {
      type: convertChartTypeToMark(chartType),
    },
    encoding: {
      [xEncodingKey]: {
        field: formValues.general.xColumn?.field,
        type: convertDataTypeToVegaType(
          formValues.general.xColumn?.type ?? "unknown",
        ),
        title: xAxisLabel,
      },
      [yEncodingKey]: {
        field: formValues.general.yColumn?.field,
        type: convertDataTypeToVegaType(
          formValues.general.yColumn?.type ?? "unknown",
        ),
        title: yAxisLabel,
        aggregate:
          formValues.general.yColumn?.agg === DEFAULT_AGGREGATION
            ? undefined
            : formValues.general.yColumn?.agg,
      },
    },
  };
}

// https://vega.github.io/vega-lite/docs/type.html
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
    default:
      return chartType as Mark;
  }
}
