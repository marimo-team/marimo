/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  extractTimezone,
  type FieldTypesWithExternalType,
  resolveDisplayTimezone,
  toFieldTypes,
} from "../types";

describe("toFieldTypes", () => {
  // Regression: https://github.com/marimo-team/marimo/issues/9269.
  // When `FieldTypes` was a plain `Record<string, DataType>`, column
  // names that look like non-negative integers (e.g. "2000", "2010")
  // were hoisted to the front in numeric order by ECMAScript's
  // `OrdinaryOwnPropertyKeys` algorithm. `Map` preserves insertion
  // order for all keys.
  it("preserves insertion order for digit-string column names", () => {
    const input: FieldTypesWithExternalType = [
      ["here", ["string", ""]],
      ["is", ["string", ""]],
      ["a", ["string", ""]],
      ["2010", ["number", ""]],
      ["column", ["string", ""]],
      ["2000", ["number", ""]],
      ["set", ["string", ""]],
    ];
    expect([...toFieldTypes(input).keys()]).toEqual([
      "here",
      "is",
      "a",
      "2010",
      "column",
      "2000",
      "set",
    ]);
  });
});

describe("extractTimezone", () => {
  it("should return undefined when dtype is undefined", () => {
    expect(extractTimezone(undefined)).toBe(undefined);
  });

  it("should return undefined when dtype is not a datetime with timezone", () => {
    expect(extractTimezone("string")).toBe(undefined);
    expect(extractTimezone("int64")).toBe(undefined);
    expect(extractTimezone("float64")).toBe(undefined);
    expect(extractTimezone("date")).toBe(undefined);
    expect(extractTimezone("datetime")).toBe(undefined);
    expect(extractTimezone("datetime[]")).toBe(undefined);
  });

  it("should return the timezone for datetime with timezone format", () => {
    expect(extractTimezone("datetime[ns,UTC]")).toBe("UTC");
    expect(extractTimezone("datetime[ns,US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime[ms,Europe/London]")).toBe("Europe/London");
    expect(extractTimezone("datetime[s,UTC]")).toBe("UTC");
    expect(extractTimezone("datetime[s,US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime[s,Europe/London]")).toBe("Europe/London");
    expect(extractTimezone("datetime[m,UTC]")).toBe("UTC");
    expect(extractTimezone("datetime[m,US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime[m,Europe/London]")).toBe("Europe/London");

    // With spaces
    expect(extractTimezone("datetime[ns, UTC]")).toBe("UTC");
    expect(extractTimezone("datetime[ns, US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime[m, Europe/London]")).toBe("Europe/London");
  });

  it("should return timezone for datetime64", () => {
    expect(extractTimezone("datetime64[ns, UTC]")).toBe("UTC");
    expect(extractTimezone("datetime64[ns, US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime64[ns, Europe/London]")).toBe(
      "Europe/London",
    );
    expect(extractTimezone("datetime64[m,US/Eastern]")).toBe("US/Eastern");
  });
});

describe("resolveDisplayTimezone", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns the encoded timezone when local display is disabled", () => {
    expect(resolveDisplayTimezone("datetime64[ns, UTC]", false)).toBe("UTC");
    expect(resolveDisplayTimezone("datetime64[ns, US/Eastern]", false)).toBe(
      "US/Eastern",
    );
  });

  it("returns undefined for naive datetimes even when enabled", () => {
    expect(resolveDisplayTimezone("datetime64[ns]", true)).toBe(undefined);
    expect(resolveDisplayTimezone(undefined, true)).toBe(undefined);
    expect(resolveDisplayTimezone("string", true)).toBe(undefined);
  });

  // Regression: https://github.com/marimo-team/marimo/issues/6250.
  // A timestamptz column (dtype "datetime64[ns, UTC]") should render in the
  // browser's local timezone when the user opts in, instead of UTC.
  it("returns the browser-local timezone for tz-aware dtypes when enabled", () => {
    vi.stubEnv("TZ", "America/Los_Angeles");
    const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    expect(localTimezone).toBe("America/Los_Angeles");
    expect(resolveDisplayTimezone("datetime64[ns, UTC]", true)).toBe(
      "America/Los_Angeles",
    );
    expect(resolveDisplayTimezone("datetime[us, UTC]", true)).toBe(
      "America/Los_Angeles",
    );
    expect(resolveDisplayTimezone("datetime64[ns, US/Eastern]", true)).toBe(
      "America/Los_Angeles",
    );
  });
});
