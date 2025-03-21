/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { ColumnChartSpecModel } from "../chart-spec-model";
import type { ColumnHeaderSummary, FieldTypes } from "../types";

describe("ColumnChartSpecModel", () => {
  const mockData = "http://example.com/data.json";
  const mockFieldTypes: FieldTypes = {
    date: "date",
    number: "number",
    integer: "integer",
    boolean: "boolean",
    string: "string",
  };
  const mockSummaries: ColumnHeaderSummary[] = [
    { column: "date", min: "2023-01-01", max: "2023-12-31" },
    { column: "number", min: 0, max: 100 },
    { column: "integer", min: 1, max: 10 },
    { column: "boolean", true: 5, false: 5 },
    { column: "string", unique: 20 },
  ];

  it("should create an instance", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockSummaries,
      { includeCharts: true },
    );
    expect(model).toBeInstanceOf(ColumnChartSpecModel);
  });

  it("should return EMPTY for static EMPTY property", () => {
    expect(ColumnChartSpecModel.EMPTY).toBeInstanceOf(ColumnChartSpecModel);
    expect(ColumnChartSpecModel.EMPTY.summaries).toEqual([]);
  });

  it("should return header summary with spec when includeCharts is true", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockSummaries,
      { includeCharts: true },
    );
    const dateSummary = model.getHeaderSummary("date");
    expect(dateSummary.summary).toEqual(mockSummaries[0]);
    expect(dateSummary.type).toBe("date");
    expect(dateSummary.spec).toBeDefined();
  });

  it("should return header summary without spec when includeCharts is false", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockSummaries,
      { includeCharts: false },
    );
    const numberSummary = model.getHeaderSummary("number");
    expect(numberSummary.summary).toEqual(mockSummaries[1]);
    expect(numberSummary.type).toBe("number");
    expect(numberSummary.spec).toBeUndefined();
  });

  it("should return null spec for string and unknown types", () => {
    const model = new ColumnChartSpecModel(
      mockData,
      mockFieldTypes,
      mockSummaries,
      { includeCharts: true },
    );
    const stringSummary = model.getHeaderSummary("string");
    expect(stringSummary.spec).toBeNull();
  });

  it("should handle special characters in column names", () => {
    const specialFieldTypes: FieldTypes = {
      "column.with[special:chars]": "number",
    };
    const specialSummaries: ColumnHeaderSummary[] = [
      { column: "column.with[special:chars]", min: 0, max: 100 },
    ];
    const model = new ColumnChartSpecModel(
      mockData,
      specialFieldTypes,
      specialSummaries,
      { includeCharts: true },
    );
    const summary = model.getHeaderSummary("column.with[special:chars]");
    expect(summary.spec).toBeDefined();
    // @ts-expect-error numerical charts have 'layer' property
    expect((summary.spec?.layer[0].encoding?.x as { field: string })?.field).toBe(
      "column\\.with\\[special\\:chars\\]",
    );
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
        mockSummaries,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("date").spec).toMatchSnapshot();
    });

    it("csv data", () => {
      const model = new ColumnChartSpecModel(
        `data:text/csv;base64,${btoa("a,b,c\n1,2,3\n4,5,6")}`,
        fieldTypes,
        mockSummaries,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("a").spec).toMatchSnapshot();
    });

    it("csv string", () => {
      const model = new ColumnChartSpecModel(
        "a,b,c\n1,2,3\n4,5,6",
        fieldTypes,
        mockSummaries,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("a").spec).toMatchSnapshot();
    });

    it("array", () => {
      const model = new ColumnChartSpecModel(
        ["a", "b", "c"],
        fieldTypes,
        mockSummaries,
        { includeCharts: true },
      );
      expect(model.getHeaderSummary("a").spec).toMatchSnapshot();
    });
  });
});
