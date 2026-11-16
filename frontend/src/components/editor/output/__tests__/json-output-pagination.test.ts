/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import {
  determineMaxDisplayLength,
  estimateExpandedLines,
  paginateJson,
} from "../json-output/pagination";

describe("determineMaxDisplayLength", () => {
  const sample2DArray = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
    [10, 11, 12],
    [13, 14, 15],
    [16, 17, 18],
    [19, 20, 21],
    [22, 23, 24],
    [25, 26, 27],
    [28, 29, 30],
  ];

  it("should return undefined for 1 level arrays", () => {
    const value = [1, 2, 3];
    const result = determineMaxDisplayLength(value);
    expect(result).toBeUndefined();
  });

  it("should return undefined for 2 level arrays with less than 20 items", () => {
    const value = sample2DArray;
    const result = determineMaxDisplayLength(value);
    expect(result).toBeUndefined();
  });

  it("should return 10 for 2 level arrays with more than 20 items", () => {
    const longArray = Array.from({ length: 21 }, (_, i) => i);
    const value = [...sample2DArray, longArray];
    const result = determineMaxDisplayLength(value);
    expect(result).toBe(10);
  });

  it("should return 5 for 2 level arrays with more than 50 items", () => {
    const longArray = Array.from({ length: 51 }, (_, i) => i);
    const value = [...sample2DArray, longArray];
    const result = determineMaxDisplayLength(value);
    expect(result).toBe(5);
  });

  it("should return 5 for 3 level arrays with more than 20 items", () => {
    const longArray = Array.from({ length: 21 }, (_, i) => i);
    const value = [[...sample2DArray], [...sample2DArray, longArray]];
    const result = determineMaxDisplayLength(value);
    expect(result).toBe(5);
  });
});

describe("estimateExpandedLines", () => {
  it("scalars count as 1", () => {
    expect(estimateExpandedLines(42, 100)).toBe(1);
    expect(estimateExpandedLines(null, 100)).toBe(1);
  });

  it("flat containers = child count", () => {
    expect(estimateExpandedLines({ a: 1, b: 2, c: 3 }, 100)).toBe(3);
    expect(estimateExpandedLines([1, 2, 3, 4], 100)).toBe(4);
  });

  it("small nested children expand recursively", () => {
    expect(estimateExpandedLines({ a: { x: 1, y: 2 }, b: 3 }, 100)).toBe(3);
  });

  it("large children count as 1 collapsed line", () => {
    const big = Array.from({ length: 20 }, (_, i) => i);
    expect(estimateExpandedLines({ a: big, b: 1 }, 100)).toBe(2);
  });

  it("bails at cap", () => {
    const big = Array.from({ length: 500 }, (_, i) => i);
    expect(estimateExpandedLines(big, 50)).toBe(50);
  });

  it("bails at max depth", () => {
    const data = { a: { b: { c: { d: { e: { f: 1 } } } } } };
    expect(estimateExpandedLines(data, 100)).toBe(1);
  });
});

describe("paginateJson", () => {
  const options = { limits: {}, pageSize: 30 };

  it("preserves full originals and reports the remaining count", () => {
    const rows = Array.from({ length: 100 }, (_, i) => i);
    const data = { rows };
    const tree = paginateJson(data, options);
    const displayRows: unknown[] = Reflect.get(tree.data, "rows");
    expect(displayRows.slice(0, 30)).toEqual(rows.slice(0, 30));
    expect(tree.getPage(displayRows[30])).toEqual({
      path: '["rows"]',
      remaining: 70,
    });
    expect(tree.getOriginal(tree.data)).toBe(data);
    expect(tree.getOriginal(displayRows)).toBe(rows);
    expect(tree.getOriginal("value")).toBe("value");
  });

  it("paginates arrays and objects at the boundary", () => {
    for (const count of [0, 1, 29, 30, 31, 60]) {
      const values = Array.from({ length: count }, (_, i) => i);
      for (const data of [
        values,
        Object.fromEntries(values.map((i) => [`k${i}`, i])),
      ]) {
        const tree = paginateJson(data, options);
        const displayed = Object.values(tree.data);
        expect(displayed.slice(0, 30)).toEqual(values.slice(0, 30));
        expect(displayed).toHaveLength(
          Math.min(count, 30) + Number(count > 30),
        );
        expect(tree.getPage(displayed.at(-1))).toEqual(
          count > 30 ? { path: "[]", remaining: count - 30 } : undefined,
        );
      }
    }
  });

  it("keeps dotted, quoted, and empty keys distinct without reserving user strings", () => {
    const values = Array.from({ length: 40 }, (_, i) => i);
    const data = { "a.b": values, a: { b: values }, '"': values, "": values };
    const tree = paginateJson(data, { ...options, limits: { '["a.b"]': 60 } });
    expect(Reflect.get(tree.data, "a.b")).toEqual(values);
    for (const path of [["a", "b"], ['"'], [""]]) {
      const node = path.reduce(
        (node: object, key) => Reflect.get(node, key),
        tree.data,
      );
      expect(tree.getPage(Object.values(node).at(-1))).toEqual({
        path: JSON.stringify(path),
        remaining: 10,
      });
    }
    expect(tree.getPage("\u0000show_more\u000040|$")).toBeUndefined();
    expect(tree.getPage(Symbol("show more"))).toBeUndefined();
  });

  it("preserves __proto__ and empty keys when adding an object page", () => {
    const data = { "": 1, ["__proto__"]: 2, other: 3 };
    const tree = paginateJson(data, { limits: {}, pageSize: 2 });
    expect(Object.values(tree.data).slice(0, 2)).toEqual([1, 2]);
    expect(tree.getOriginal(tree.data)).toBe(data);
    expect(tree.getPage(Object.values(tree.data).at(-1))).toEqual({
      path: "[]",
      remaining: 1,
    });
  });

  it("does not traverse hidden branches, and caches visible children", () => {
    const read = vi.fn(() => [1, 2]);
    const hidden = vi.fn(() => [3, 4]);
    const data = {
      get visible() {
        return read();
      },
      get hidden() {
        return hidden();
      },
    };
    const tree = paginateJson(data, { limits: {}, pageSize: 1 });
    expect(read).not.toHaveBeenCalled();
    const first = Reflect.get(tree.data, "visible");
    expect(Reflect.get(tree.data, "visible")).toBe(first);
    expect(read).toHaveBeenCalledOnce();
    expect(hidden).not.toHaveBeenCalled();
  });

  it("paginates deep branches without a depth cutoff", () => {
    const data = {
      deep: {
        more: {
          levels: {
            still: {
              going: {
                deeper: { rows: Array.from({ length: 100 }, (_, i) => i) },
              },
            },
          },
        },
      },
    };
    const tree = paginateJson(data, options);
    const keys = ["deep", "more", "levels", "still", "going", "deeper", "rows"];
    const rows = keys.reduce(
      (node: object, key) => Reflect.get(node, key),
      tree.data,
    );
    expect(Object.values(rows)).toHaveLength(31);
    expect(tree.getPage(Object.values(rows).at(-1))).toEqual({
      path: JSON.stringify(keys),
      remaining: 70,
    });
  });

  it("preserves non-JSON objects and does not mutate input", () => {
    const date = new Date("2026-01-01");
    const data = Object.freeze({ date, values: Object.freeze([1, 2, 3]) });
    const tree = paginateJson(data, { limits: {}, pageSize: 2 });
    expect(Reflect.get(tree.data, "date")).toBe(date);
    expect(Object.values(Reflect.get(tree.data, "values"))).toHaveLength(3);
    expect(data.values).toEqual([1, 2, 3]);
  });
});

describe("pagination negative cases", () => {
  it("does not overwrite empty or NUL keys with pagination controls", () => {
    const data = { "": "empty", "\0": "nul", "\0\0": "two", last: "last" };
    const tree = paginateJson(data, { limits: {}, pageSize: 3 });
    expect(Object.values(tree.data).slice(0, 3)).toEqual([
      "empty",
      "nul",
      "two",
    ]);
    expect(tree.getPage(Object.values(tree.data).at(-1))).toEqual({
      path: "[]",
      remaining: 1,
    });
    expect(Object.keys(data)).toEqual(["", "\0", "\0\0", "last"]);
  });

  it("does not accept page markers from another tree", () => {
    const first = paginateJson([1, 2], { limits: {}, pageSize: 1 });
    const second = paginateJson([3, 4], { limits: {}, pageSize: 1 });
    expect(second.getPage(Object.values(first.data).at(-1))).toBeUndefined();
  });

  it("does not read values beyond the visible page", () => {
    const data = {
      visible: 1,
      get hidden() {
        throw new Error("hidden value read");
      },
    };
    const tree = paginateJson(data, { limits: {}, pageSize: 1 });
    expect(Object.values(tree.data)[0]).toBe(1);
    expect(tree.getOriginal(tree.data)).toBe(data);
  });

  it("does not expose inherited or non-enumerable fields", () => {
    const data = Object.defineProperty({ visible: 1 }, "hidden", { value: 2 });
    const tree = paginateJson(data, { limits: {}, pageSize: 30 });
    expect(Object.entries(tree.data)).toEqual([["visible", 1]]);
    expect(Reflect.get(tree.data, "toString")).toBeUndefined();
  });
});
