/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  deselectMatching,
  multiselectFilterFn,
  selectMatching,
} from "../utils";

describe("multiselectFilterFn", () => {
  it("matches when all query words appear in the option (any order)", () => {
    expect(multiselectFilterFn("foo bar", "bar foo")).toBe(1);
  });

  it("does not match a partial word", () => {
    expect(multiselectFilterFn("foo bar", "foob")).toBe(0);
  });
});

describe("selectMatching", () => {
  it("adds only unselected matches, existing first then additions", () => {
    expect(selectMatching(["a"], ["a", "b", "c"])).toEqual(["a", "b", "c"]);
  });

  it("keeps selections outside the filter untouched", () => {
    expect(selectMatching(["x", "y"], ["a", "b"])).toEqual([
      "x",
      "y",
      "a",
      "b",
    ]);
  });

  it("is generic over the value type", () => {
    expect(selectMatching<number>([1], [1, 2])).toEqual([1, 2]);
  });
});

describe("deselectMatching", () => {
  it("removes only the matching items", () => {
    expect(deselectMatching(["a", "b", "c"], ["a", "c"])).toEqual(["b"]);
  });

  it("leaves out-of-filter selections intact", () => {
    expect(deselectMatching(["x", "a"], ["a", "b"])).toEqual(["x"]);
  });
});
