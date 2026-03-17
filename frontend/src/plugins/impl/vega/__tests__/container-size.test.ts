/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { vegaContainerClasses } from "../container-size";

describe("vegaContainerClasses", () => {
  it('returns true for width "container"', () => {
    expect(vegaContainerClasses({ width: "container" })).toEqual({
      "vega-container-width": true,
    });
  });

  it("returns false for fixed width", () => {
    expect(vegaContainerClasses({ width: 400 })).toEqual({
      "vega-container-width": false,
    });
  });

  it("returns false when width is not set", () => {
    expect(vegaContainerClasses({})).toEqual({
      "vega-container-width": false,
    });
  });

  it("handles a full vega-lite-like spec", () => {
    expect(
      vegaContainerClasses({
        $schema: "https://vega.github.io/schema/vega-lite/v5.json",
        mark: "point",
        width: "container",
        encoding: { x: { field: "a" } },
      }),
    ).toEqual({
      "vega-container-width": true,
    });
  });
});
