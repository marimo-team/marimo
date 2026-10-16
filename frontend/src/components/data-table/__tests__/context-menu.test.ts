/* Copyright 2026 Marimo. All rights reserved. */

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildCellFilter } from "../context-menu";

describe("buildCellFilter", () => {
  // Use a non-UTC, non-DST-ambiguous offset so date-only parsing bugs
  // (UTC vs. local midnight) can't hide behind a host machine that
  // happens to run in UTC.
  let originalTimezone: string | undefined;
  beforeAll(() => {
    originalTimezone = process.env.TZ;
    process.env.TZ = "America/New_York";
  });
  afterAll(() => {
    process.env.TZ = originalTimezone;
  });

  it("builds an equality filter for a normal date value", () => {
    const filter = buildCellFilter({
      type: "date",
      value: "2024-01-15",
      comparison: "eq",
      dataType: "date",
      dtype: "date",
    });
    expect(filter).toEqual({
      type: "date",
      operator: "==",
      // Must be local midnight, not `new Date("2024-01-15")` (UTC
      // midnight), or the filter shifts by a day in UTC- timezones.
      value: new Date(2024, 0, 15),
    });
  });

  it("returns undefined for an empty-string date value in a non-temporal-looking context", () => {
    const filter = buildCellFilter({
      type: "date",
      value: "",
      comparison: "eq",
      dataType: "date",
      dtype: "date",
    });
    expect(filter).toBeUndefined();
  });

  it("returns undefined for an unparsable date value instead of an Invalid Date filter", () => {
    const filter = buildCellFilter({
      type: "date",
      value: "not-a-date",
      comparison: "eq",
      dataType: "date",
      dtype: "date",
    });
    expect(filter).toBeUndefined();
  });

  it("builds an equality filter for a normal datetime value", () => {
    const filter = buildCellFilter({
      type: "datetime",
      value: "2024-01-15 08:30:00",
      comparison: "eq",
      dataType: "datetime",
      dtype: "datetime64[ns]",
    });
    expect(filter).toEqual({
      type: "datetime",
      operator: "==",
      value: new Date(2024, 0, 15, 8, 30, 0),
    });
  });

  it("returns undefined for an unparsable datetime value", () => {
    const filter = buildCellFilter({
      type: "datetime",
      value: "not-a-datetime",
      comparison: "eq",
      dataType: "datetime",
      dtype: "datetime64[ns]",
    });
    expect(filter).toBeUndefined();
  });

  it("builds an equality filter for a normal time value", () => {
    const filter = buildCellFilter({
      type: "time",
      value: "08:30:00",
      comparison: "eq",
      dataType: "time",
    });
    expect(filter).toEqual({
      type: "time",
      operator: "==",
      value: new Date(1970, 0, 1, 8, 30, 0),
    });
  });

  it("returns undefined instead of an unparsable time value", () => {
    const filter = buildCellFilter({
      type: "time",
      value: "25:00:00",
      comparison: "eq",
      dataType: "time",
    });
    expect(filter).toBeUndefined();
  });

  it("maps a NaT date value to is_null instead of an invalid Date filter", () => {
    const filter = buildCellFilter({
      type: "date",
      value: "NaT",
      comparison: "eq",
      dataType: "date",
      dtype: "date",
    });
    expect(filter).toEqual({ type: "date", operator: "is_null" });
  });

  it("maps a NaT datetime value to is_not_null for the neq comparison", () => {
    const filter = buildCellFilter({
      type: "datetime",
      value: "NaT",
      comparison: "neq",
      dataType: "datetime",
      dtype: "datetime64[ns]",
    });
    expect(filter).toEqual({ type: "datetime", operator: "is_not_null" });
  });

  it("does not treat the string 'NaT' in a non-temporal column as a sentinel", () => {
    const filter = buildCellFilter({
      type: "text",
      value: "NaT",
      comparison: "eq",
      dataType: "string",
    });
    expect(filter).toEqual({ type: "text", operator: "equals", text: "NaT" });
  });

  it("maps an actual null value to is_null", () => {
    const filter = buildCellFilter({
      type: "number",
      value: null,
      comparison: "eq",
      dataType: "number",
    });
    expect(filter).toEqual({ type: "number", operator: "is_null" });
  });

  it("builds a literal (always-false) equality filter for a NaN number value", () => {
    // NaN is a real float value, not a missing-value marker like null/NaT,
    // and the backend's is_null() (narwhals/polars semantics) doesn't match
    // it, so it falls through to a normal (if unsatisfiable) == filter.
    const filter = buildCellFilter({
      type: "number",
      value: Number.NaN,
      comparison: "eq",
      dataType: "number",
    });
    expect(filter).toEqual({
      type: "number",
      operator: "==",
      value: Number.NaN,
    });
  });

  it("builds a literal equality filter for a normal number value", () => {
    const filter = buildCellFilter({
      type: "number",
      value: 42,
      comparison: "eq",
      dataType: "number",
    });
    expect(filter).toEqual({ type: "number", operator: "==", value: 42 });
  });
});
