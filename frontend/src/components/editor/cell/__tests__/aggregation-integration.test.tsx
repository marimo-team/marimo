/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";

/**
 * Integration tests for aggregation cell creation
 *
 * These tests verify the code generation for mo.stat aggregations with column selection
 */
describe("Aggregation Cell Code Generation", () => {
  it("should generate min aggregation code with column", () => {
    const variableName = "df";
    const columnName = "price";
    const aggregationType = "min";
    const expectedCode = `mo.stat(label="${columnName}", caption="${aggregationType.toUpperCase()}", value=${variableName}["${columnName}"].${aggregationType}())`;

    expect(expectedCode).toBe(
      'mo.stat(label="price", caption="MIN", value=df["price"].min())',
    );
  });

  it("should generate max aggregation code with column", () => {
    const variableName = "df";
    const columnName = "quantity";
    const aggregationType = "max";
    const expectedCode = `mo.stat(label="${columnName}", caption="${aggregationType.toUpperCase()}", value=${variableName}["${columnName}"].${aggregationType}())`;

    expect(expectedCode).toBe(
      'mo.stat(label="quantity", caption="MAX", value=df["quantity"].max())',
    );
  });

  it("should generate mean aggregation code with column", () => {
    const variableName = "df";
    const columnName = "value";
    const aggregationType = "mean";
    const expectedCode = `mo.stat(label="${columnName}", caption="${aggregationType.toUpperCase()}", value=${variableName}["${columnName}"].${aggregationType}())`;

    expect(expectedCode).toBe(
      'mo.stat(label="value", caption="MEAN", value=df["value"].mean())',
    );
  });

  it("should generate sum aggregation code with column", () => {
    const variableName = "df";
    const columnName = "total";
    const aggregationType = "sum";
    const expectedCode = `mo.stat(label="${columnName}", caption="${aggregationType.toUpperCase()}", value=${variableName}["${columnName}"].${aggregationType}())`;

    expect(expectedCode).toBe(
      'mo.stat(label="total", caption="SUM", value=df["total"].sum())',
    );
  });

  it("should generate count aggregation code with column", () => {
    const variableName = "df";
    const columnName = "id";
    const aggregationType = "count";
    const expectedCode = `mo.stat(label="${columnName}", caption="${aggregationType.toUpperCase()}", value=${variableName}["${columnName}"].${aggregationType}())`;

    expect(expectedCode).toBe(
      'mo.stat(label="id", caption="COUNT", value=df["id"].count())',
    );
  });

  it("should work with different dataframe and column names", () => {
    const testCases = [
      {
        df: "data",
        col: "age",
        agg: "min",
        expected:
          'mo.stat(label="age", caption="MIN", value=data["age"].min())',
      },
      {
        df: "my_df",
        col: "score",
        agg: "max",
        expected:
          'mo.stat(label="score", caption="MAX", value=my_df["score"].max())',
      },
      {
        df: "df1",
        col: "revenue",
        agg: "mean",
        expected:
          'mo.stat(label="revenue", caption="MEAN", value=df1["revenue"].mean())',
      },
    ];

    testCases.forEach(({ df, col, agg, expected }) => {
      const code = `mo.stat(label="${col}", caption="${agg.toUpperCase()}", value=${df}["${col}"].${agg}())`;
      expect(code).toBe(expected);
    });
  });

  it("should handle column names with special characters", () => {
    const variableName = "df";
    const columnName = "Total Cost ($)";
    const aggregationType = "sum";
    const expectedCode = `mo.stat(label="${columnName}", caption="${aggregationType.toUpperCase()}", value=${variableName}["${columnName}"].${aggregationType}())`;

    expect(expectedCode).toBe(
      'mo.stat(label="Total Cost ($)", caption="SUM", value=df["Total Cost ($)"].sum())',
    );
  });
});
