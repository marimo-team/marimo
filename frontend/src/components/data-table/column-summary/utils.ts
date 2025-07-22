/* Copyright 2024 Marimo. All rights reserved. */

import type { StringFieldDef } from "vega-lite/build/src/channeldef";
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
