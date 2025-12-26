/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { getBinnedFields, getDirectionOfBar, ParamNames } from "../params";
import type { VegaLiteUnitSpec } from "../types";

describe("getDirectionOfBar", () => {
  it("should return undefined if spec is not provided", () => {
    expect(getDirectionOfBar(undefined!)).toBeUndefined();
  });

  it("should return undefined if mark is not in spec", () => {
    const spec = { encoding: {} } as VegaLiteUnitSpec;
    expect(getDirectionOfBar(spec)).toBeUndefined();
  });

  it('should return "vertical" if xEncoding type is "nominal"', () => {
    const spec = {
      mark: {},
      encoding: { x: { type: "nominal" } },
    } as VegaLiteUnitSpec;
    expect(getDirectionOfBar(spec)).toBe("vertical");
  });

  it('should return "horizontal" if yEncoding type is "nominal"', () => {
    const spec = {
      mark: {},
      encoding: { y: { type: "nominal" } },
    } as VegaLiteUnitSpec;
    expect(getDirectionOfBar(spec)).toBe("horizontal");
  });

  it('should return "horizontal" if xEncoding has "aggregate"', () => {
    const spec = {
      mark: {},
      encoding: { x: { aggregate: "sum" } },
    } as VegaLiteUnitSpec;
    expect(getDirectionOfBar(spec)).toBe("horizontal");
  });

  it('should return "vertical" if yEncoding has "aggregate"', () => {
    const spec = {
      mark: {},
      encoding: { y: { aggregate: "sum" } },
    } as VegaLiteUnitSpec;
    expect(getDirectionOfBar(spec)).toBe("vertical");
  });

  it("should return undefined if no conditions are met", () => {
    const spec = { mark: {}, encoding: { x: {}, y: {} } } as VegaLiteUnitSpec;
    expect(getDirectionOfBar(spec)).toBeUndefined();
  });
});

describe("getBinnedFields", () => {
  it("should return empty array if spec has no encoding", () => {
    const spec = { mark: "point" } as VegaLiteUnitSpec;
    expect(getBinnedFields(spec)).toEqual([]);
  });

  it("should return empty array if no fields are binned", () => {
    const spec = {
      mark: "point",
      encoding: {
        x: { field: "x", type: "quantitative" },
        y: { field: "y", type: "quantitative" },
      },
    } as VegaLiteUnitSpec;
    expect(getBinnedFields(spec)).toEqual([]);
  });

  it("should return binned field name for x encoding", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { field: "x", bin: true, type: "quantitative" },
        y: { aggregate: "count", type: "quantitative" },
      },
    } as VegaLiteUnitSpec;
    expect(getBinnedFields(spec)).toEqual(["x"]);
  });

  it("should return binned field name for y encoding", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { aggregate: "count", type: "quantitative" },
        y: { field: "y", bin: true, type: "quantitative" },
      },
    } as VegaLiteUnitSpec;
    expect(getBinnedFields(spec)).toEqual(["y"]);
  });

  it("should return multiple binned fields", () => {
    const spec = {
      mark: "rect",
      encoding: {
        x: { field: "x", bin: true, type: "quantitative" },
        y: { field: "y", bin: true, type: "quantitative" },
        color: { aggregate: "count", type: "quantitative" },
      },
    } as VegaLiteUnitSpec;
    expect(getBinnedFields(spec)).toEqual(["x", "y"]);
  });

  it("should handle bin with custom configuration", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: {
          field: "temperature",
          bin: { maxbins: 20 },
          type: "quantitative",
        },
        y: { aggregate: "count", type: "quantitative" },
      },
    } as VegaLiteUnitSpec;
    expect(getBinnedFields(spec)).toEqual(["temperature"]);
  });

  it("should ignore encodings without field property", () => {
    const spec = {
      mark: "bar",
      encoding: {
        x: { bin: true, type: "quantitative" },
        y: { field: "y", type: "quantitative" },
      },
    } as VegaLiteUnitSpec;
    expect(getBinnedFields(spec)).toEqual([]);
  });
});

describe("ParamNames", () => {
  describe("binColoring", () => {
    it("should generate bin_coloring for undefined layer", () => {
      expect(ParamNames.binColoring(undefined)).toBe("bin_coloring");
    });

    it("should generate bin_coloring_0 for layer 0", () => {
      expect(ParamNames.binColoring(0)).toBe("bin_coloring_0");
    });

    it("should generate bin_coloring_1 for layer 1", () => {
      expect(ParamNames.binColoring(1)).toBe("bin_coloring_1");
    });
  });

  describe("isBinColoring", () => {
    it("should return true for bin_coloring", () => {
      expect(ParamNames.isBinColoring("bin_coloring")).toBe(true);
    });

    it("should return true for bin_coloring_0", () => {
      expect(ParamNames.isBinColoring("bin_coloring_0")).toBe(true);
    });

    it("should return true for bin_coloring_123", () => {
      expect(ParamNames.isBinColoring("bin_coloring_123")).toBe(true);
    });

    it("should return false for select_point", () => {
      expect(ParamNames.isBinColoring("select_point")).toBe(false);
    });

    it("should return false for select_interval", () => {
      expect(ParamNames.isBinColoring("select_interval")).toBe(false);
    });

    it("should return false for legend_selection_field", () => {
      expect(ParamNames.isBinColoring("legend_selection_field")).toBe(false);
    });
  });
});
