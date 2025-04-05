/* Copyright 2024 Marimo. All rights reserved. */

import type { TopLevelSpec } from "vega-lite";
import type { ChartType } from "./storage";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { DataType } from "@/core/kernel/messages";
import type { LineChartSchema } from "./chart-schemas";
import type { z } from "zod";

export function createVegaSpec(
  chartType: ChartType,
  data: object[],
  formValues: z.infer<typeof LineChartSchema>,
  theme: ResolvedTheme,
  width: number,
  height: number,
): TopLevelSpec | null {
  if (chartType === "line") {
    return {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      background: theme === "dark" ? "dark" : undefined,
      mark: {
        type: "line",
        cornerRadius: 2,
      },
      data: {
        values: data,
      },
      height: height,
      width: width,
      encoding: {
        x: {
          field: "continent",
          // type: "quantitative",
        },
        y: {
          field: "lifeExp",
          type: "quantitative",
        },
      },
    };
  }
  return null;
}

function convertDataTypeToVegaType(dataType: DataType) {
  switch (dataType) {
    case "number":
      return "quantitative";
    case "string":
      return "nominal";
    case "boolean":
      return "nominal";
    case "date":
      return "temporal";
    case "datetime":
      return "temporal";
    default:
      return "nominal";
  }
}
