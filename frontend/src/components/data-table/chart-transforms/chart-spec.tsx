/* Copyright 2024 Marimo. All rights reserved. */

import type { TopLevelSpec } from "vega-lite";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { DataType } from "@/core/kernel/messages";
import {
  type BinSchema,
  DEFAULT_AGGREGATION,
  DEFAULT_BIN_VALUE,
  type ChartSchema,
  DEFAULT_COLOR_SCHEME,
  type SelectableDataType,
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
import { ChartType, EMPTY_VALUE } from "./constants";

export type ErrorMessage = TypedString<"ErrorMessage">;

export function createVegaSpec(
  chartType: ChartType,
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
): TopLevelSpec | ErrorMessage {
  const { xColumn, yColumn, colorByColumn, horizontal, stacking, title } =
    formValues.general;

  if (chartType === ChartType.PIE) {
    return getPieChartSpec(data, formValues, theme, width, height);
  }

  // Validate required fields
  if (!FieldValidators.exists(xColumn?.field)) {
    return "X-axis column is required" as ErrorMessage;
  }
  if (!FieldValidators.exists(yColumn?.field)) {
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
  const xEncodingKey = "x";
  const yEncodingKey = "y";

  // Create encodings
  const xEncoding: PositionDef<string> | PolarDef<string> = {
    field: xColumn.field,
    type: TypeConverters.toVegaType(xColumn.selectedDataType ?? "unknown"),
    bin: EncodingUtils.getBin(formValues.xAxis?.bin),
    title: xAxisLabel,
    stack: colorByColumn?.field && horizontal ? stacking : undefined,
    sort: xColumn.sort,
    timeUnit:
      xColumn.selectedDataType === "temporal" ? xColumn.timeUnit : undefined,
  };

  const yEncoding: PositionDef<string> | PolarDef<string> = {
    field: yColumn.field,
    type: TypeConverters.toVegaType(yColumn.selectedDataType ?? "unknown"),
    bin: EncodingUtils.getBin(formValues.yAxis?.bin),
    title: yAxisLabel,
    stack: colorByColumn?.field && !horizontal ? stacking : undefined,
    aggregate: yColumn.agg === DEFAULT_AGGREGATION ? undefined : yColumn.agg,
    timeUnit:
      yColumn.selectedDataType === "temporal" ? yColumn.timeUnit : undefined,
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

function getPieChartSpec(
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
) {
  const { yColumn, colorByColumn, title } = formValues.general;

  if (!FieldValidators.exists(colorByColumn?.field)) {
    return "Color by column is required" as ErrorMessage;
  }

  if (!FieldValidators.exists(yColumn?.field)) {
    return "Size by column is required" as ErrorMessage;
  }

  const colorFieldLabel = FieldValidators.getLabel(
    colorByColumn.field,
    formValues.xAxis?.label,
  );

  const thetaFieldLabel = FieldValidators.getLabel(
    yColumn.field,
    formValues.xAxis?.label,
  );

  const thetaEncoding: PositionDef<string> | PolarDef<string> = {
    field: yColumn.field,
    type: TypeConverters.toVegaType(yColumn.type ?? "unknown"),
    bin: EncodingUtils.getBin(formValues.xAxis?.bin),
    title: thetaFieldLabel,
  };

  const colorEncoding: ColorDef<string> = {
    field: colorByColumn.field,
    type: TypeConverters.toVegaType(
      colorByColumn.selectedDataType ?? "unknown",
    ),
    scale: EncodingUtils.getColorInScale(formValues),
    title: colorFieldLabel,
  };

  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: theme === "dark" ? "dark" : "white",
    title,
    data: { values: data },
    height: formValues.yAxis?.height ?? height,
    width: formValues.xAxis?.width ?? width,
    mark: { type: TypeConverters.toMark(ChartType.PIE) },
    encoding: {
      theta: thetaEncoding,
      color: colorEncoding,
      tooltip: EncodingUtils.getTooltips(formValues),
    },
  };
}
// Type conversion utilities
export const TypeConverters = {
  toVegaType(dataType: DataType | SelectableDataType): Type | undefined {
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
        return undefined;
    }
  },

  toSelectableDataType(type: DataType): SelectableDataType {
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
export const FieldValidators = {
  exists(field: string | undefined): field is string {
    return field !== undefined && field.trim() !== EMPTY_VALUE;
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
      !FieldValidators.exists(formValues.general.colorByColumn?.field) ||
      chartType === ChartType.PIE
    ) {
      return undefined;
    }
    return { field: formValues.general.colorByColumn?.field };
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
      !FieldValidators.exists(formValues.general.colorByColumn?.field)
    ) {
      return undefined;
    }

    const aggregate = formValues.general.colorByColumn.agg;

    return {
      color: {
        field: formValues.general.colorByColumn.field,
        type: TypeConverters.toVegaType(
          formValues.general.colorByColumn.selectedDataType ?? "unknown",
        ),
        scale: EncodingUtils.getColorInScale(formValues),
        aggregate: aggregate === DEFAULT_AGGREGATION ? undefined : aggregate,
      },
    };
  },
};
