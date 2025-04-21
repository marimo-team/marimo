/* Copyright 2024 Marimo. All rights reserved. */

import type { TopLevelSpec } from "vega-lite";
import { ChartType } from "./storage";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { DataType } from "@/core/kernel/messages";
import {
  type BinSchema,
  DEFAULT_AGGREGATION,
  DEFAULT_BIN_VALUE,
  type ChartSchema,
  DEFAULT_COLOR_SCHEME,
  type ScaleType,
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
import type { TypedString } from "@/utils/typed";

export type ErrorMessage = TypedString<"ErrorMessage">;

export function createVegaSpec(
  chartType: ChartType,
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
): TopLevelSpec | ErrorMessage {
  const { xColumn, yColumn, groupByColumn, horizontal, stacking, title } =
    formValues.general;

  // Validate required fields
  if (!FieldValidators.isRequired(xColumn?.field)) {
    return "X-axis column is required" as ErrorMessage;
  }
  if (!FieldValidators.isRequired(yColumn?.field)) {
    return "Y-axis column is required" as ErrorMessage;
  }

  // Get axis labels
  const xAxisLabel = FieldValidators.getLabel(
    xColumn.field,
    formValues.xAxis?.label,
  );
  const yAxisLabel = FieldValidators.getLabel(
    FieldValidators.getAggregatedLabel(yColumn.field, yColumn.agg),
    formValues.yAxis?.label,
  );

  // Determine encoding keys based on chart type
  const xEncodingKey = chartType === ChartType.PIE ? "theta" : "x";
  const yEncodingKey = chartType === ChartType.PIE ? "color" : "y";

  // Create encodings
  const xEncoding: PositionDef<string> | PolarDef<string> = {
    field: xColumn.field,
    type: TypeConverters.toVegaType(xColumn.scaleType ?? "unknown"),
    bin: EncodingUtils.getBin(formValues.xAxis?.bin),
    title: xAxisLabel,
    stack: groupByColumn?.field && horizontal ? stacking : undefined,
    sort: xColumn.sort,
  };

  const yEncoding: PositionDef<string> | PolarDef<string> = {
    field: yColumn.field,
    type: TypeConverters.toVegaType(yColumn.type ?? "unknown"),
    bin: EncodingUtils.getBin(formValues.yAxis?.bin),
    title: yAxisLabel,
    scale:
      yEncodingKey === "color"
        ? EncodingUtils.getColorInScale(formValues)
        : undefined,
    stack: groupByColumn?.field && !horizontal ? stacking : undefined,
    aggregate: yColumn.agg === DEFAULT_AGGREGATION ? undefined : yColumn.agg,
  };

  // Create the final spec
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: theme === "dark" ? "dark" : "white",
    title,
    data: { values: data },
    height: formValues.yAxis?.height ?? height,
    width: formValues.xAxis?.width ?? width,
    mark: { type: TypeConverters.toMark(chartType) },
    encoding: {
      [xEncodingKey]: horizontal ? yEncoding : xEncoding,
      [yEncodingKey]: horizontal ? xEncoding : yEncoding,
      xOffset: EncodingUtils.getOffset(chartType, formValues),
      ...ColorUtils.getColor(chartType, formValues),
      tooltip: EncodingUtils.getTooltips(formValues),
    },
  };
}

// Type conversion utilities
export const TypeConverters = {
  toVegaType(dataType: DataType | ScaleType): Type {
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
  },

  toScaleType(type: DataType): ScaleType {
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
  },

  toMark(chartType: ChartType): Mark {
    switch (chartType) {
      case ChartType.PIE:
        return "arc";
      case ChartType.SCATTER:
        return "point";
      default:
        return chartType;
    }
  },
};

// Field validation utilities
const FieldValidators = {
  isRequired(field: string | undefined): field is string {
    return field !== undefined && field.trim() !== "";
  },

  getLabel(field: string, label?: string): string {
    return label?.trim() || field;
  },

  getAggregatedLabel(field: string, agg?: string): string {
    if (!agg || agg === DEFAULT_AGGREGATION) {
      return field;
    }
    return `${agg.toUpperCase()}(${field})`;
  },
};

// Encoding utilities
const EncodingUtils = {
  getBin(binValues?: z.infer<typeof BinSchema>) {
    if (!binValues?.binned) {
      return undefined;
    }
    return binValues.step === DEFAULT_BIN_VALUE
      ? true
      : { binned: true, step: binValues.step };
  },

  getColorInScale(formValues: z.infer<typeof ChartSchema>) {
    const colorRange = formValues.color?.range;
    if (colorRange?.length) {
      return { range: colorRange };
    }

    const scheme = formValues.color?.scheme;
    return scheme === DEFAULT_COLOR_SCHEME
      ? undefined
      : { scheme: scheme as ColorScheme };
  },

  getOffset(
    chartType: ChartType,
    formValues: z.infer<typeof ChartSchema>,
  ): OffsetDef<string> | undefined {
    if (
      formValues.general.stacking ||
      !FieldValidators.isRequired(formValues.general.groupByColumn?.field) ||
      chartType === ChartType.PIE
    ) {
      return undefined;
    }
    return { field: formValues.general.groupByColumn?.field };
  },

  getTooltipAggregate(
    field: string,
    yColumn?: { field: string; agg: string },
  ): "count" | "sum" | "mean" | "median" | "min" | "max" | undefined {
    if (field !== yColumn?.field) {
      return undefined;
    }
    return yColumn.agg === DEFAULT_AGGREGATION
      ? undefined
      : (yColumn.agg as "count" | "sum" | "mean" | "median" | "min" | "max");
  },

  getTooltipFormat(dataType: DataType): string | undefined {
    switch (dataType) {
      case "integer":
        return ",.0f"; // Use comma grouping and no decimals
      case "number":
        return ",.2f"; // Use comma grouping and 2 decimal places
      default:
        return undefined;
    }
  },

  getTooltips(formValues: z.infer<typeof ChartSchema>) {
    if (!formValues.general.tooltips) {
      return undefined;
    }

    return formValues.general.tooltips.map(
      (tooltip): StringFieldDef<string> => ({
        field: tooltip.field,
        aggregate: this.getTooltipAggregate(
          tooltip.field,
          formValues.general.yColumn?.field && formValues.general.yColumn?.agg
            ? {
                field: formValues.general.yColumn.field,
                agg: formValues.general.yColumn.agg,
              }
            : undefined,
        ),
        format: this.getTooltipFormat(tooltip.type),
      }),
    );
  },
};

// Color encoding utilities
const ColorUtils = {
  getColor(
    chartType: ChartType,
    formValues: z.infer<typeof ChartSchema>,
  ): { color?: ColorDef<string> } | undefined {
    if (
      chartType === ChartType.PIE ||
      !FieldValidators.isRequired(formValues.general.groupByColumn?.field)
    ) {
      return undefined;
    }

    return {
      color: {
        field: formValues.general.groupByColumn.field,
        type: TypeConverters.toVegaType(
          formValues.general.groupByColumn.type ?? "unknown",
        ),
        scale: EncodingUtils.getColorInScale(formValues),
      },
    };
  },
};
