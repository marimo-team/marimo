/* Copyright 2024 Marimo. All rights reserved. */
import type { TopLevelSpec } from "vega-lite";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { DataType } from "@/core/kernel/messages";
import {
  type BinSchema,
  DEFAULT_BIN_VALUE,
  type ChartSchema,
  type AxisSchema,
} from "./chart-schemas";
import {
  ChartType,
  NONE_AGGREGATION,
  type SelectableDataType,
  type TimeUnitTooltip,
} from "./types";
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
import { COUNT_FIELD, DEFAULT_COLOR_SCHEME, EMPTY_VALUE } from "./constants";
import type { Tooltip } from "./form-components";

/**
 * Convert marimo chart configuration to Vega-Lite specification.
 */

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
    FieldValidators.getAggregatedLabel(yColumn.field, yColumn.aggregate),
    formValues.yAxis?.label,
  );

  // Determine encoding keys based on chart type
  const xEncodingKey = "x";
  const yEncodingKey = "y";

  // Create encodings
  const xEncoding = getAxisEncoding(
    xColumn,
    formValues.xAxis?.bin,
    xAxisLabel,
    colorByColumn?.field && horizontal ? stacking : undefined,
    chartType,
  );

  const yEncoding = getAxisEncoding(
    yColumn,
    formValues.yAxis?.bin,
    yAxisLabel,
    colorByColumn?.field && !horizontal ? stacking : undefined,
    chartType,
  );

  // Create the final spec
  return {
    ...getBaseSpec(data, formValues, theme, width, height, title),
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

export function getAxisEncoding(
  column: NonNullable<z.infer<typeof AxisSchema>>,
  binValues: z.infer<typeof BinSchema> | undefined,
  label: string | undefined,
  stack: boolean | undefined,
  chartType: ChartType,
): PositionDef<string> {
  if (column.field === COUNT_FIELD) {
    return {
      aggregate: "count",
      type: "quantitative",
      bin: EncodingUtils.getBin(binValues),
      title: label === COUNT_FIELD ? undefined : label,
      stack: stack,
    };
  }

  return {
    field: column.field,
    type: TypeConverters.toVegaType(column.selectedDataType || "unknown"),
    bin: EncodingUtils.getBin(binValues, chartType),
    title: label,
    stack: stack,
    aggregate:
      column.aggregate === NONE_AGGREGATION ? undefined : column.aggregate,
    timeUnit:
      column.selectedDataType === "temporal" ? column.timeUnit : undefined,
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

  const thetaEncoding: PolarDef<string> = getAxisEncoding(
    yColumn,
    formValues.xAxis?.bin,
    thetaFieldLabel,
    undefined,
    ChartType.PIE,
  );

  const colorEncoding: ColorDef<string> = {
    field: colorByColumn.field,
    type: TypeConverters.toVegaType(
      colorByColumn.selectedDataType || "unknown",
    ),
    scale: EncodingUtils.getColorInScale(formValues),
    title: colorFieldLabel,
  };

  return {
    ...getBaseSpec(data, formValues, theme, width, height, title),
    mark: {
      type: TypeConverters.toMark(ChartType.PIE),
      innerRadius: formValues.style?.innerRadius,
    },
    encoding: {
      theta: thetaEncoding,
      color: colorEncoding,
      tooltip: EncodingUtils.getTooltips(formValues),
    },
  };
}

function getBaseSpec(
  data: object[],
  formValues: z.infer<typeof ChartSchema>,
  theme: ResolvedTheme,
  width: number | "container",
  height: number,
  title?: string,
) {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: theme === "dark" ? "dark" : "white",
    title: title,
    data: { values: data },
    height: formValues.yAxis?.height ?? height,
    width: formValues.xAxis?.width ?? width,
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
      case ChartType.HEATMAP:
        return "rect";
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
    if (!agg || agg === NONE_AGGREGATION) {
      return field;
    }
    return `${agg.toUpperCase()}(${field})`;
  },
};

// Encoding utilities
const EncodingUtils = {
  getBin(binValues?: z.infer<typeof BinSchema>, chartType?: ChartType) {
    if (chartType === ChartType.HEATMAP) {
      return { maxbins: binValues?.maxbins };
    }

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
    // Offset only applies to bar charts, to unstack them
    if (
      formValues.general.stacking ||
      !FieldValidators.exists(formValues.general.colorByColumn?.field) ||
      chartType !== ChartType.BAR
    ) {
      return undefined;
    }
    return { field: formValues.general.colorByColumn?.field };
  },

  getTooltipAggregate(
    field: string,
    yColumn?: z.infer<typeof AxisSchema>,
  ): "count" | "sum" | "mean" | "median" | "min" | "max" | undefined {
    if (field !== yColumn?.field) {
      return undefined;
    }
    return yColumn.aggregate === NONE_AGGREGATION
      ? undefined
      : (yColumn.aggregate as
          | "count"
          | "sum"
          | "mean"
          | "median"
          | "min"
          | "max");
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

  getTooltipTimeUnit(
    tooltip: Tooltip,
    formValues: z.infer<typeof ChartSchema>,
  ): TimeUnitTooltip | undefined {
    const xColumn = formValues.general.xColumn;
    const yColumn = formValues.general.yColumn;
    const colorByColumn = formValues.general.colorByColumn;
    const columns = [xColumn, yColumn, colorByColumn];

    // Check if tooltip field matches any temporal column with timeUnit
    const matchingColumn = columns.find(
      (col) =>
        tooltip.field === col?.field &&
        col?.selectedDataType === "temporal" &&
        col?.timeUnit,
    );

    if (matchingColumn?.timeUnit) {
      return matchingColumn.timeUnit;
    }

    switch (tooltip.type) {
      case "datetime":
        return "yearmonthdatehoursminutesseconds";
      case "date":
        return "yearmonthdate";
      case "time":
        return "hoursminutesseconds";
      default:
        return undefined;
    }
  },

  getTooltips(formValues: z.infer<typeof ChartSchema>) {
    if (!formValues.general.tooltips) {
      return undefined;
    }

    return formValues.general.tooltips.map(
      (tooltip): StringFieldDef<string> => {
        const timeUnit = this.getTooltipTimeUnit(tooltip, formValues);
        return {
          field: tooltip.field,
          aggregate: this.getTooltipAggregate(
            tooltip.field,
            formValues.general.yColumn,
          ),
          format: this.getTooltipFormat(tooltip.type),
          timeUnit: timeUnit,
          title: timeUnit ? tooltip.field : undefined,
        };
      },
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
        type: TypeConverters.toVegaType(
          colorByColumn.selectedDataType || "unknown",
        ),
        scale: EncodingUtils.getColorInScale(formValues),
        aggregate: aggregate === NONE_AGGREGATION ? undefined : aggregate,
      },
    };
  },
};
