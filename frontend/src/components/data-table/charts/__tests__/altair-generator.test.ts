/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  generateAltairChart,
  generateAltairChartSnippet,
} from "../chart-spec/altair-generator";
import type { VegaLiteSpec } from "@/plugins/impl/vega/types";

describe("generateAltairChart", () => {
  it("should generate a basic bar chart", () => {
    const spec: VegaLiteSpec = {
      mark: "bar",
      encoding: {
        x: { field: "category" },
        y: { field: "value" },
      },
    } as VegaLiteSpec;
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(
              field='category'
          ),
          y=alt.Y(
              field='value'
          )
      )"
    `);
  });

  it("should generate a donut chart", () => {
    const spec: VegaLiteSpec = {
      mark: { type: "arc", innerRadius: 100 },
      encoding: {
        theta: { field: "value" },
      },
    } as VegaLiteSpec;
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_arc(innerRadius=100)
      .encode(theta=alt.Theta(
          field='value'
      ))"
    `);
  });

  it("should use the provided datasource variable name", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { field: "x" },
        y: { field: "y" },
      },
    } as VegaLiteSpec;
    const datasource = "my_custom_dataframe";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(my_custom_dataframe)
      .mark_bar()
      .encode(
          x=alt.X(
              field='x'
          ),
          y=alt.Y(
              field='y'
          )
      )"
    `);
  });

  it("should generate a snippet", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { field: "x" },
        y: { field: "y" },
      },
    } as VegaLiteSpec;
    const datasource = "df";

    const result = generateAltairChartSnippet(spec, datasource, "_chart");

    expect(result).toMatchInlineSnapshot(`
      "_chart = (
          alt.Chart(df)
          .mark_bar()
          .encode(
              x=alt.X(
                  field='x'
              ),
              y=alt.Y(
                  field='y'
              )
          )
      )
      _chart"
    `);
  });
});
