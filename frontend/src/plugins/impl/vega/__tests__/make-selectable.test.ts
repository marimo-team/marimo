/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { makeSelectable } from "../make-selectable";
import { VegaLiteSpec } from "../types";
import { getSelectionParamNames } from "../params";

describe("makeSelectable", () => {
  it("should return correctly if mark is not string", () => {
    const spec = {
      mark: {
        type: "point",
      },
    } as VegaLiteSpec;
    expect(makeSelectable(spec, {})).toMatchSnapshot();
  });

  it("should return correctly if mark is a string", () => {
    const spec = {
      mark: "point",
    } as VegaLiteSpec;
    expect(makeSelectable(spec, {})).toMatchSnapshot();
  });

  it("should return the same spec if selection is false", () => {
    const spec = {
      mark: "point",
    } as VegaLiteSpec;
    const newSpec = makeSelectable(spec, {
      chartSelection: false,
      fieldSelection: false,
    });
    expect(newSpec).toEqual(spec);
    expect(getSelectionParamNames(newSpec)).toEqual([]);
  });

  it("should return the same spec for not-defined and true", () => {
    const spec = {
      mark: "point",
    } as VegaLiteSpec;
    expect(
      makeSelectable(spec, {
        chartSelection: true,
        fieldSelection: true,
      }),
    ).toEqual(makeSelectable(spec, {}));
  });

  it("should return the same spec if mark is not in spec", () => {
    const spec1 = {
      mark: "point",
    } as VegaLiteSpec;
    const spec2 = {
      mark: {
        type: "point",
      },
    } as VegaLiteSpec;
    expect(makeSelectable(spec1, {})).toEqual(makeSelectable(spec2, {}));
  });

  it("should return correctly if overlapping encodings", () => {
    const spec = {
      config: {
        view: {
          continuousHeight: 300,
        },
      },
      data: { url: "data/cars.json" },
      encoding: {
        color: {
          field: "Origin",
          type: "nominal",
        },
        x: {
          field: "Horsepower",
          type: "quantitative",
        },
        y: {
          field: "Miles_per_Gallon",
          type: "quantitative",
        },
      },
      mark: {
        type: "point",
      },
    } as VegaLiteSpec;
    const newSpec = makeSelectable(spec, {
      chartSelection: true,
      fieldSelection: true,
    });
    expect(newSpec).toMatchSnapshot();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "legend_selection_Origin",
      "select_point",
      "select_interval",
    ]);
  });

  it("should skip field selection if empty or false", () => {
    const spec = {
      config: {
        view: {
          continuousHeight: 300,
        },
      },
      data: { url: "data/cars.json" },
      encoding: {
        color: {
          field: "Origin",
          type: "nominal",
        },
        x: {
          field: "Horsepower",
          type: "quantitative",
        },
        y: {
          field: "Miles_per_Gallon",
          type: "quantitative",
        },
      },
      mark: {
        type: "point",
      },
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {
      chartSelection: true,
      fieldSelection: false,
    });
    expect(newSpec).toMatchSnapshot();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "select_point",
      "select_interval",
    ]);

    // These are the same
    expect(
      makeSelectable(spec, { chartSelection: true, fieldSelection: false }),
    ).toEqual(
      makeSelectable(spec, { chartSelection: true, fieldSelection: [] }),
    );
  });

  it("should return correctly with multiple encodings", () => {
    const spec = {
      mark: "point",
      encoding: {
        color: {
          field: "colorField",
          type: "nominal",
        },
        size: {
          field: "sizeField",
          type: "quantitative",
        },
      },
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});
    expect(newSpec).toMatchSnapshot();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "legend_selection_colorField",
      "legend_selection_sizeField",
      "select_point",
      "select_interval",
    ]);
  });

  it("should return correctly if existing legend selection", () => {
    const spec = {
      config: {
        view: {
          continuousHeight: 300,
        },
      },
      data: {
        url: "https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/unemployment-across-industries.json",
      },
      encoding: {
        color: {
          field: "series",
          scale: { scheme: "category20b" },
          type: "nominal",
        },
        opacity: {
          condition: { param: "param_1", value: 1 },
          value: 0.2,
        },
        x: {
          axis: { domain: false, format: "%Y", tickSize: 0 },
          field: "date",
          timeUnit: "yearmonth",
          type: "temporal",
        },
        y: {
          aggregate: "sum",
          axis: null,
          field: "count",
          stack: "center",
          type: "quantitative",
        },
      },
      mark: { type: "area" },
      params: [
        {
          bind: "legend",
          name: "param_1",
          select: { fields: ["series"], type: "point" },
        },
      ],
    } as VegaLiteSpec;
    const newSpec = makeSelectable(spec, {});
    expect(newSpec).toMatchSnapshot();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "param_1",
      "legend_selection_series",
      "select_point",
    ]);
  });

  it("should work for multi-layered charts", () => {
    const spec = {
      layer: [
        {
          mark: {
            type: "errorbar",
            ticks: true,
          },
          encoding: {
            x: {
              field: "yield_center",
              scale: {
                zero: false,
              },
              title: "yield",
              type: "quantitative",
            },
            xError: {
              field: "yield_error",
            },
            y: {
              field: "variety",
              type: "nominal",
            },
          },
        },
        {
          mark: {
            type: "point",
            color: "black",
            filled: true,
          },
          encoding: {
            x: {
              field: "yield_center",
              type: "quantitative",
            },
          },
        },
      ],
      data: { name: "source" },
      width: "container",
      datasets: {
        source: [
          {
            yield_error: 7.5522,
            yield_center: 32.4,
          },
          {
            yield_error: 6.9775,
            yield_center: 30.966_67,
          },
          {
            yield_error: 3.9167,
            yield_center: 33.966_665,
          },
          {
            yield_error: 11.9732,
            yield_center: 30.45,
          },
        ],
      },
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {
      chartSelection: true,
    });
    expect(newSpec).toMatchSnapshot();

    expect(getSelectionParamNames(newSpec)).toEqual([
      "select_point",
      "select_interval",
    ]);
  });
});
