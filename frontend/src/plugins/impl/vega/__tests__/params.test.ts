/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { getDirectionOfBar } from "../params";
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
