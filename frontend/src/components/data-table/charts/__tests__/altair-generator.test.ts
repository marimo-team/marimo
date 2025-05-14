/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  generateAltairChart,
  generateAltairChartSnippet,
  generateTooltipCode,
} from "../chart-spec/altair-generator";
import { ChartType } from "../types";
import type { ChartSchemaType } from "../schemas";
import type { StringFieldDef } from "vega-lite/build/src/channeldef";

describe("generateAltairChart", () => {
  it("should generate a basic bar chart", () => {
    const chartType = ChartType.BAR;
    const spec = {
      general: {
        xColumn: { field: "category" },
        yColumn: { field: "value" },
      },
    } as ChartSchemaType;
    const datasource = "df";

    const result = generateAltairChart(chartType, spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X('category'),
          y=alt.Y('value')
      )"
    `);
  });

  it("should use the correct mark type for different chart types", () => {
    const spec = {
      general: {
        xColumn: { field: "x" },
        yColumn: { field: "y" },
      },
    } as ChartSchemaType;
    const datasource = "data";

    const lineChart = generateAltairChart(
      ChartType.LINE,
      spec,
      datasource,
    ).toCode();
    expect(lineChart).toMatchInlineSnapshot(`
      "alt.Chart(data)
      .mark_line()"
    `);

    const scatterChart = generateAltairChart(
      ChartType.SCATTER,
      spec,
      datasource,
    ).toCode();
    expect(scatterChart).toMatchInlineSnapshot(`
      "alt.Chart(data)
      .mark_point()"
    `);
  });

  it("should handle pie chart type correctly", () => {
    const chartType = ChartType.PIE;
    const spec = {
      general: {
        xColumn: { field: "category" },
        yColumn: { field: "value" },
      },
    } as ChartSchemaType;
    const datasource = "df";

    const result = generateAltairChart(chartType, spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_arc()"
    `);
  });

  it("should use the provided datasource variable name", () => {
    const chartType = ChartType.BAR;
    const spec = {
      general: {
        xColumn: { field: "x" },
        yColumn: { field: "y" },
      },
    } as ChartSchemaType;
    const datasource = "my_custom_dataframe";

    const result = generateAltairChart(chartType, spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(my_custom_dataframe)
      .mark_bar()
      .encode(
          x=alt.X('x'),
          y=alt.Y('y')
      )"
    `);
  });

  it("should generate a snippet", () => {
    const chartType = ChartType.BAR;
    const spec = {
      general: {
        xColumn: { field: "x" },
        yColumn: { field: "y" },
      },
    } as ChartSchemaType;
    const datasource = "df";

    const result = generateAltairChartSnippet(
      chartType,
      spec,
      datasource,
      "_chart",
    );

    expect(result).toMatchInlineSnapshot(`
      "_chart = (
          alt.Chart(df)
          .mark_bar()
          .encode(
              x=alt.X('x'),
              y=alt.Y('y')
          )
      )
      _chart"
    `);
  });
});

describe("generateTooltips", () => {
  it("should generate tooltips with variable keys", () => {
    const tooltips: Array<StringFieldDef<string>> = [
      {
        field: "sepalLength",
        format: ",.2f",
        timeUnit: undefined,
        aggregate: undefined,
      },
      {
        field: "species",
        aggregate: undefined,
        format: undefined,
        timeUnit: undefined,
      },
    ];

    const result = generateTooltipCode(tooltips).toCode();

    expect(result).toMatchInlineSnapshot(`
      "[
          alt.Tooltip(field='sepalLength', format=',.2f'),
          alt.Tooltip(field='species')
      ]"
    `);
  });
});
