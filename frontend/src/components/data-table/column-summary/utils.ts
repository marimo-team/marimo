/* Copyright 2024 Marimo. All rights reserved. */

import type { StringFieldDef } from "vega-lite/types_unstable/channeldef.js";
import { Logger } from "@/utils/Logger";
import type { BinValues } from "../types";

const READABLE_TIME_FORMAT = "%-I:%M:%S %p"; // e.g., 1:02:30 AM (no leading zero on hour)

export function getPartialTimeTooltip(
  values: BinValues,
): Partial<StringFieldDef<string>> {
  if (values.length === 0) {
    return {};
  }

  // Find non-null value
  const value = values.find((v) => v.bin_start !== null)?.bin_start;
  if (!value) {
    return {};
  }

  // If value is a year (2019, 2020, etc), we return empty as it bugs out when we return a time unit
  if (typeof value === "number" && value.toString().length === 4) {
    return {};
  }

  // If value is just time (00:00:00, 01:00:00, etc)
  if (typeof value === "string" && value.length === 8) {
    return {
      type: "temporal",
      timeUnit: "hoursminutesseconds",
      format: READABLE_TIME_FORMAT,
    };
  }

  // If value is a date (2019-01-01, 2020-01-01, etc)
  if (typeof value === "string" && value.length === 10) {
    return {
      type: "temporal",
      timeUnit: "yearmonthdate",
    };
  }

  // If value is a datetime (2019-01-01 00:00:00, 2020-01-01 00:00:00, 2023-05-15T01:00:00 etc)
  if (typeof value === "string" && value.length === 19) {
    const minimumValue = value; // non-null value
    const maximumValue = values[values.length - 1].bin_end;

    try {
      const minimumDate = new Date(minimumValue);
      const maximumDate = new Date(maximumValue as string);
      const timeDifference = maximumDate.getTime() - minimumDate.getTime();

      // If time difference is less than 1 day, we use hoursminutesseconds
      if (timeDifference < 1000 * 60 * 60 * 24) {
        return {
          type: "temporal",
          timeUnit: "hoursminutesseconds",
          format: READABLE_TIME_FORMAT,
        };
      }
    } catch (error) {
      Logger.debug("Error parsing date", error);
    }

    return {
      type: "temporal",
      timeUnit: "yearmonthdatehoursminutes",
    };
  }

  Logger.debug("Unknown time unit", value);

  return {
    type: "temporal",
    timeUnit: "yearmonthdate",
  };
}

/**
 * Calculate the bin step for a given set of values.
 * If the bin step is too small for a large range, it can crash the browser.
 *
 * @param values - The values to calculate the bin step for.
 * @returns The bin step.
 */
export function calculateBinStep(values: BinValues) {
  if (values.length === 0) {
    return 1;
  }

  const validValues = values.filter(
    (v) => v.bin_start !== null && v.bin_end !== null,
  );

  if (validValues.length === 0) {
    return 1;
  }

  // Check the data types
  const firstStart = validValues[0].bin_start;
  const firstEnd = validValues[0].bin_end;

  // If values are strings or dates, we need to convert them to numbers
  let min: number;
  let max: number;

  // Use first and last values since binValues are sorted
  if (typeof firstStart === "number" && typeof firstEnd === "number") {
    const firstValue = validValues[0];
    const lastValue = validValues[validValues.length - 1];
    min = firstValue.bin_start as number;
    max = lastValue.bin_end as number;
  } else if (typeof firstStart === "string" || typeof firstEnd === "string") {
    // String data (likely dates) - convert to timestamps
    const firstValue = validValues[0];
    const lastValue = validValues[validValues.length - 1];
    const firstStart = new Date(firstValue.bin_start as string).getTime();
    const lastEnd = new Date(lastValue.bin_end as string).getTime();
    min = firstStart;
    max = lastEnd;
  } else {
    // Date objects - use first and last values since they're sorted
    const firstValue = validValues[0];
    const lastValue = validValues[validValues.length - 1];
    min = (firstValue.bin_start as Date).getTime();
    max = (lastValue.bin_end as Date).getTime();
  }

  const range = max - min;

  // Handle edge case where range is 0
  if (range === 0) {
    return 1;
  }

  const numBins = validValues.length;
  const step = range / numBins;

  // Ensure minimum step size
  return Math.max(step, 1);
}
