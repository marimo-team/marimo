/* Copyright 2024 Marimo. All rights reserved. */

import type { PositionDef } from "vega-lite/build/src/channeldef";
import { describe, expect, it } from "vitest";
import {
  getAggregate,
  getBinEncoding,
  getColorEncoding,
} from "../chart-spec/encodings";
import { getAxisEncoding } from "../chart-spec/spec";
import { getTooltips } from "../chart-spec/tooltips";
import { COUNT_FIELD, EMPTY_VALUE } from "../constants";
import type { ChartSchemaType } from "../schemas";
import {
  AGGREGATION_FNS,
  ChartType,
  NONE_VALUE,
  STRING_AGGREGATION_FNS,
} from "../types";

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
        aggregate: NONE_VALUE,
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
        aggregate: NONE_VALUE,
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
      if (agg === NONE_VALUE || !STRING_AGGREGATION_FNS.includes(agg)) {
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

  it("should return correct encoding for sorted data", () => {
    for (const sort of ["ascending", "descending", undefined]) {
      const result = getAxisEncoding(
        {
          field: "value",
          selectedDataType: "number",
          sort: sort as "ascending" | "descending" | undefined,
        },
        undefined,
        "Value",
        false,
        ChartType.BAR,
      );

      const expectedSort = (result as { sort?: string }).sort;
      expect(expectedSort).toEqual(sort);
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

  it("should handle time unit in tooltips", () => {
    const result = getTooltips({
      formValues: {
        general: {
          xColumn: { field: "x", type: "string" as const },
          yColumn: { field: "y", type: "number" as const },
        },
        tooltips: {
          auto: true,
          fields: [],
        },
      },
      xEncoding: { field: "x", type: "nominal", timeUnit: "year" },
      yEncoding: { field: "y", type: "quantitative" },
    });

    expect(result).toEqual([
      {
        field: "x",
        bin: undefined,
        format: undefined,
        timeUnit: "year",
        title: "x", // Should be set to field name
        aggregate: undefined,
      },
      {
        field: "y",
        format: ",.2f",
        timeUnit: undefined,
        title: undefined,
        aggregate: undefined,
      },
    ]);
  });
});

describe("getColorEncoding", () => {
  it("should return undefined for pie charts", () => {
    const result = getColorEncoding(ChartType.PIE, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: { field: "Color", type: "string" as const },
      },
    });

    expect(result).toBeUndefined();
  });

  it("should return undefined when no color field is set", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
      },
    });

    expect(result).toBeUndefined();
  });

  it("should return undefined when color field is NONE_VALUE", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: { field: NONE_VALUE, type: "string" as const },
      },
    });

    expect(result).toBeUndefined();
  });

  it("should return undefined when color field is empty string", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: { field: EMPTY_VALUE, type: "string" as const },
      },
    });

    expect(result).toBeUndefined();
  });

  it("should return count encoding for COUNT_FIELD", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: { field: COUNT_FIELD, type: "number" as const },
      },
    });

    expect(result).toEqual({
      aggregate: "count",
      type: "quantitative",
    });
  });

  it("should use colorByColumn when set", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: {
          field: "category",
          type: "string" as const,
          selectedDataType: "string",
          aggregate: "count" as const,
        },
      },
      color: {
        field: "Color",
        scheme: "category10",
      },
    });

    expect(result).toEqual({
      field: "category",
      type: "nominal",
      scale: { scheme: "category10" },
      aggregate: "count",
      bin: undefined,
    });
  });

  it("should use xColumn when color field matches xColumn field", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: {
          field: "category",
          type: "string" as const,
          selectedDataType: "string",
        },
        yColumn: { field: "y", type: "number" as const },
      },
      color: {
        field: "X",
        scheme: "category10",
      },
    });

    expect(result).toEqual({
      field: "category",
      type: "nominal",
      scale: { scheme: "category10" },
      aggregate: undefined,
      bin: undefined,
    });
  });

  it("should use yColumn when color field matches yColumn field", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" },
        yColumn: {
          field: "value",
          type: "number",
          selectedDataType: "number",
          aggregate: "sum",
        },
      },
      color: {
        field: "Y",
        scheme: "viridis",
      },
    });

    expect(result).toEqual({
      field: "value",
      type: "quantitative",
      scale: { scheme: "viridis" },
      aggregate: "sum",
      bin: undefined,
    });
  });

  it("should return undefined when color field doesn't match any column", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
      },
      color: {
        field: "Color",
        scheme: "category10",
      },
    });

    expect(result).toBeUndefined();
  });

  it("should handle bin encoding for numeric data", () => {
    const result = getColorEncoding(ChartType.HEATMAP, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: {
          field: "value",
          type: "number" as const,
          selectedDataType: "number",
        },
      },
      color: {
        bin: { maxbins: 10 },
      },
    });

    expect(result).toEqual({
      field: "value",
      type: "quantitative",
      scale: undefined,
      aggregate: undefined,
      bin: { maxbins: 10 },
    });
  });

  it("should handle color range instead of scheme", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: {
          field: "category",
          type: "string" as const,
          selectedDataType: "string",
        },
      },
      color: {
        range: ["red", "blue", "green"],
      },
    });

    expect(result).toEqual({
      field: "category",
      type: "nominal",
      scale: { range: ["red", "blue", "green"] },
      aggregate: undefined,
      bin: undefined,
    });
  });

  it("should handle temporal data types", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: {
          field: "date",
          type: "datetime" as const,
          selectedDataType: "temporal",
          aggregate: "sum" as const,
        },
      },
    });

    expect(result).toEqual({
      field: "date",
      type: "temporal",
      scale: undefined,
      aggregate: undefined, // temporal data types don't support aggregation
      bin: undefined,
    });
  });

  it("should handle string aggregation functions", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: {
          field: "category",
          type: "string" as const,
          selectedDataType: "string",
          aggregate: "count" as const,
        },
      },
    });

    expect(result).toEqual({
      field: "category",
      type: "nominal",
      scale: undefined,
      aggregate: "count",
      bin: undefined,
    });
  });

  it("should return undefined for invalid string aggregation", () => {
    const result = getColorEncoding(ChartType.BAR, {
      general: {
        xColumn: { field: "x", type: "string" as const },
        yColumn: { field: "y", type: "number" as const },
        colorByColumn: {
          field: "category",
          type: "string" as const,
          selectedDataType: "string",
          aggregate: "sum" as const, // sum is not valid for strings
        },
      },
    });

    expect(result).toEqual({
      field: "category",
      type: "nominal",
      scale: undefined,
      aggregate: undefined, // sum is not valid for strings
      bin: undefined,
    });
  });
});

describe("getAggregate", () => {
  it("should return undefined for temporal data types", () => {
    const result = getAggregate("sum", "temporal");
    expect(result).toBeUndefined();
  });

  it("should return undefined for NONE_VALUE", () => {
    const result = getAggregate("none", "number");
    expect(result).toBeUndefined();
  });

  it("should return undefined for BIN_AGGREGATION", () => {
    const result = getAggregate("bin", "number");
    expect(result).toBeUndefined();
  });

  it("should return defaultAggregate when aggregate is undefined", () => {
    const result = getAggregate(undefined, "number", "mean");
    expect(result).toEqual("mean");
  });

  it("should return undefined when aggregate is undefined and no default", () => {
    const result = getAggregate(undefined, "number");
    expect(result).toBeUndefined();
  });

  it("should return valid string aggregation for string data types", () => {
    const result = getAggregate("count", "string");
    expect(result).toEqual("count");
  });

  it("should return undefined for invalid string aggregation", () => {
    const result = getAggregate("sum", "string");
    expect(result).toBeUndefined();
  });

  it("should return aggregate for numeric data types", () => {
    const result = getAggregate("sum", "number");
    expect(result).toEqual("sum");
  });
});

describe("getBinEncoding", () => {
  it("should return maxbins for HEATMAP chart type", () => {
    const result = getBinEncoding(ChartType.HEATMAP, "number", {
      binned: false,
      maxbins: 10,
    });
    expect(result).toEqual({ maxbins: 10 });
  });

  it("should return undefined for HEATMAP without maxbins", () => {
    const result = getBinEncoding(ChartType.HEATMAP, "number", {
      binned: false,
    });
    expect(result).toBeUndefined();
  });

  it("should return undefined when not binned", () => {
    const result = getBinEncoding(ChartType.BAR, "number", {
      binned: false,
      step: 5,
    });
    expect(result).toBeUndefined();
  });

  it("should return undefined for non-numeric data types", () => {
    const result = getBinEncoding(ChartType.BAR, "string", {
      binned: true,
      step: 5,
    });
    expect(result).toBeUndefined();
  });

  it("should return true when binned with no parameters", () => {
    const result = getBinEncoding(ChartType.BAR, "number", {
      binned: true,
    });
    expect(result).toBe(true);
  });

  it("should return step parameter when provided", () => {
    const result = getBinEncoding(ChartType.BAR, "number", {
      binned: true,
      step: 5,
    });
    expect(result).toEqual({ step: 5 });
  });

  it("should return maxbins parameter when provided", () => {
    const result = getBinEncoding(ChartType.BAR, "number", {
      binned: true,
      maxbins: 20,
    });
    expect(result).toEqual({ maxbins: 20 });
  });

  it("should return both step and maxbins when both provided", () => {
    const result = getBinEncoding(ChartType.BAR, "number", {
      binned: true,
      step: 5,
      maxbins: 20,
    });
    expect(result).toEqual({ step: 5, maxbins: 20 });
  });

  it("should return undefined when binValues is undefined", () => {
    const result = getBinEncoding(ChartType.BAR, "number");
    expect(result).toBeUndefined();
  });

  it("should handle zero values for step and maxbins", () => {
    const result = getBinEncoding(ChartType.BAR, "number", {
      binned: true,
      step: 0,
      maxbins: 0,
    });
    expect(result).toEqual({ step: 0, maxbins: 0 });
  });

  it("should work with different chart types", () => {
    const chartTypes = [ChartType.BAR, ChartType.LINE, ChartType.SCATTER];

    for (const chartType of chartTypes) {
      const result = getBinEncoding(chartType, "number", {
        binned: true,
        step: 10,
      });
      expect(result).toEqual({ step: 10 });
    }
  });
});
