/* Copyright 2024 Marimo. All rights reserved. */

import type { StringFieldDef } from "vega-lite/build/src/channeldef";
import type { z } from "zod";
import type { AxisSchema, ChartSchemaType } from "../schemas";
import type { TimeUnitTooltip } from "../types";
import type { DataType } from "@/core/kernel/messages";
import type { Tooltip } from "../components/form-fields";
import type { Aggregate } from "vega-lite/build/src/aggregate";
import { isFieldSet } from "./spec";
import { COUNT_FIELD } from "../constants";
import { getAggregate } from "./encodings";

function getTooltipAggregate(
  field: string,
  column?: z.infer<typeof AxisSchema>,
): Aggregate | undefined {
  if (field !== column?.field) {
    return undefined;
  }

  if (column?.field === COUNT_FIELD) {
    return "count";
  }

  const selectedDataType = column?.selectedDataType;
  return getAggregate(column.aggregate, selectedDataType || "string");
}

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

function getTooltipTimeUnit(
  tooltip: Tooltip,
  formValues: ChartSchemaType,
): TimeUnitTooltip | undefined {
  const xColumn = formValues.general?.xColumn;
  const yColumn = formValues.general?.yColumn;
  const colorByColumn = formValues.general?.colorByColumn;
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
}

export function getTooltips(
  formValues: ChartSchemaType,
): Array<StringFieldDef<string>> | undefined {
  if (!formValues.tooltips) {
    return undefined;
  }

  let tooltips = formValues.tooltips.fields ?? [];
  const countTooltips: Array<StringFieldDef<string>> = [];

  // If autoTooltips is enabled, we manually add the x, y, and color columns to the tooltips
  if (formValues.tooltips.auto) {
    const newTooltips: Tooltip[] = [];
    const xColumn = formValues.general?.xColumn;
    const yColumn = formValues.general?.yColumn;
    const colorByColumn = formValues.general?.colorByColumn;

    const columns = [xColumn, yColumn, colorByColumn];
    for (const column of columns) {
      if (!isFieldSet(column?.field)) {
        continue;
      }

      if (column.field === COUNT_FIELD) {
        countTooltips.push({ aggregate: "count" });
      } else {
        newTooltips.push({
          field: column.field,
          type: column.type || "string",
        });
      }
    }

    tooltips = newTooltips;
  }

  const formattedTooltips = tooltips.map((tooltip): StringFieldDef<string> => {
    const timeUnit = getTooltipTimeUnit(tooltip, formValues);
    return {
      field: tooltip.field,
      aggregate: getTooltipAggregate(
        tooltip.field,
        formValues.general?.yColumn,
      ),
      format: getTooltipFormat(tooltip.type),
      timeUnit: timeUnit,
      title: timeUnit ? tooltip.field : undefined,
    };
  });

  return [...countTooltips, ...formattedTooltips];
}
