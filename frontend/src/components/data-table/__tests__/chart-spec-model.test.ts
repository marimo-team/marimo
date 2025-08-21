/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { ColumnChartSpecModel } from "../column-summary/chart-spec-model";
import { calculateBinStep } from "../column-summary/utils";
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

describe("calculateBinStep", () => {
  describe("numeric data", () => {
    it("should calculate proper step for numeric data", () => {
      const values: BinValues = [
        { bin_start: 0, bin_end: 10, count: 5 },
        { bin_start: 10, bin_end: 20, count: 8 },
        { bin_start: 20, bin_end: 30, count: 12 },
        { bin_start: 30, bin_end: 40, count: 6 },
        { bin_start: 40, bin_end: 50, count: 3 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(10); // Range is 50, 5 bins, so 50/5 = 10
    });

    it("should handle zero range", () => {
      const values: BinValues = [
        { bin_start: 5, bin_end: 5, count: 10 },
        { bin_start: 5, bin_end: 5, count: 15 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(1); // Minimum step size when range is 0
    });

    it("should handle very small ranges", () => {
      const values: BinValues = [
        { bin_start: 0.001, bin_end: 0.002, count: 5 },
        { bin_start: 0.002, bin_end: 0.003, count: 8 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(1); // Minimum step size when calculated step is too small
    });

    it("should handle very large ranges", () => {
      const values: BinValues = [
        { bin_start: 0, bin_end: 1_000_000, count: 5 },
        { bin_start: 1_000_000, bin_end: 2_000_000, count: 8 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(1_000_000); // Range is 2_000_000, 2 bins, so 2_000_000/2 = 1_000_000
    });

    it("should use actual number of bins", () => {
      const values: BinValues = [
        { bin_start: 0, bin_end: 10, count: 5 },
        { bin_start: 10, bin_end: 20, count: 8 },
        { bin_start: 20, bin_end: 30, count: 12 },
        { bin_start: 30, bin_end: 40, count: 6 },
        { bin_start: 40, bin_end: 50, count: 3 },
        { bin_start: 50, bin_end: 60, count: 7 },
        { bin_start: 60, bin_end: 70, count: 9 },
        { bin_start: 70, bin_end: 80, count: 4 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(10); // Range is 80, 8 bins, so 80/8 = 10
    });
  });

  describe("string date data", () => {
    it("should calculate proper step for string dates", () => {
      const values: BinValues = [
        { bin_start: "2023-01-01", bin_end: "2023-01-02", count: 5 },
        { bin_start: "2023-01-02", bin_end: "2023-01-03", count: 8 },
        { bin_start: "2023-01-03", bin_end: "2023-01-04", count: 12 },
        { bin_start: "2023-01-04", bin_end: "2023-01-05", count: 6 },
      ];

      const step = calculateBinStep(values);
      const oneDayMs = 24 * 60 * 60 * 1000;
      expect(step).toBe(oneDayMs); // 4 days range, 4 bins, so 4 days / 4 = 1 day in ms
    });

    it("should handle datetime strings", () => {
      const values: BinValues = [
        {
          bin_start: "2023-01-01 00:00:00",
          bin_end: "2023-01-01 01:00:00",
          count: 5,
        },
        {
          bin_start: "2023-01-01 01:00:00",
          bin_end: "2023-01-01 02:00:00",
          count: 8,
        },
        {
          bin_start: "2023-01-01 02:00:00",
          bin_end: "2023-01-01 03:00:00",
          count: 12,
        },
      ];

      const step = calculateBinStep(values);
      const oneHourMs = 60 * 60 * 1000;
      expect(step).toBe(oneHourMs); // 3 hours range, 3 bins, so 3 hours / 3 = 1 hour in ms
    });

    it("should handle ISO datetime strings", () => {
      const values: BinValues = [
        {
          bin_start: "2023-01-01T00:00:00Z",
          bin_end: "2023-01-01T01:00:00Z",
          count: 5,
        },
        {
          bin_start: "2023-01-01T01:00:00Z",
          bin_end: "2023-01-01T02:00:00Z",
          count: 8,
        },
      ];

      const step = calculateBinStep(values);
      const oneHourMs = 60 * 60 * 1000;
      expect(step).toBe(oneHourMs); // 2 hours range, 2 bins, so 2 hours / 2 = 1 hour in ms
    });
  });

  describe("Date object data", () => {
    it("should calculate proper step for Date objects", () => {
      const values: BinValues = [
        {
          bin_start: new Date("2023-01-01"),
          bin_end: new Date("2023-01-02"),
          count: 5,
        },
        {
          bin_start: new Date("2023-01-02"),
          bin_end: new Date("2023-01-03"),
          count: 8,
        },
        {
          bin_start: new Date("2023-01-03"),
          bin_end: new Date("2023-01-04"),
          count: 12,
        },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(24 * 60 * 60 * 1000); // 3 days range, 3 bins, so 3 days / 3 = 1 day in ms
    });
  });

  describe("edge cases", () => {
    it("should handle empty array", () => {
      const values: BinValues = [];
      const step = calculateBinStep(values);
      expect(step).toBe(1);
    });

    it("should handle array with only null values", () => {
      const values: BinValues = [
        { bin_start: null, bin_end: null, count: 5 },
        { bin_start: null, bin_end: null, count: 8 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(1);
    });

    it("should handle mixed null and valid values", () => {
      const values: BinValues = [
        { bin_start: null, bin_end: null, count: 5 },
        { bin_start: 0, bin_end: 10, count: 8 },
        { bin_start: 10, bin_end: 20, count: 12 },
        { bin_start: null, bin_end: null, count: 6 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(10); // Range is 20, 2 valid bins, so 20/2 = 10
    });

    it("should handle single valid value", () => {
      const values: BinValues = [{ bin_start: 5, bin_end: 15, count: 10 }];

      const step = calculateBinStep(values);
      expect(step).toBe(10); // Range is 10, 1 bin, so 10/1 = 10
    });

    it("should handle very small step sizes", () => {
      const values: BinValues = [
        { bin_start: 0.0001, bin_end: 0.0002, count: 5 },
        { bin_start: 0.0002, bin_end: 0.0003, count: 8 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(1); // Minimum step size when calculated step is too small
    });

    it("should handle very large step sizes", () => {
      const values: BinValues = [
        { bin_start: 0, bin_end: 1_000_000, count: 5 },
        { bin_start: 1_000_000, bin_end: 2_000_000, count: 8 },
      ];

      const step = calculateBinStep(values);
      expect(step).toBe(1_000_000); // Range is 2_000_000, 2 bins, so 2_000_000/2 = 1_000_000
    });

    it("should handle single bin", () => {
      const values: BinValues = [{ bin_start: 0, bin_end: 10, count: 5 }];

      const step = calculateBinStep(values);
      expect(step).toBe(10); // Range is 10, 1 bin, so 10/1 = 10
    });

    it("should handle many bins", () => {
      const values: BinValues = Array.from({ length: 100 }, (_, i) => ({
        bin_start: i * 10,
        bin_end: (i + 1) * 10,
        count: Math.floor(Math.random() * 20) + 1,
      }));

      const step = calculateBinStep(values);
      expect(step).toBe(10); // Range is 1000, 100 bins, so 1000/100 = 10
    });
  });

  describe("data type consistency", () => {
    it("should handle consistent numeric types", () => {
      const values: BinValues = [
        { bin_start: 0, bin_end: 10, count: 5 },
        { bin_start: 10, bin_end: 20, count: 8 },
        { bin_start: 20, bin_end: 30, count: 12 },
      ];

      const step = calculateBinStep(values);
      expect(typeof step).toBe("number");
      expect(step).toBe(10); // Range is 30, 3 bins, so 30/3 = 10
    });

    it("should handle consistent string date types", () => {
      const values: BinValues = [
        { bin_start: "2023-01-01", bin_end: "2023-01-02", count: 5 },
        { bin_start: "2023-01-02", bin_end: "2023-01-03", count: 8 },
      ];

      const step = calculateBinStep(values);
      expect(typeof step).toBe("number");
      expect(step).toBe(24 * 60 * 60 * 1000); // 2 days range, 2 bins, so 2 days / 2 = 1 day in ms
    });

    it("should handle consistent Date object types", () => {
      const values: BinValues = [
        {
          bin_start: new Date("2023-01-01"),
          bin_end: new Date("2023-01-02"),
          count: 5,
        },
        {
          bin_start: new Date("2023-01-02"),
          bin_end: new Date("2023-01-03"),
          count: 8,
        },
      ];

      const step = calculateBinStep(values);
      expect(typeof step).toBe("number");
      expect(step).toBe(24 * 60 * 60 * 1000); // 2 days range, 2 bins, so 2 days / 2 = 1 day in ms
    });
  });
});
