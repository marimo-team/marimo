/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { seedFromFilter } from "../column-header";
import { Filter } from "../filters";

describe("seedFromFilter", () => {
  it("returns empty defaults when there is no filter", () => {
    expect(seedFromFilter(undefined)).toEqual({
      values: [],
      operator: "in",
    });
  });

  it("seeds values from an `in` select filter", () => {
    const filter = Filter.select({
      options: ["Flying", "Ground"],
      operator: "in",
    });
    expect(seedFromFilter(filter)).toEqual({
      values: ["Flying", "Ground"],
      operator: "in",
    });
  });

  it("preserves `not_in` so reapplying does not silently flip to `in`", () => {
    const filter = Filter.select({
      options: ["Fire"],
      operator: "not_in",
    });
    expect(seedFromFilter(filter)).toEqual({
      values: ["Fire"],
      operator: "not_in",
    });
  });

  it("returns a fresh array (callers may mutate without affecting the filter)", () => {
    const options = ["a", "b"];
    const filter = Filter.select({ options, operator: "in" });
    const seeded = seedFromFilter(filter);
    seeded.values.push("c");
    expect(options).toEqual(["a", "b"]);
  });

  it("ignores non-select filters and falls back to defaults", () => {
    expect(seedFromFilter(Filter.text({ text: "abc" }))).toEqual({
      values: [],
      operator: "in",
    });
    expect(seedFromFilter(Filter.number({ min: 0, max: 10 }))).toEqual({
      values: [],
      operator: "in",
    });
    expect(
      seedFromFilter(Filter.boolean({ value: true, operator: "is_true" })),
    ).toEqual({
      values: [],
      operator: "in",
    });
  });
});
