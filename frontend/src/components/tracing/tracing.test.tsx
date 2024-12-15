/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { formatChartTime } from "./tracing";

describe("formatUTCTime", () => {
  it("should format a timestamp correctly", () => {
    const timestamp = 1_700_000_000; // Example timestamp
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2023-11-15 06:13:20.000");
  });

  it("should return an empty string for invalid timestamp", () => {
    const invalidTimestamp = Number.NaN;
    const formattedTime = formatChartTime(invalidTimestamp);
    expect(formattedTime).toBe("");
  });
});
