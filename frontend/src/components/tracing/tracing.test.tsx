/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { formatChartTime } from "./tracing";

describe("formatChartTime", () => {
  it("should format a valid timestamp correctly", () => {
    const timestamp = 1_700_000_000; // Example timestamp
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2023-11-15 06:13:20.000");
  });

  it("should handle a timestamp with milliseconds correctly", () => {
    const timestamp = 1_700_000_000.123;
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2023-11-15 06:13:20.123");
  });

  it("should handle a timestamp at the start of the year correctly", () => {
    const timestamp = 1_640_966_400;
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2022-01-01 00:00:00.000");
  });

  it("should handle a timestamp at the end of the year correctly", () => {
    const timestamp = 1_640_966_399;
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2021-12-31 23:59:59.000");
  });
});
