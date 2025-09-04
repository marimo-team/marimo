/* Copyright 2024 Marimo. All rights reserved. */

import type { VegaLiteSpec } from "@/plugins/impl/vega/types";

export const BAR_CHART: VegaLiteSpec = {
  data: {
    values: [
      { a: "A", b: 28 },
      { a: "B", b: 55 },
      { a: "C", b: 43 },
      { a: "D", b: 91 },
      { a: "E", b: 81 },
      { a: "F", b: 53 },
      { a: "G", b: 19 },
      { a: "H", b: 87 },
      { a: "I", b: 52 },
    ],
  },
  mark: "bar",
  encoding: {
    x: { field: "a", type: "ordinal" },
    y: { field: "b", type: "quantitative" },
  },
};

export const LINE_CHART: VegaLiteSpec = {
  data: {
    values: [
      { a: "A", b: 28 },
      { a: "B", b: 55 },
      { a: "C", b: 43 },
      { a: "D", b: 91 },
      { a: "E", b: 81 },
      { a: "F", b: 53 },
      { a: "G", b: 19 },
      { a: "H", b: 87 },
      { a: "I", b: 52 },
    ],
  },
  mark: "line",
  encoding: {
    x: { field: "a", type: "ordinal" },
    y: { field: "b", type: "quantitative" },
  },
};

export const POINT_CHART: VegaLiteSpec = {
  data: {
    url: "https://raw.githubusercontent.com/vega/vega/main/docs/data/cars.json",
  },
  mark: "point",
  encoding: {
    x: { field: "Horsepower", type: "quantitative" },
    y: { field: "Miles_per_Gallon", type: "quantitative" },
  },
};

export const AREA_CHART: VegaLiteSpec = {
  data: {
    url: "https://raw.githubusercontent.com/vega/vega/main/docs/data/unemployment-across-industries.json",
  },
  mark: "area",
  encoding: {
    x: {
      timeUnit: "yearmonth",
      field: "date",
      type: "temporal",
      axis: {
        format: "%Y",
      },
    },
    y: {
      aggregate: "sum",
      field: "count",
      type: "quantitative",
      axis: {
        title: "sum of persons unemployed",
      },
    },
    color: {
      field: "series",
      type: "nominal",
      scale: {
        scheme: "category20b",
      },
    },
  },
};

export const PIE_CHART: VegaLiteSpec = {
  data: {
    values: [
      { category: "A", value: 0.4 },
      { category: "B", value: 0.6 },
    ],
  },
  mark: "arc",
  encoding: {
    theta: { field: "value", type: "quantitative" },
    color: { field: "category", type: "nominal" },
  },
};

export const DONUT_CHART: VegaLiteSpec = {
  data: {
    values: [
      { category: "A", value: 0.4 },
      { category: "B", value: 0.6 },
    ],
  },
  mark: "arc",
  encoding: {
    theta: { field: "value", type: "quantitative" },
    color: { field: "category", type: "nominal" },
    stroke: { value: "white" },
  },
};

export const STACKED_BAR_CHART: VegaLiteSpec = {
  data: {
    url: "https://raw.githubusercontent.com/vega/vega/master/docs/data/barley.json",
  },
  mark: "bar",
  encoding: {
    x: { field: "variety" },
    y: { aggregate: "sum", field: "yield" },
    color: { field: "site" },
  },
};

export const TICK_CHART: VegaLiteSpec = {
  ...POINT_CHART,
  mark: "tick",
};

export const CIRCLE_CHART: VegaLiteSpec = {
  ...POINT_CHART,
  encoding: {
    ...POINT_CHART.encoding,
    color: {
      field: "Origin",
      type: "nominal",
    },
  },
  mark: "circle",
};

export const CIRCLE_2_CHART: VegaLiteSpec = {
  $schema: "https://vega.github.io/schema/vega-lite/v6.json",
  config: {
    view: { continuousHeight: 300, continuousWidth: 300 },
    scale: { bandPaddingInner: 0.2 },
  },
  data: {
    url: "https://raw.githubusercontent.com/vega/vega-lite-v1/master/data/iris.json",
  },
  encoding: {
    color: {
      field: "species",
      type: "nominal",
    },
    size: { field: "petalWidth", type: "quantitative" },
    x: {
      field: "sepalLength",
      scale: { zero: false },
      type: "quantitative",
    },
    y: {
      field: "sepalWidth",
      scale: { padding: 1, zero: false },
      type: "quantitative",
    },
  },
  mark: { type: "circle" },
};

export const SQUARE_CHART: VegaLiteSpec = {
  ...POINT_CHART,
  mark: "square",
};

export const RECT_CHART: VegaLiteSpec = {
  data: {
    url: "https://raw.githubusercontent.com/vega/vega/master/docs/data/movies.json",
  },
  transform: [
    {
      filter: {
        and: [
          { field: "IMDB Rating", valid: true },
          { field: "Rotten Tomatoes Rating", valid: true },
        ],
      },
    },
  ],
  mark: "rect",
  width: 300,
  height: 200,
  encoding: {
    x: {
      bin: { maxbins: 60 },
      field: "IMDB Rating",
      type: "quantitative",
    },
    y: {
      bin: { maxbins: 40 },
      field: "Rotten Tomatoes Rating",
      type: "quantitative",
    },
    color: {
      aggregate: "count",
      type: "quantitative",
    },
  },
  config: {
    view: {
      stroke: "transparent",
    },
  },
};

export const RULE_CHART: VegaLiteSpec = {
  ...POINT_CHART,
  mark: "rule",
};
