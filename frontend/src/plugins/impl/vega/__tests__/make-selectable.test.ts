/* Copyright 2026 Marimo. All rights reserved. */

// @ts-expect-error - vega-parser is not typed
import { parse } from "vega-parser";
import { describe, expect, it } from "vitest";
import { invariant } from "@/utils/invariant";
import { makeSelectable } from "../make-selectable";
import { getSelectionParamNames } from "../params";
import type { VegaLiteSpec } from "../types";

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
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
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
    expect(makeSelectable(spec, {})).toMatchSnapshot();
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
    expect(makeSelectable(spec1, {})).toMatchSnapshot();
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
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "legend_selection_Origin",
      "select_point",
      "select_interval",
      "pan_zoom",
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
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "select_point",
      "select_interval",
      "pan_zoom",
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
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "legend_selection_colorField",
      "legend_selection_sizeField",
      "select_point",
      "select_interval",
      "pan_zoom",
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
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "param_1",
      "select_point",
      "pan_zoom",
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
    expect(parse(newSpec)).toBeDefined();

    expect(getSelectionParamNames(newSpec)).toEqual([
      "pan_zoom",
      "select_point_1",
      "select_interval_1",
    ]);
  });

  it("should work for multi-layered charts with different selections", () => {
    const spec = {
      layer: [
        {
          mark: { type: "bar", cornerRadius: 10, height: 10 },
          encoding: {
            x: {
              aggregate: "min",
              field: "temp_min",
              scale: { domain: [-15, 45] },
              title: "Temperature (°C)",
              type: "quantitative",
            },
            x2: { aggregate: "max", field: "temp_max" },
            y: {
              field: "date",
              timeUnit: "month",
              title: null,
              type: "ordinal",
            },
          },
        },
        {
          mark: { type: "text", align: "right", dx: -5 },
          encoding: {
            text: {
              aggregate: "min",
              field: "temp_min",
              type: "quantitative",
            },
            x: { aggregate: "min", field: "temp_min", type: "quantitative" },
            y: { field: "date", timeUnit: "month", type: "ordinal" },
          },
        },
        {
          mark: { type: "text", align: "left", dx: 5 },
          encoding: {
            text: {
              aggregate: "max",
              field: "temp_max",
              type: "quantitative",
            },
            x: { aggregate: "max", field: "temp_max", type: "quantitative" },
            y: { field: "date", timeUnit: "month", type: "ordinal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {
      chartSelection: true,
    });

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toEqual([
      "select_point_0",
      "select_interval_0",
      "pan_zoom",
      "select_point_1",
      "select_interval_1",
      "select_point_2",
      "select_interval_2",
    ]);
  });

  it("should work for geoshape", () => {
    const spec = {
      mark: "geoshape",
      encoding: {
        color: {
          datum: "red",
          type: "nominal",
        },
        x: {
          field: "x",
          type: "quantitative",
        },
        y: {
          field: "y",
          type: "quantitative",
        },
      },
    } as VegaLiteSpec;
    const newSpec = makeSelectable(spec, {});
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toEqual([]);
  });

  it("should work for layered charts, with existing selection", () => {
    const spec = {
      data: {
        name: "data-34c3e7380bd529c27667c64406db8bb8",
      },
      datasets: {
        "data-34c3e7380bd529c27667c64406db8bb8": [
          {
            Level1: "a",
            count: 1,
            stage: "france",
          },
          {
            Level1: "b",
            count: 2,
            stage: "france",
          },
          {
            Level1: "c",
            count: 3,
            stage: "england",
          },
        ],
      },
      layer: [
        {
          encoding: {
            color: {
              condition: {
                field: "stage",
                param: "param_22",
              },
              value: "lightgray",
            },
            x: {
              field: "Level1",
              sort: {
                order: "descending",
              },
              title: "Subpillar",
              type: "nominal",
            },
            y: {
              field: "count",
              title: "Number of Companies",
              type: "quantitative",
            },
          },
          mark: {
            type: "bar",
          },
          name: "view_21",
        },
        {
          encoding: {
            color: {
              datum: "england",
            },
            y: {
              datum: 2,
            },
          },
          mark: {
            strokeDash: [2, 2],
            type: "rule",
          },
        },
      ],
      params: [
        {
          name: "param_22",
          select: {
            encodings: ["x"],
            type: "point",
          },
          views: ["view_21"],
        },
      ],
    } as VegaLiteSpec;
    const newSpec = makeSelectable(spec, {});
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toMatchInlineSnapshot(`
      [
        "param_22",
      ]
    `);
  });

  it("should work for layered charts, with existing legend selection", () => {
    const spec = {
      data: {
        name: "data-34c3e7380bd529c27667c64406db8bb8",
      },
      datasets: {
        "data-34c3e7380bd529c27667c64406db8bb8": [
          {
            Level1: "a",
            count: 1,
            stage: "france",
          },
          {
            Level1: "b",
            count: 2,
            stage: "france",
          },
          {
            Level1: "c",
            count: 3,
            stage: "england",
          },
        ],
      },
      layer: [
        {
          encoding: {
            color: {
              condition: {
                field: "stage",
                param: "param_22",
              },
              value: "lightgray",
            },
            x: {
              field: "Level1",
              sort: {
                order: "descending",
              },
              title: "Subpillar",
              type: "nominal",
            },
            y: {
              field: "count",
              title: "Number of Companies",
              type: "quantitative",
            },
          },
          mark: {
            type: "bar",
          },
          name: "view_21",
        },
        {
          encoding: {
            color: {
              datum: "england",
            },
            y: {
              datum: 2,
            },
          },
          mark: {
            strokeDash: [2, 2],
            type: "rule",
          },
        },
      ],
      params: [
        {
          name: "param_22",
          bind: "legend",
          select: {
            fields: ["x"],
            type: "point",
          },
          views: ["view_21"],
        },
      ],
    } as VegaLiteSpec;
    const newSpec = makeSelectable(spec, {});
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    expect(getSelectionParamNames(newSpec)).toMatchInlineSnapshot(`
      [
        "param_22",
      ]
    `);
  });

  it.each([
    "errorbar",
    "errorband",
    "boxplot",
  ])("should return the same spec if mark is %s", (mark) => {
    const spec = {
      mark,
    } as unknown as VegaLiteSpec;
    const newSpec = makeSelectable(spec, {});
    expect(newSpec).toEqual(spec);
    expect(getSelectionParamNames(newSpec)).toEqual([]);
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should add legend selection to composite charts (issue #6676)", () => {
    // Test case from https://github.com/marimo-team/marimo/issues/6676
    const spec = {
      layer: [
        {
          mark: "rule",
          encoding: {
            x: { field: "x_value", type: "quantitative" },
            y: { field: "upper", type: "quantitative" },
            y2: { field: "lower" },
            color: {
              field: "category",
              type: "nominal",
            },
          },
        },
        {
          mark: { type: "point", filled: true, size: 60 },
          encoding: {
            x: { field: "x_value", type: "quantitative" },
            y: { field: "value", type: "quantitative" },
            color: {
              field: "category",
              type: "nominal",
            },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {
      chartSelection: true,
      fieldSelection: true,
    });

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    const paramNames = getSelectionParamNames(newSpec);
    // Should have legend selection for category field
    expect(paramNames).toContain("legend_selection_category");
    // Should NOT have duplicate legend params
    expect(
      paramNames.filter((name) => name === "legend_selection_category"),
    ).toHaveLength(1);
  });

  it("should not duplicate legend params when multiple layers have same color field", () => {
    const spec = {
      layer: [
        {
          mark: "line",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
        {
          mark: { type: "point", size: 100 },
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});
    const paramNames = getSelectionParamNames(newSpec);

    // Should have exactly one legend_selection_category param
    const legendParams = paramNames.filter((name) =>
      name.startsWith("legend_selection_category"),
    );
    expect(legendParams).toHaveLength(1);
    expect(legendParams[0]).toBe("legend_selection_category");
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should add bin_coloring param for binned charts", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { field: "x", bin: true, type: "quantitative" },
        y: { aggregate: "count", type: "quantitative" },
      },
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, { chartSelection: true });
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    const paramNames = getSelectionParamNames(newSpec);

    // Should have point selection and bin_coloring param
    expect(paramNames).toContain("select_point");
    expect(paramNames).toContain("bin_coloring");
    // Should NOT have interval selection for binned charts
    expect(paramNames).not.toContain("select_interval");
  });

  it("should add bin_coloring param for 2D binned histogram", () => {
    const spec = {
      mark: "rect",
      encoding: {
        x: { field: "x", bin: true, type: "quantitative" },
        y: { field: "y", bin: true, type: "quantitative" },
        color: { aggregate: "count", type: "quantitative" },
      },
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, { chartSelection: true });
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    const paramNames = getSelectionParamNames(newSpec);

    // Should have point selection and bin_coloring param
    expect(paramNames).toContain("select_point");
    expect(paramNames).toContain("bin_coloring");
  });

  it("should add bin_coloring param for layered binned charts", () => {
    const spec = {
      layer: [
        {
          mark: "bar",
          encoding: {
            x: { field: "x", bin: true, type: "quantitative" },
            y: { aggregate: "count", type: "quantitative" },
          },
        },
        {
          mark: "rule",
          encoding: {
            x: { aggregate: "mean", field: "x", type: "quantitative" },
            color: { value: "red" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, { chartSelection: true });
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
    const paramNames = getSelectionParamNames(newSpec);

    // First layer should have point selection and bin_coloring
    expect(paramNames).toContain("select_point_0");
    expect(paramNames).toContain("bin_coloring_0");
  });

  it("should prefer point selection for binned charts even when chartSelection is true", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { field: "x", bin: { maxbins: 20 }, type: "quantitative" },
        y: { aggregate: "count", type: "quantitative" },
      },
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, { chartSelection: true });
    const paramNames = getSelectionParamNames(newSpec);

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();

    // Should only have point selection for binned charts (not interval)
    expect(paramNames).toContain("select_point");
    expect(paramNames).not.toContain("select_interval");
    expect(paramNames).toContain("bin_coloring");
  });

  it("should not add bin_coloring when chartSelection is false", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { field: "x", bin: true, type: "quantitative" },
        y: { aggregate: "count", type: "quantitative" },
      },
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, { chartSelection: false });
    const paramNames = getSelectionParamNames(newSpec);

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();

    // Should not have any chart selection params
    expect(paramNames).not.toContain("select_point");
    expect(paramNames).not.toContain("bin_coloring");
  });

  it("should collect legend fields from multiple layers with different fields", () => {
    const spec = {
      layer: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            size: { field: "size_field", type: "quantitative" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});
    const paramNames = getSelectionParamNames(newSpec);

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();

    // Should have legend params for both fields
    expect(paramNames).toContain("legend_selection_category");
    expect(paramNames).toContain("legend_selection_size_field");
  });

  it("should add legend selection to vconcat specs", () => {
    const spec = {
      vconcat: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
        {
          mark: "bar",
          encoding: {
            x: { field: "x", type: "nominal" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});
    const paramNames = getSelectionParamNames(newSpec);

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();

    // Should have legend selection for category field
    expect(paramNames).toContain("legend_selection_category");
  });

  it("should add legend selection to hconcat specs", () => {
    const spec = {
      hconcat: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "series", type: "nominal" },
          },
        },
        {
          mark: "line",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "series", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});
    const paramNames = getSelectionParamNames(newSpec);

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();

    // Should have legend selection for series field
    expect(paramNames).toContain("legend_selection_series");
  });

  it("should add legend selection to nested vconcat(hconcat(...)) specs", () => {
    const spec = {
      vconcat: [
        {
          hconcat: [
            {
              mark: "point",
              encoding: {
                x: { field: "x", type: "quantitative" },
                y: { field: "y", type: "quantitative" },
                color: { field: "category", type: "nominal" },
              },
            },
            {
              mark: "bar",
              encoding: {
                x: { field: "x", type: "nominal" },
                y: { field: "y", type: "quantitative" },
                color: { field: "category", type: "nominal" },
              },
            },
          ],
        },
        {
          mark: "line",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});
    const paramNames = getSelectionParamNames(newSpec);

    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();

    // Should have legend selection for category field
    expect(paramNames).toContain("legend_selection_category");
  });

  it("should hoist params to top level in hconcat(vconcat(...)) and apply opacity to nested specs", () => {
    const spec = {
      hconcat: [
        {
          vconcat: [
            {
              mark: "point",
              encoding: {
                x: { field: "Horsepower", type: "quantitative" },
                y: { field: "Miles_per_Gallon", type: "quantitative" },
                color: { field: "Origin", type: "nominal" },
              },
              height: 100,
            },
            {
              mark: "point",
              encoding: {
                x: { field: "Horsepower", type: "quantitative" },
                y: { field: "Miles_per_Gallon", type: "quantitative" },
                color: { field: "Origin", type: "nominal" },
              },
              height: 100,
            },
          ],
        },
        {
          mark: "point",
          encoding: {
            x: { field: "Horsepower", type: "quantitative" },
            y: { field: "Miles_per_Gallon", type: "quantitative" },
            color: { field: "Origin", type: "nominal" },
          },
          height: 100,
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // Params should be hoisted to top level
    expect(newSpec.params).toBeDefined();
    expect(newSpec.params!.length).toBeGreaterThan(0);

    // Should have legend selection for Origin field
    const paramNames = getSelectionParamNames(newSpec);
    expect(paramNames).toContain("legend_selection_Origin");

    // Nested specs should NOT have params (they should be hoisted)
    if ("hconcat" in newSpec) {
      for (const subSpec of newSpec.hconcat) {
        if ("vconcat" in subSpec) {
          invariant("vconcat" in subSpec, "subSpec should have vconcat");
          for (const innerSpec of subSpec.vconcat) {
            expect("params" in innerSpec).toBe(false);
            // But should have opacity encoding
            if ("mark" in innerSpec) {
              expect(innerSpec.encoding?.opacity).toBeDefined();
            }
          }
        } else if ("mark" in subSpec) {
          expect(subSpec.params).toBeUndefined();
          // But should have opacity encoding
          expect(subSpec.encoding?.opacity).toBeDefined();
        }
      }
    }
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should only hoist common params with same select.type and select.encodings", () => {
    // All point charts with x,y encodings - should hoist point/interval params
    const spec = {
      hconcat: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // Common params should be hoisted
    expect(newSpec.params).toBeDefined();
    const topLevelParamNames = getSelectionParamNames(newSpec);

    // Legend param should be hoisted (common across all)
    expect(topLevelParamNames).toContain("legend_selection_category");

    // Point and interval params should be hoisted (same type and encodings)
    expect(topLevelParamNames).toContain("select_point");
    expect(topLevelParamNames).toContain("select_interval");

    // Nested specs should not have params
    if ("hconcat" in newSpec) {
      for (const subSpec of newSpec.hconcat) {
        expect("params" in subSpec).toBe(false);
      }
    }
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should not hoist params when specs have different selection types", () => {
    // One bar chart (point+interval) and one area chart (point only) - different selection strategies
    const spec = {
      hconcat: [
        {
          mark: "bar",
          encoding: {
            x: { field: "x", type: "nominal" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
        {
          mark: "area",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // Legend param should be hoisted (common across all)
    const topLevelParamNames = getSelectionParamNames(newSpec);
    expect(topLevelParamNames).toContain("legend_selection_category");

    // But chart selection params should NOT be hoisted (different types)
    // Bar gets point+interval with x encoding, area gets point with color encoding
    if ("hconcat" in newSpec) {
      const subspecParams = newSpec.hconcat.flatMap((subSpec) =>
        "params" in subSpec ? subSpec.params : [],
      );
      expect(subspecParams.length).toBeGreaterThan(0);
    }
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should not hoist params when specs have different encodings", () => {
    // One chart with x,y selection and one with color selection
    const spec = {
      hconcat: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
          },
        },
        {
          mark: "arc",
          encoding: {
            theta: { field: "value", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // Chart selection params should NOT be hoisted (different encodings)
    // Point chart uses x,y encodings, arc chart uses color encoding
    if ("hconcat" in newSpec) {
      const subspecParams = newSpec.hconcat.flatMap((subSpec) =>
        "params" in subSpec ? subSpec.params : [],
      );
      // Both subspecs should have their own params
      expect(subspecParams.length).toBeGreaterThan(0);
    }
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should hoist only common legend params when chart selections differ", () => {
    const spec = {
      hconcat: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
        {
          mark: "bar",
          encoding: {
            x: { field: "x", type: "nominal" },
            y: { field: "y", type: "quantitative" },
            color: { field: "category", type: "nominal" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // Common legend param should be hoisted
    const topLevelParamNames = getSelectionParamNames(newSpec);
    expect(topLevelParamNames).toContain("legend_selection_category");

    // But chart-specific params may or may not be hoisted depending on if they match
    // The point chart has x,y encodings, bar has x encoding - these differ
    if ("hconcat" in newSpec) {
      const subspecParams = newSpec.hconcat.flatMap((subSpec) =>
        "params" in subSpec ? subSpec.params : [],
      );
      // Each subspec should have its own chart selection params
      expect(subspecParams.length).toBeGreaterThan(0);
    }
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should handle empty concat specs gracefully", () => {
    const spec = {
      hconcat: [],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});
    expect(newSpec).toEqual(spec);
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should handle concat with only one subspec", () => {
    const spec = {
      hconcat: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
          },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // Should hoist params even with single subspec
    expect(newSpec.params).toBeDefined();
    const topLevelParamNames = getSelectionParamNames(newSpec);
    expect(topLevelParamNames.length).toBeGreaterThan(0);
    expect(newSpec).toMatchSnapshot();
    expect(parse(newSpec)).toBeDefined();
  });

  it("should preserve vconcat with existing selection params unchanged (issue #7668)", () => {
    // This test reproduces the issue from #7668:
    // Altair charts with cross-view interactions (e.g., brush selection)
    // should not be modified by makeSelectable to preserve the interaction.
    const spec = {
      vconcat: [
        {
          mark: "area",
          encoding: {
            x: {
              field: "x",
              type: "quantitative",
              scale: { domain: { param: "brush", encoding: "x" } },
            },
            y: { field: "y", type: "quantitative" },
          },
        },
        {
          mark: "area",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
          },
        },
      ],
      params: [
        {
          name: "brush",
          select: { type: "interval", encodings: ["x"] },
          views: ["view_1"],
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // The spec should be returned unchanged to preserve cross-view interactions
    expect(newSpec).toEqual(spec);
    expect(getSelectionParamNames(newSpec)).toEqual(["brush"]);
  });

  it("should preserve hconcat with existing selection params unchanged (issue #7668)", () => {
    const spec = {
      hconcat: [
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
          },
        },
        {
          mark: "point",
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
          },
        },
      ],
      params: [
        {
          name: "my_selection",
          select: { type: "point", encodings: ["x", "y"] },
        },
      ],
    } as VegaLiteSpec;

    const newSpec = makeSelectable(spec, {});

    // The spec should be returned unchanged
    expect(newSpec).toEqual(spec);
    expect(getSelectionParamNames(newSpec)).toEqual(["my_selection"]);
  });
});
