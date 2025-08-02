/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { ColumnChartSpecModel } from "../column-summary/chart-spec-model";
import type {
  BinValues,
  ColumnHeaderStats,
  ColumnName,
  FieldTypes,
  ValueCounts,
} from "../types";

// Mock the runtime config
vi.mock("@/core/runtime/config", () => ({
  asRemoteURL: vi.fn((path: string) => {
    if (path.startsWith("http")) {
      return new URL(path);
    }
    return new URL(path, "http://localhost:8080/");
  }),
}));

describe("ColumnChartSpecModel", () => {
  const mockData = "http://example.com/data.json";
  const mockFieldTypes: FieldTypes = {
    date: "date",
    number: "number",
    integer: "integer",
    boolean: "boolean",
    string: "string",
    datetime: "datetime",
  };
  const mockStats: Record<ColumnName, Partial<ColumnHeaderStats>> = {
    date: { min: "2023-01-01", max: "2023-12-31" },
    number: { min: 0, max: 100 },
    integer: { min: 1, max: 10 },
    boolean: { true: 5, false: 5, nulls: 10 },
    string: { unique: 20 },
    datetime: { nulls: 10 },
  };
  const mockBinValues: Record<ColumnName, BinValues> = {
    number: [
      { bin_start: 0, bin_end: 10, count: 10 },
      { bin_start: 10, bin_end: 20, count: 20 },
    ],
    integer: [
      { bin_start: 0, bin_end: 10, count: 10 },
      { bin_start: 10, bin_end: 20, count: 20 },
    ],
    datetime: [
      { bin_start: "2023-01-01", bin_end: "2023-01-02", count: 10 },
      { bin_start: "2023-01-02", bin_end: "2023-01-03", count: 20 },
    ],
  };
  const mockValueCounts: Record<ColumnName, ValueCounts> = {
    string: [
      { value: "A", count: 10 },
      { value: "B", count: 30 },
    ],
  };

  it("should create an instance", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true },
    );
    expect(model).toBeInstanceOf(ColumnChartSpecModel);
  });

  it("should return EMPTY for static EMPTY property", () => {
    expect(ColumnChartSpecModel.EMPTY).toBeInstanceOf(ColumnChartSpecModel);
    expect(ColumnChartSpecModel.EMPTY.stats).toEqual({});
  });

  it("should return header summary with spec when includeCharts is true", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true },
    );
    const dateSummary = model.getHeaderSummary("date");
    expect(dateSummary.stats).toEqual(mockStats.date);
    expect(dateSummary.type).toBe("date");
    expect(dateSummary.spec).toBeDefined();
  });

  it("should return header summary without spec when includeCharts is false", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: false },
    );
    const numberSummary = model.getHeaderSummary("number");
    expect(numberSummary.stats).toEqual(mockStats.number);
    expect(numberSummary.type).toBe("number");
    expect(numberSummary.spec).toBeUndefined();
  });

  it("should return null spec for string and unknown types", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true },
    );
    const stringSummary = model.getHeaderSummary("string");
    expect(stringSummary.spec).toBeNull();
  });

  it("should handle special characters in column names", () => {
    const specialFieldTypes: FieldTypes = {
      "column.with[special:chars]": "time",
    };
    const specialStats: Record<ColumnName, Partial<ColumnHeaderStats>> = {
      "column.with[special:chars]": { min: "2023-01-01", max: "2023-12-31" },
    };
    const model = new ColumnChartSpecModel(
      mockData,
      specialFieldTypes,
      specialStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true },
    );
    const summary = model.getHeaderSummary("column.with[special:chars]");
    expect(summary.spec).toBeDefined();
    expect(
      // @ts-expect-error layer should be available
      (summary.spec?.layer[0].encoding?.x as { field: string })?.field,
    ).toBe("column\\.with\\[special\\:chars\\]");
  });

  it("should expect bin values to be used for number and integer columns when feat flag is true", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true, usePreComputedValues: true },
    );
    const summary = model.getHeaderSummary("number");
    expect(summary.spec).toBeDefined();
    // @ts-expect-error data.values should be available
    expect(summary.spec?.data?.values).toEqual(mockBinValues.number);

    // @ts-expect-error layer should be available
    const layer = summary.spec?.layer[0];

    expect(summary.spec).toMatchSnapshot();

    // field names should be bin_start and bin_end
    expect(layer.encoding?.x?.field).toBe("bin_start");
    expect(layer.encoding?.x2?.field).toBe("bin_end");

    const summary2 = model.getHeaderSummary("integer");
    expect(summary2.spec).toBeDefined();
    // @ts-expect-error data.values should be available
    expect(summary2.spec?.data?.values).toEqual(mockBinValues.integer);
  });

  it("should handle datetime bin values when feat flag is true", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true, usePreComputedValues: true },
    );

    const summary = model.getHeaderSummary("datetime");
    expect(summary.spec).toBeDefined();
    // @ts-expect-error data.values should be available
    expect(summary.spec?.data?.values).toEqual(mockBinValues.datetime);

    // Expect hconcat since there are nulls
    // @ts-expect-error hconcat should be available
    expect(summary.spec?.hconcat).toBeDefined();
    expect(summary.spec).toMatchSnapshot();

    // Test again without the nulls
    const mockStats2 = {
      ...mockStats,
      datetime: { min: "2023-01-01", max: "2023-12-31" },
    };
    const model2 = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats2,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true, usePreComputedValues: true },
    );
    const summary2 = model2.getHeaderSummary("datetime");
    expect(summary2.spec).toBeDefined();

    // No hconcat since there are no nulls
    // @ts-expect-error hconcat should be available
    expect(summary2.spec?.hconcat).toBeUndefined();
  });

  it("should handle boolean stats when feat flag is true", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true, usePreComputedValues: true },
    );
    const summary = model.getHeaderSummary("boolean");
    expect(summary.spec).toBeDefined();
    // @ts-expect-error data.values should be available
    expect(summary.spec?.data?.values).toEqual([
      { value: "true", count: 5 },
      { value: "false", count: 5 },
      { value: "null", count: 10 },
    ]);

    // Snapshot
    expect(summary.spec).toMatchSnapshot();
  });

  it("should handle string value counts when feat flag is true", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockStats,
      mockBinValues,
      mockValueCounts,
      { includeCharts: true, usePreComputedValues: true },
    );
    const summary = model.getHeaderSummary("string");
    expect(summary.spec).toBeDefined();
    // @ts-expect-error data.values should be available
    expect(summary.spec?.data?.values).toEqual([
      { value: "A", count: 10, xStart: 0, xEnd: 10, xMid: 5, proportion: 0.25 },
      {
        value: "B",
        count: 30,
        xStart: 10,
        xEnd: 40,
        xMid: 25,
        proportion: 0.75,
      },
    ]);

    // Snapshot
    expect(summary.spec).toMatchSnapshot();
  });

  describe("snapshot", () => {
    const fieldTypes: FieldTypes = {
      ...mockFieldTypes,
      a: "number",
    };

    it("url data", () => {
      const model = new ColumnChartSpecModel(
        mockData,
        fieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("date").spec).toMatchSnapshot();
    });

    it("csv data", () => {
      const model = new ColumnChartSpecModel(
        `data:text/csv;base64,${btoa("a,b,c\n1,2,3\n4,5,6")}`,
        fieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("a").spec).toMatchSnapshot();
    });

    it("csv string", () => {
      const model = new ColumnChartSpecModel(
        "a,b,c\n1,2,3\n4,5,6",
        fieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("a").spec).toMatchSnapshot();
    });

    it("array", () => {
      const model = new ColumnChartSpecModel(
        ["a", "b", "c"],
        fieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("a").spec).toMatchSnapshot();
    });
  });

  describe("file URL handling", () => {
    it("should handle marimo file URLs with ./@file prefix", () => {
      const model = new ColumnChartSpecModel(
        "./@file/data.csv",
        mockFieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );

      const summary = model.getHeaderSummary("date");
      expect(summary.spec).toBeDefined();
      // @ts-expect-error accessing internal dataSpec
      expect(model.dataSpec?.url).toBe("http://localhost:8080/@file/data.csv");
    });

    it("should handle marimo file URLs with /@file prefix", () => {
      const model = new ColumnChartSpecModel(
        "/@file/data.csv",
        mockFieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );

      const summary = model.getHeaderSummary("date");
      expect(summary.spec).toBeDefined();
      // @ts-expect-error accessing internal dataSpec
      expect(model.dataSpec?.url).toBe("http://localhost:8080/@file/data.csv");
    });

    it("should handle absolute HTTP URLs", () => {
      const model = new ColumnChartSpecModel(
        "https://external.com/data.csv",
        mockFieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );

      const summary = model.getHeaderSummary("date");
      expect(summary.spec).toBeDefined();
      // @ts-expect-error accessing internal dataSpec
      expect(model.dataSpec?.url).toBeUndefined();
    });

    it("should handle data URLs", () => {
      const dataUrl = "data:text/csv;base64,YSxiLGMKMSwyLDMKNCw1LDY=";
      const model = new ColumnChartSpecModel(
        dataUrl,
        mockFieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );

      const summary = model.getHeaderSummary("date");
      expect(summary.spec).toBeDefined();
      // Data URLs should be handled by parseCsvData, not as URL
      // @ts-expect-error accessing internal dataSpec
      expect(model.dataSpec?.values).toBeDefined();
    });

    it("should handle CSV string data", () => {
      const csvString = "a,b,c\n1,2,3\n4,5,6";
      const model = new ColumnChartSpecModel(
        csvString,
        mockFieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );

      const summary = model.getHeaderSummary("date");
      expect(summary.spec).toBeDefined();
      // CSV strings should be parsed, not treated as URLs
      // @ts-expect-error accessing internal dataSpec
      expect(model.dataSpec?.values).toBeDefined();
    });

    it("should handle arrow data", () => {
      const arrowData = "ARROW1\n";
      const model = new ColumnChartSpecModel(
        `data:text/plain;base64,${btoa(arrowData)}`,
        mockFieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );
      const spec = model.getHeaderSummary("date").spec;
      expect(spec).toMatchSnapshot();
      expect(spec?.data?.format?.type).toBe("arrow");
      // @ts-expect-error accessing internal dataSpec
      expect(model.dataSpec?.values).toBeDefined();
    });

    it("should handle array data", () => {
      const arrayData = [
        { a: 1, b: 2, c: 3 },
        { a: 4, b: 5, c: 6 },
      ];
      const model = new ColumnChartSpecModel(
        arrayData,
        mockFieldTypes,
        mockStats,
        mockBinValues,
        mockValueCounts,
        { includeCharts: true },
      );

      const summary = model.getHeaderSummary("date");
      expect(summary.spec).toBeDefined();
      // @ts-expect-error accessing internal dataSpec
      expect(model.dataSpec?.values).toEqual(arrayData);
    });
  });
});
