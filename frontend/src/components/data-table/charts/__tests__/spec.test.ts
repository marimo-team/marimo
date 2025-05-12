/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getAxisEncoding } from "../chart-spec/spec";
import { AGGREGATION_FNS, ChartType, STRING_AGGREGATION_FNS } from "../types";
import { COUNT_FIELD } from "../constants";
import { NONE_AGGREGATION } from "../types";

describe("getAxisEncoding", () => {
  it("should return correct encoding for COUNT_FIELD", () => {
    const result = getAxisEncoding(
      {
        field: COUNT_FIELD,
        selectedDataType: "number",
        aggregate: "sum",
        timeUnit: undefined,
      },
      { binned: true, step: 10 },
      COUNT_FIELD,
      true,
      ChartType.BAR,
    );

    expect(result).toEqual({
      aggregate: "count",
      type: "quantitative",
      bin: { binned: true, step: 10 },
      title: undefined,
      stack: true,
    });
  });

  it("should return correct encoding for numeric field with aggregation", () => {
    const result = getAxisEncoding(
      {
        field: "price",
        selectedDataType: "number",
        aggregate: "mean",
        timeUnit: undefined,
      },
      undefined,
      "Average Price",
      false,
      ChartType.BAR,
    );

    expect(result).toEqual({
      field: "price",
      type: "quantitative",
      bin: undefined,
      title: "Average Price",
      stack: false,
      aggregate: "mean",
    });
  });

  it("should return correct encoding for temporal field with timeUnit", () => {
    const result = getAxisEncoding(
      {
        field: "date",
        selectedDataType: "temporal",
        aggregate: NONE_AGGREGATION,
        timeUnit: "yearmonth",
      },
      undefined,
      "Date",
      undefined,
      ChartType.LINE,
    );

    expect(result).toEqual({
      field: "date",
      type: "temporal",
      bin: undefined,
      title: "Date",
      stack: undefined,
      aggregate: undefined,
      timeUnit: "yearmonth",
    });
  });

  it("should return correct encoding for categorical field", () => {
    const result = getAxisEncoding(
      {
        field: "category",
        selectedDataType: "string",
        aggregate: NONE_AGGREGATION,
        timeUnit: undefined,
      },
      undefined,
      "Category",
      true,
      ChartType.BAR,
    );

    expect(result).toEqual({
      field: "category",
      type: "nominal",
      bin: undefined,
      title: "Category",
      stack: true,
      aggregate: undefined,
    });
  });

  it("should handle undefined bin values", () => {
    const result = getAxisEncoding(
      {
        field: "value",
        selectedDataType: "number",
        aggregate: "sum",
        timeUnit: undefined,
      },
      undefined,
      "Value",
      false,
      ChartType.BAR,
    );

    expect((result as { bin?: unknown }).bin).toBeUndefined();
  });

  it("should handle undefined label", () => {
    const result = getAxisEncoding(
      {
        field: "value",
        selectedDataType: "number",
        aggregate: "sum",
        timeUnit: undefined,
      },
      undefined,
      undefined,
      false,
      ChartType.BAR,
    );

    expect((result as { title?: string }).title).toBeUndefined();
  });

  it("should invalid aggregation for string data types", () => {
    for (const agg of AGGREGATION_FNS) {
      const result = getAxisEncoding(
        {
          field: "value",
          selectedDataType: "string",
          aggregate: agg,
          timeUnit: undefined,
        },
        undefined,
        "Value",
        false,
        ChartType.BAR,
      );

      const expectedAggregate = (result as { aggregate?: string }).aggregate;

      // For aggregations that are not valid for string data types, we should return undefined
      if (agg === NONE_AGGREGATION || !STRING_AGGREGATION_FNS.includes(agg)) {
        expect(expectedAggregate).toBeUndefined();
      } else if (STRING_AGGREGATION_FNS.includes(agg)) {
        expect(expectedAggregate).toEqual(agg);
      }
    }
  });

  it("should return undefined for temporal data types", () => {
    for (const agg of AGGREGATION_FNS) {
      const result = getAxisEncoding(
        {
          field: "date",
          selectedDataType: "temporal",
          aggregate: agg,
          timeUnit: undefined,
        },
        undefined,
        "Date",
        false,
        ChartType.BAR,
      );

      const expectedAggregate = (result as { aggregate?: string }).aggregate;
      expect(expectedAggregate).toBeUndefined();
    }
  });
});
