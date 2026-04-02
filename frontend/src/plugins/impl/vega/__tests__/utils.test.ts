/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getContainerWidth } from "../utils";

describe("getContainerWidth", () => {
  it('should return "container" when spec width is "container"', () => {
    expect(getContainerWidth({ width: "container" })).toBe("container");
  });

  it("should return a numeric width", () => {
    expect(getContainerWidth({ width: 500 })).toBe(500);
  });

  it("should return undefined when spec has no width", () => {
    expect(getContainerWidth({ height: 300 })).toBeUndefined();
  });

  it("should return undefined for null", () => {
    expect(getContainerWidth(null)).toBeUndefined();
  });

  it("should return undefined for undefined", () => {
    expect(getContainerWidth(undefined)).toBeUndefined();
  });

  it("should return undefined for non-object values", () => {
    expect(getContainerWidth("string")).toBeUndefined();
    expect(getContainerWidth(42)).toBeUndefined();
    expect(getContainerWidth(true)).toBeUndefined();
  });

  it("should return undefined when width is explicitly undefined", () => {
    expect(getContainerWidth({ width: undefined })).toBeUndefined();
  });

  it("should find width in nested facet spec", () => {
    expect(
      getContainerWidth({
        $schema: "https://vega.github.io/schema/vega-lite/v6.json",
        facet: { column: { field: "Origin", type: "nominal" } },
        spec: {
          mark: "point",
          encoding: {},
          width: "container",
        },
      }),
    ).toBe("container");
  });

  it("should find width in nested repeat spec", () => {
    expect(
      getContainerWidth({
        $schema: "https://vega.github.io/schema/vega-lite/v6.json",
        repeat: { row: ["A", "B"] },
        spec: {
          mark: "point",
          encoding: {},
          width: "container",
        },
      }),
    ).toBe("container");
  });

  it("should return undefined for nested spec without width", () => {
    expect(
      getContainerWidth({
        facet: { column: { field: "Origin" } },
        spec: { mark: "point", encoding: {} },
      }),
    ).toBeUndefined();
  });

  it("should return undefined for hconcat (width on sub-specs)", () => {
    expect(
      getContainerWidth({
        hconcat: [{ width: "container" }, { width: "container" }],
      }),
    ).toBeUndefined();
  });

  it("should return undefined for vconcat (width on sub-specs)", () => {
    expect(
      getContainerWidth({
        vconcat: [{ width: "container" }, { width: "container" }],
      }),
    ).toBeUndefined();
  });

  it("should return undefined for compiled Vega spec (width as signal)", () => {
    expect(
      getContainerWidth({
        $schema: "https://vega.github.io/schema/vega/v6.json",
        autosize: { contains: "padding", type: "fit-x" },
        signals: [
          {
            name: "width",
            init: "isFinite(containerSize()[0]) ? containerSize()[0] : 300",
          },
        ],
      }),
    ).toBeUndefined();
  });
});
