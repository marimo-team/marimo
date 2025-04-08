/* Copyright 2024 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import { createVegaSpec } from "../chart-spec";
import { ChartType } from "../storage";
import { DEFAULT_AGGREGATION, NONE_GROUP_BY } from "../chart-schemas";
import type { z } from "zod";
import type { ChartSchema } from "../chart-schemas";

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
        agg: DEFAULT_AGGREGATION as "default",
      },
    },
  });

  describe("Bar Chart", () => {
    it("should create a basic bar chart spec", () => {
      const formValues = createBasicFormValues();
      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(spec).toMatchSnapshot();
    });

    it("should create a bar chart with custom axis labels", () => {
      const formValues = {
        ...createBasicFormValues(),
        xAxis: { label: "Categories" },
        yAxis: { label: "Values" },
      };

      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(spec).toMatchSnapshot();
    });

    it("should create a horizontal bar chart", () => {
      const formValues = {
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

      expect(spec).toMatchSnapshot();
    });

    it("should create a stacked bar chart with grouping", () => {
      const formValues = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          groupByColumn: {
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

      expect(spec).toMatchSnapshot();
    });

    it("should create a bar chart with aggregation", () => {
      const formValues = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          yColumn: {
            field: "value",
            type: "number" as const,
            agg: "sum" as const,
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

      expect(spec).toMatchSnapshot();
    });

    it("should create a bar chart with tooltips", () => {
      const formValues = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          tooltips: [
            { field: "category", type: "string" as const },
            { field: "value", type: "number" as const },
            { field: "group", type: "string" as const },
          ],
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

      expect(spec).toMatchSnapshot();
    });
  });

  describe("Line Chart", () => {
    it("should create a basic line chart spec", () => {
      const formValues = createBasicFormValues();
      const spec = createVegaSpec(
        ChartType.LINE,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(spec).toMatchSnapshot();
    });

    it("should create a line chart with grouping", () => {
      const formValues = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          groupByColumn: {
            field: "group",
            type: "string" as const,
          },
        },
      };

      const spec = createVegaSpec(
        ChartType.LINE,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(spec).toMatchSnapshot();
    });
  });

  describe("Pie Chart", () => {
    it("should create a basic pie chart spec", () => {
      const formValues = createBasicFormValues();
      const spec = createVegaSpec(
        ChartType.PIE,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(spec).toMatchSnapshot();
    });

    it("should create a pie chart with tooltips", () => {
      const formValues = {
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

      expect(spec).toMatchSnapshot();
    });
  });

  describe("Scatter Chart", () => {
    it("should create a basic scatter chart spec", () => {
      const formValues = createBasicFormValues();
      const spec = createVegaSpec(
        ChartType.SCATTER,
        sampleData,
        formValues,
        "light",
        width,
        height,
      );

      expect(spec).toMatchSnapshot();
    });

    it("should create a scatter chart with grouping", () => {
      const formValues = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          groupByColumn: {
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

      expect(spec).toMatchSnapshot();
    });
  });

  describe("Theme variations", () => {
    it("should create a chart with dark theme", () => {
      const formValues = createBasicFormValues();
      const spec = createVegaSpec(
        ChartType.BAR,
        sampleData,
        formValues,
        "dark",
        width,
        height,
      );

      expect(spec).toMatchSnapshot();
    });
  });

  describe("Edge cases", () => {
    it("should handle missing xColumn field", () => {
      const formValues = {
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

      expect(spec).toMatchSnapshot();
    });

    it("should handle missing yColumn field", () => {
      const formValues = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          yColumn: {
            field: undefined,
            type: "number" as const,
            agg: DEFAULT_AGGREGATION as "default",
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

      expect(spec).toMatchSnapshot();
    });

    it("should handle NONE_GROUP_BY for groupByColumn", () => {
      const formValues = {
        ...createBasicFormValues(),
        general: {
          ...createBasicFormValues().general,
          groupByColumn: {
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

      expect(spec).toMatchSnapshot();
    });
  });
});
