/* Copyright 2024 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import {
  createSpecWithoutData,
  augmentSpecWithData,
  X_AXIS_REQUIRED,
  Y_AXIS_REQUIRED,
} from "../chart-spec/spec";
import type { ChartSchemaType } from "../schemas";
import { NONE_AGGREGATION, ChartType } from "../types";
import type { TopLevelSpec } from "vega-lite/build/src/spec";

describe("create vega spec", () => {
  // Sample data for testing
  const sampleData = [
    { category: "A", value: 10, group: "Group 1" },
    { category: "B", value: 20, group: "Group 1" },
    { category: "C", value: 15, group: "Group 1" },
    { category: "A", value: 5, group: "Group 2" },
    { category: "B", value: 10, group: "Group 2" },
    { category: "C", value: 25, group: "Group 2" },
  ];

  // Helper function to create basic form values
  const createBasicFormValues = (): ChartSchemaType => ({
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

  it("should create and augment a spec", () => {
    const spec = createSpecWithoutData(
      ChartType.BAR,
      createBasicFormValues(),
      "light",
      400,
      300,
    );
    expect(spec).toMatchSnapshot();
    expect(typeof spec !== "string").toBe(true); // Not error message
    expect((spec as TopLevelSpec).data).toEqual({ values: [] });

    // Augment the spec with data
    const augmentedSpec = augmentSpecWithData(spec as TopLevelSpec, sampleData);
    expect(augmentedSpec.data).toEqual({ values: sampleData });
  });

  it("should return an error message if the spec is invalid", () => {
    const formValues = createBasicFormValues();
    formValues.general!.xColumn!.field = undefined;

    const spec = createSpecWithoutData(
      ChartType.BAR,
      formValues,
      "light",
      400,
      300,
    );
    expect(spec).toEqual(X_AXIS_REQUIRED);

    // Undefined yColumn
    const formValues2 = createBasicFormValues();
    formValues2.general!.yColumn!.field = undefined;
    const spec2 = createSpecWithoutData(
      ChartType.BAR,
      formValues2,
      "light",
      400,
      300,
    );
    expect(spec2).toEqual(Y_AXIS_REQUIRED);
  });
});
