/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  generateAltairChart,
  generateAltairChartSnippet,
} from "../chart-spec/altair-generator";
import type { VegaLiteSpec } from "@/plugins/impl/vega/types";

function createSpec(spec: {
  mark: string | Record<string, unknown>;
  encoding: Record<
    string,
    | { field: string; type?: string }
    | Array<{ field: string; tooltip?: Record<string, string> }>
  >;
  resolve?: Record<string, unknown>;
  title?: string;
  width?: number;
  height?: number;
}): VegaLiteSpec {
  return {
    ...spec,
    data: { name: "_unused_" },
  } as VegaLiteSpec;
}

const Mocks = {
  // Simple
  xAxis: {
    field: "category",
  },
  yAxis: {
    field: "value",
  },

  // Full
  xAxisFull: {
    field: "category",
    axis: {
      title: "X Axis",
    },
  },
  yAxisFull: {
    field: "value",
    axis: {
      title: "Y Axis",
    },
  },

  // Color
  colorAxis: {
    field: "color",
  },
  thetaAxis: {
    field: "theta",
    axis: {
      title: "Theta Axis",
    },
  },
  rowAxis: {
    field: "row",
    axis: {
      title: "Row Axis",
    },
  },
  columnAxis: {
    field: "column",
    axis: {
      title: "Column Axis",
    },
  },
  tooltip: {
    field: "tooltip",
    tooltip: {
      title: "Tooltip",
    },
  },
  marks: {
    bar: {
      type: "bar",
      opacity: 0.8,
      color: "red",
    },
    arc: {
      type: "arc",
      innerRadius: 100,
    },
  },
};

describe("generateAltairChart", () => {
  it("should remove undefined values", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: { ...Mocks.xAxis, type: undefined },
      },
    });

    const result = generateAltairChart(spec, "df").toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(x=alt.X(field='category'))"
    `);
  });

  it("should generate a basic bar chart", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value')
      )"
    `);
  });

  it("should generate a donut chart", () => {
    const spec = createSpec({
      mark: Mocks.marks.arc,
      encoding: {
        theta: Mocks.thetaAxis,
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_arc(innerRadius=100)
      .encode(theta=alt.Theta(field='theta', axis={
          'title': 'Theta Axis'
      }))"
    `);
  });

  it("should use the provided datasource variable name", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
      },
    });
    const datasource = "my_custom_dataframe";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(my_custom_dataframe)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value')
      )"
    `);
  });

  it("should generate a snippet", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
      },
    });
    const datasource = "df";

    const result = generateAltairChartSnippet(spec, datasource, "_chart");

    expect(result).toMatchInlineSnapshot(`
      "_chart = (
          alt.Chart(df)
          .mark_bar()
          .encode(
              x=alt.X(field='category'),
              y=alt.Y(field='value')
          )
      )
      _chart"
    `);
  });

  it("should generate a chart with color encoding", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
        color: Mocks.colorAxis,
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value'),
          color=alt.Color(field='color')
      )"
    `);
  });

  it("should generate a chart with tooltip", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
        tooltip: Mocks.tooltip,
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value'),
          tooltip=alt.Tooltip(field='tooltip', tooltip={
              'title': 'Tooltip'
          })
      )"
    `);
  });

  it("should handle array tooltips", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
        tooltip: [Mocks.tooltip, Mocks.tooltip],
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value'),
          tooltip=[
              alt.Tooltip(field='tooltip', tooltip={
                  'title': 'Tooltip'
              }),
              alt.Tooltip(field='tooltip', tooltip={
                  'title': 'Tooltip'
              })
          ]
      )"
    `);
  });

  it("should generate a chart with row and column facets", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
        row: Mocks.rowAxis,
        column: Mocks.columnAxis,
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value'),
          row=alt.Row(field='row', axis={
              'title': 'Row Axis'
          }),
          column=alt.Column(field='column', axis={
              'title': 'Column Axis'
          })
      )"
    `);
  });

  it("should generate a chart with resolve_scale", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
      },
      resolve: {
        axis: {
          x: "independent",
          y: "shared",
        },
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value')
      )
      .resolve_scale(
          x='independent',
          y='shared'
      )"
    `);
  });

  it("should generate a chart with properties", () => {
    const spec = createSpec({
      mark: "bar",
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
      },
      title: "Chart Title",
      width: 600,
      height: 400,
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value')
      )
      .properties(
          title='Chart Title',
          height=400,
          width=600
      )"
    `);
  });

  it("should handle custom mark properties", () => {
    const spec = createSpec({
      mark: Mocks.marks.bar,
      encoding: {
        x: Mocks.xAxis,
        y: Mocks.yAxis,
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar(
          opacity=0.8,
          color='red'
      )
      .encode(
          x=alt.X(field='category'),
          y=alt.Y(field='value')
      )"
    `);
  });

  it("should handle complex x/y axis", () => {
    const spec = createSpec({
      mark: Mocks.marks.bar,
      encoding: {
        x: Mocks.xAxisFull,
        y: Mocks.yAxisFull,
      },
    });
    const datasource = "df";

    const result = generateAltairChart(spec, datasource).toCode();

    expect(result).toMatchInlineSnapshot(`
      "alt.Chart(df)
      .mark_bar(
          opacity=0.8,
          color='red'
      )
      .encode(
          x=alt.X(field='category', axis={
              'title': 'X Axis'
          }),
          y=alt.Y(field='value', axis={
              'title': 'Y Axis'
          })
      )"
    `);
  });
});
