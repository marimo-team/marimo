/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  extractTimezone,
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "../types";

describe("toFieldTypes", () => {
  // Regression: https://github.com/marimo-team/marimo/issues/9269
  // Column names that look like non-negative integers (e.g. "2000",
  // "2010") get hoisted to the front in numeric order by the
  // ECMAScript `OrdinaryOwnPropertyKeys` algorithm whenever they live
  // as keys of a plain object. The data_editor's `FieldTypes` shape
  // (`Record<string, DataType>`) loses column order for those keys.
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
    expect(Object.keys(toFieldTypes(input))).toEqual([
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
