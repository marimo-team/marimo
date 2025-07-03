/* Copyright 2024 Marimo. All rights reserved. */

import type { StandardType } from "vega-lite/build/src/type";
import type { DataType } from "@/core/kernel/messages";
import type { Mark } from "@/plugins/impl/vega/types";
import { logNever } from "@/utils/assertNever";
import { ChartType, type SelectableDataType } from "../types";

export interface BaseSpec {
  $schema: string;
  background: string;
  title: string | undefined;
  data: { values: object[] };
  height: number;
  width: number | "container";
  config: {
    axis: {
      grid: boolean;
    };
  };
}

export function convertDataTypeToVega(
  dataType: DataType | SelectableDataType,
): StandardType {
  switch (dataType) {
    case "number":
    case "integer":
      return "quantitative";
    case "string":
    case "boolean":
    case "unknown":
      return "nominal";
    case "date":
    case "datetime":
    case "time":
    case "temporal":
      return "temporal";
    default:
      logNever(dataType);
      return "nominal";
  }
}

export function convertDataTypeToSelectable(
  type: DataType,
): SelectableDataType {
  switch (type) {
    case "number":
    case "integer":
      return "number";
    case "string":
    case "boolean":
    case "unknown":
      return "string";
    case "date":
    case "datetime":
    case "time":
      return "temporal";
    default:
      logNever(type);
      return "string";
  }
}

export function convertChartTypeToMark(chartType: ChartType): Mark {
  switch (chartType) {
    case ChartType.PIE:
      return "arc";
    case ChartType.SCATTER:
      return "point";
    case ChartType.HEATMAP:
      return "rect";
    default:
      return chartType;
  }
}
