/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { Option } from "../types";
import {
  deselectMatching,
  getBulkActions,
  getVisibleOptions,
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

const opt = (value: string): Option<string> => ({ value, label: value });

describe("getVisibleOptions", () => {
  it("pins selected options first, both groups in option order", () => {
    const options = ["a", "b", "c", "d"].map(opt);
    expect(
      getVisibleOptions(options, new Set(["b", "d"])).map((o) => o.value),
    ).toEqual(["b", "d", "a", "c"]);
  });

  it("returns options unchanged when nothing is pinned", () => {
    const options = ["a", "b", "c"].map(opt);
    expect(getVisibleOptions(options, new Set()).map((o) => o.value)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  it("ignores pinned values that are not in options", () => {
    const options = ["a", "b"].map(opt);
    expect(
      getVisibleOptions(options, new Set(["b", "ghost"])).map((o) => o.value),
    ).toEqual(["b", "a"]);
  });
});

const bulkBase = {
  options: ["a", "b", "c", "d"].map(opt),
  value: [] as string[],
  searchQuery: "",
  maxSelections: undefined as number | undefined,
};

describe("getBulkActions", () => {
  it("returns no rows for 2 or fewer options", () => {
    expect(
      getBulkActions({
        ...bulkBase,
        options: ["a", "b"].map(opt),
        filteredOptions: ["a", "b"].map(opt),
      }),
    ).toEqual({});
  });

  it("returns no rows when maxSelections is 1", () => {
    expect(
      getBulkActions({
        ...bulkBase,
        filteredOptions: bulkBase.options,
        maxSelections: 1,
      }),
    ).toEqual({});
  });

  it("idle: Select all / Deselect all with enable flags", () => {
    expect(
      getBulkActions({
        ...bulkBase,
        value: ["a"],
        filteredOptions: bulkBase.options,
      }),
    ).toEqual({
      select: { label: "Select all", enabled: true },
      deselect: { label: "Deselect all", enabled: true },
    });
  });

  it("idle: Select all disabled when everything is selected", () => {
    expect(
      getBulkActions({
        ...bulkBase,
        value: ["a", "b", "c", "d"],
        filteredOptions: bulkBase.options,
      }),
    ).toEqual({
      select: { label: "Select all", enabled: false },
      deselect: { label: "Deselect all", enabled: true },
    });
  });

  it("searching: counts reflect unselected vs selected matches", () => {
    expect(
      getBulkActions({
        ...bulkBase,
        value: ["a"],
        searchQuery: "x",
        filteredOptions: ["a", "b", "c"].map(opt),
      }),
    ).toEqual({
      select: { label: "Select 2 matching", enabled: true },
      deselect: { label: "Deselect 1 matching", enabled: true },
    });
  });

  it("searching with no matches: no rows", () => {
    expect(
      getBulkActions({ ...bulkBase, searchQuery: "zzz", filteredOptions: [] }),
    ).toEqual({});
  });

  it("maxSelections > 1: deselect-side only, idle and searching", () => {
    expect(
      getBulkActions({
        ...bulkBase,
        value: ["a"],
        filteredOptions: bulkBase.options,
        maxSelections: 3,
      }),
    ).toEqual({ deselect: { label: "Deselect all", enabled: true } });

    expect(
      getBulkActions({
        ...bulkBase,
        value: ["a"],
        searchQuery: "x",
        filteredOptions: ["a", "b"].map(opt),
        maxSelections: 3,
      }),
    ).toEqual({ deselect: { label: "Deselect 1 matching", enabled: true } });
  });
});
