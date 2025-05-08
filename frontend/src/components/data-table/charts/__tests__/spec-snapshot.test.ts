/* Copyright 2024 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import { createVegaSpec } from "../spec";
import { DEFAULT_BIN_VALUE, NONE_GROUP_BY } from "../schemas";
import type { z } from "zod";
import type { ChartSchema, ChartSchemaType } from "../schemas";
import { NONE_AGGREGATION, ChartType } from "../types";

describe("createVegaSpec", () => {
  // Sample data for testing
  const sampleData = [
    { category: "A", value: 10, group: "Group 1" },
    { category: "B", value: 20, group: "Group 1" },
    { category: "C", value: 15, group: "Group 1" },
    { category: "A", value: 5, group: "Group 2" },
    { category: "B", value: 10, group: "Group 2" },
    { category: "C", value: 25, group: "Group 2" },
  ];

  // Common test parameters
  const width = 400;
  const height = 300;

  // Helper function to create basic form values
  const createBasicFormValues = (): z.infer<typeof ChartSchema> => ({
    general: {
      title: "Test Chart",
      xColumn: {
        field: "category",
        type: "string" as const,
      },
      yColumn: {
        field: "value",
        type: "number" as const,
        aggregate: NONE_AGGREGATION,
      },
    },
  });

  describe("Bar Chart", () => {
    it("should create a horizontal bar chart", () => {
      const formValues: ChartSchemaType = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          horizontal: true,
        },
      };

      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });

    it("should create a stacked bar chart with grouping", () => {
      const formValues: ChartSchemaType = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          colorByColumn: {
            field: "group",
            type: "string" as const,
          },
          stacking: true,
        },
      };

      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });
  });

  it("should create a bar chart with binning", () => {
    const formValues: ChartSchemaType = {
      ...createBasicFormValues(),
      xAxis: { bin: { binned: true, step: DEFAULT_BIN_VALUE } },
    };

    const spec = createVegaSpec(
      ChartType.BAR,
      sampleData,
      formValues,
      "light",
      width,
      height,
    );

    expect(removeUndefined(spec)).toMatchSnapshot();
  });

  describe("Line Chart", () => {
    it("should create a basic line chart spec", () => {
      const formValues: ChartSchemaType = createBasicFormValues();
      const spec = createVegaSpec(
        ChartType.LINE,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });
  });

  describe("Pie Chart", () => {
    it("should create a pie chart with tooltips", () => {
      const formValues: ChartSchemaType = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          tooltips: [
            { field: "category", type: "string" as const },
            { field: "value", type: "number" as const },
          ],
        },
      };

      const spec = createVegaSpec(
        ChartType.PIE,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });
  });

  describe("Scatter Chart", () => {
    it("should create a scatter chart with grouping", () => {
      const formValues: ChartSchemaType = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          colorByColumn: {
            field: "group",
            type: "string" as const,
          },
        },
      };

      const spec = createVegaSpec(
        ChartType.SCATTER,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });
  });

  describe("Theme variations", () => {
    it("should create a chart with dark theme", () => {
      const formValues: ChartSchemaType = createBasicFormValues();
      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "dark",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });
  });

  describe("Edge cases", () => {
    it("should handle missing xColumn field", () => {
      const formValues: ChartSchemaType = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          xColumn: {
            field: undefined,
            type: "string" as const,
          },
        },
      };

      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });

    it("should handle missing yColumn field", () => {
      const formValues: ChartSchemaType = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          yColumn: {
            field: undefined,
            type: "number" as const,
            aggregate: NONE_AGGREGATION,
          },
        },
      };

      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });

    it("should handle NONE_GROUP_BY for groupByColumn", () => {
      const formValues: ChartSchemaType = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          colorByColumn: {
            field: NONE_GROUP_BY,
            type: "string" as const,
          },
          stacking: true,
        },
      };

      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(removeUndefined(spec)).toMatchSnapshot();
    });
  });
});

function removeUndefined<T>(obj: T): T {
  if (typeof obj === "object" && obj !== null && !Array.isArray(obj)) {
    const result = {} as T;
    for (const key in obj) {
      if (obj[key] !== undefined) {
        result[key] = removeUndefined(obj[key]);
      }
    }
    return result;
  }
  return obj;
}
