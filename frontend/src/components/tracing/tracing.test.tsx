/* Copyright 2024 Marimo. All rights reserved. */
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { formatChartTime } from "./tracing";

describe("formatChartTime", () => {
  beforeAll(() => {
    // Mock Date to always use UTC
    vi.spyOn(globalThis.Date.prototype, "getFullYear").mockImplementation(
      function (this: Date) {
        return this.getUTCFullYear();
      },
    );
    vi.spyOn(globalThis.Date.prototype, "getMonth").mockImplementation(
      function (this: Date) {
        return this.getUTCMonth();
      },
    );
    vi.spyOn(globalThis.Date.prototype, "getDate").mockImplementation(function (
      this: Date,
    ) {
      return this.getUTCDate();
    });
    vi.spyOn(globalThis.Date.prototype, "getHours").mockImplementation(
      function (this: Date) {
        return this.getUTCHours();
      },
    );
    vi.spyOn(globalThis.Date.prototype, "getMinutes").mockImplementation(
      function (this: Date) {
        return this.getUTCMinutes();
      },
    );
    vi.spyOn(globalThis.Date.prototype, "getSeconds").mockImplementation(
      function (this: Date) {
        return this.getUTCSeconds();
      },
    );
    vi.spyOn(globalThis.Date.prototype, "getMilliseconds").mockImplementation(
      function (this: Date) {
        return this.getUTCMilliseconds();
      },
    );
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  it("should handle a timestamp with milliseconds correctly", () => {
    const timestamp = 1_704_067_200.123;
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2024-01-01 00:00:00.123");
  });

  it("should handle a timestamp at the start of the year correctly", () => {
    const timestamp = 1_704_067_200;
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2024-01-01 00:00:00.000");
  });

  it("should handle a timestamp at the end of the year correctly", () => {
    const timestamp = 1_704_067_199;
    const formattedTime = formatChartTime(timestamp);
    expect(formattedTime).toBe("2023-12-31 23:59:59.000");
  });
});
