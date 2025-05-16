/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getAxisEncoding } from "../chart-spec/spec";
import { AGGREGATION_FNS, ChartType, STRING_AGGREGATION_FNS } from "../types";
import { COUNT_FIELD } from "../constants";
import { NONE_AGGREGATION } from "../types";
import { getTooltips } from "../chart-spec/tooltips";
import type { ChartSchemaType } from "../schemas";
import type { PositionDef } from "vega-lite/build/src/channeldef";

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
      bin: { step: 10 },
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

describe("getTooltips", () => {
  it("should return no tooltips if undefined", () => {
    const result = getTooltips({
      formValues: {
        general: {
          xColumn: { field: "x", type: "string" as const },
        },
      },
      xEncoding: { field: "x", type: "nominal" },
      yEncoding: {},
    });

    expect(result).toBeUndefined();
  });

  it("should return tooltips for x, y and colour when auto is enabled", () => {
    const autoTooltips = {
      auto: true,
      fields: [],
    };

    const formValues: ChartSchemaType = {
      general: {
        xColumn: {
          type: "string" as const,
        },
        yColumn: {
          type: "number" as const,
        },
        colorByColumn: {
          type: "integer" as const,
        },
      },
      tooltips: autoTooltips,
      xAxis: { label: "X Axis" },
    };

    const xEncoding = {
      field: "x",
      type: "nominal",
      timeUnit: "year",
      aggregate: "sum",
      bin: { step: 10 },
    } as PositionDef<string>;

    const result = getTooltips({
      formValues,
      xEncoding,
      yEncoding: { field: "y", type: "quantitative" },
    });

    const expected = [
      {
        field: "x",
        format: undefined,
        timeUnit: "year",
        title: "X Axis",
        aggregate: "sum",
        bin: {
          step: 10,
        },
      },
      {
        field: "y",
        format: ",.2f", // For number fields, we should use 2 decimal places
        timeUnit: undefined,
        title: undefined,
        aggregate: undefined,
      },
    ];

    expect(result).toEqual(expected);

    const resultWithColor = getTooltips({
      formValues,
      xEncoding,
      yEncoding: { field: "y", type: "quantitative" },
      colorByEncoding: { field: "color", type: "nominal" },
    });

    expect(resultWithColor).toEqual([
      ...expected,
      {
        field: "color",
        format: ",.0f", // For integer fields, we should use no decimal places
        timeUnit: undefined,
        title: undefined,
        aggregate: undefined,
      },
    ]);
  });

  it("should return no fields when auto is false", () => {
    const result = getTooltips({
      formValues: {
        general: {
          xColumn: { field: "x", type: "string" as const },
          yColumn: { field: "y", type: "number" as const },
        },
        tooltips: {
          auto: false,
          fields: [],
        },
      },
      xEncoding: { field: "x", type: "nominal" },
      yEncoding: { field: "y", type: "quantitative" },
    });

    expect(result).toEqual([]);
  });

  it("should enhance tooltips with encoding parameters when field name matches encoding field", () => {
    const formValues = {
      general: {
        xColumn: { type: "string" as const },
        yColumn: { type: "number" as const },
        colorByColumn: { type: "string" as const },
      },
      tooltips: {
        auto: false,
        fields: [
          { field: "category", type: "string" as const },
          { field: "revenue", type: "number" as const },
          { field: "region", type: "string" as const },
          { field: "other", type: "string" as const },
        ],
      },
      xAxis: { label: "Product Category" },
      yAxis: { label: "Total Revenue" },
    };

    const result = getTooltips({
      formValues,
      xEncoding: {
        field: "category",
        type: "nominal",
      },
      yEncoding: {
        field: "revenue",
        type: "quantitative",
        aggregate: "sum",
      },
      colorByEncoding: { field: "region", type: "nominal" },
    });

    expect(result).toEqual([
      {
        field: "category",
        format: undefined,
        timeUnit: undefined,
        title: "Product Category",
        aggregate: undefined,
      },
      {
        field: "revenue",
        format: ",.2f",
        timeUnit: undefined,
        title: "Total Revenue",
        aggregate: "sum",
      },
      {
        field: "region",
        format: undefined,
        timeUnit: undefined,
        title: undefined,
        aggregate: undefined,
      },
      {
        field: "other",
      },
    ]);
  });

  it("should handle count aggregate with no field set", () => {
    const formValues = {
      general: {
        xColumn: { field: "category", type: "string" as const },
        yColumn: { field: COUNT_FIELD, type: "number" as const },
      },
      tooltips: {
        auto: true,
        fields: [],
      },
    };

    const result = getTooltips({
      formValues,
      xEncoding: { field: "category", type: "nominal" },
      yEncoding: { aggregate: "count", type: "quantitative" },
    });

    expect(result).toEqual([
      {
        field: "category",
        format: undefined,
        timeUnit: undefined,
        title: undefined,
        aggregate: undefined,
      },
      {
        aggregate: "count",
      },
    ]);
  });
});
