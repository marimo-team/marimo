/* Copyright 2024 Marimo. All rights reserved. */

import type {
  ColorDef,
  PositionDef,
  StringFieldDef,
} from "vega-lite/build/src/channeldef";
import type { ChartSchemaType } from "../schemas";
import type { DataType } from "@/core/kernel/messages";
import { isFieldSet } from "./spec";

function getTooltipFormat(dataType: DataType): string | undefined {
  switch (dataType) {
    case "integer":
      return ",.0f"; // Use comma grouping and no decimals
    case "number":
      return ",.2f"; // Use comma grouping and 2 decimal places
    default:
      return undefined;
  }
}

interface GetTooltipParams {
  formValues: ChartSchemaType;
  xEncoding: PositionDef<string>;
  yEncoding: PositionDef<string>;
  colorByEncoding?: ColorDef<string>;
}

export function getTooltips(
  params: GetTooltipParams,
): Array<StringFieldDef<string>> | undefined {
  const { formValues, xEncoding, yEncoding, colorByEncoding } = params;

  if (!formValues.tooltips) {
    return undefined;
  }

  // We need to add the same params defined in the columns to the tooltip
  // Else, the tooltips will alter the display of the chart
  function addTooltip(
    encoding: PositionDef<string> | ColorDef<string>,
    type: DataType,
    title?: string,
  ): StringFieldDef<string> | undefined {
    // For count of records, there will not be a field set
    if (
      "aggregate" in encoding &&
      encoding.aggregate === "count" &&
      !isFieldSet(encoding.field)
    ) {
      return { aggregate: "count" };
    }

    if (encoding && "field" in encoding && isFieldSet(encoding.field)) {
      const tooltip: StringFieldDef<string> = {
        field: encoding.field,
        aggregate: encoding.aggregate,
        timeUnit: encoding.timeUnit,
        format: getTooltipFormat(type),
        title: title,
        bin: encoding.bin,
      };
      return tooltip;
    }
  }

  // If autoTooltips is enabled, we manually add the x, y, and color columns to the tooltips
  if (formValues.tooltips.auto) {
    const tooltips: Array<StringFieldDef<string>> = [];
    const xTooltip = addTooltip(
      xEncoding,
      formValues.general?.xColumn?.type || "string",
      formValues.xAxis?.label,
    );
    if (xTooltip) {
      tooltips.push(xTooltip);
    }

    const yTooltip = addTooltip(
      yEncoding,
      formValues.general?.yColumn?.type || "string",
      formValues.yAxis?.label,
    );
    if (yTooltip) {
      tooltips.push(yTooltip);
    }

    const colorTooltip = addTooltip(
      colorByEncoding || {},
      formValues.general?.colorByColumn?.type || "string",
    );
    if (colorTooltip) {
      tooltips.push(colorTooltip);
    }

    return tooltips;
  }

  // Selected tooltips from the form.
  const selectedTooltips = formValues.tooltips.fields ?? [];
  const tooltips: Array<StringFieldDef<string>> = [];

  // We need to find the matching columns for the selected tooltips if they exist
  // Otherwise, we can add them without other parameters
  for (const tooltip of selectedTooltips) {
    if (
      "field" in xEncoding &&
      isFieldSet(xEncoding.field) &&
      xEncoding.field === tooltip.field
    ) {
      const xTooltip = addTooltip(
        xEncoding,
        formValues.general?.xColumn?.type || "string",
        formValues.xAxis?.label,
      );
      if (xTooltip) {
        tooltips.push(xTooltip);
      }
      continue;
    }

    if (
      "field" in yEncoding &&
      isFieldSet(yEncoding.field) &&
      yEncoding.field === tooltip.field
    ) {
      const yTooltip = addTooltip(
        yEncoding,
        formValues.general?.yColumn?.type || "string",
        formValues.yAxis?.label,
      );
      if (yTooltip) {
        tooltips.push(yTooltip);
      }
      continue;
    }

    if (
      colorByEncoding &&
      "field" in colorByEncoding &&
      isFieldSet(colorByEncoding.field) &&
      colorByEncoding.field === tooltip.field
    ) {
      const colorTooltip = addTooltip(
        colorByEncoding,
        formValues.general?.colorByColumn?.type || "string",
      );
      if (colorTooltip) {
        tooltips.push(colorTooltip);
      }
      continue;
    }

    const otherTooltip: StringFieldDef<string> = {
      field: tooltip.field,
    };
    tooltips.push(otherTooltip);
  }

  return tooltips;
}
