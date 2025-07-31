/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { shallowCompare } from "../shallow-compare";

describe("shallowCompare", () => {
  test("compares primitive values", () => {
    expect(shallowCompare(1, 1)).toBe(true);
    expect(shallowCompare("a", "a")).toBe(true);
    expect(shallowCompare(true, true)).toBe(true);
    expect(shallowCompare(null, null)).toBe(true);
    expect(shallowCompare(undefined, undefined)).toBe(true);

    expect(shallowCompare(1, 2)).toBe(false);
    expect(shallowCompare("a", "b")).toBe(false);
    expect(shallowCompare(true, false)).toBe(false);
    expect(shallowCompare(null, undefined)).toBe(false);
  });

  test("compares arrays", () => {
    expect(shallowCompare([], [])).toBe(true);
    expect(shallowCompare([1, 2, 3], [1, 2, 3])).toBe(true);
    expect(shallowCompare(["a", "b"], ["a", "b"])).toBe(true);

    expect(shallowCompare([1, 2, 3], [1, 2, 4])).toBe(false);
    expect(shallowCompare([1, 2], [1, 2, 3])).toBe(false);
    expect(shallowCompare(["a", "b"], ["b", "a"])).toBe(false);
  });

  test("compares objects", () => {
    expect(shallowCompare({}, {})).toBe(true);
    expect(shallowCompare({ a: 1, b: 2 }, { a: 1, b: 2 })).toBe(true);
    expect(shallowCompare({ a: "x", b: "y" }, { a: "x", b: "y" })).toBe(true);

    expect(shallowCompare({ a: 1, b: 2 }, { a: 1, b: 3 })).toBe(false);
    expect(shallowCompare({ a: 1, b: 2 }, { a: 1, c: 2 })).toBe(false);
    expect(shallowCompare({ a: 1 }, { a: 1, b: 2 })).toBe(false);
  });

  test("compares nested structures", () => {
    const subObj1 = { c: 2 };
    const obj1 = { a: 1, b: subObj1 };
    const obj2 = { a: 1, b: subObj1 };
    const obj3 = { a: 1, b: { c: 2 } };

    expect(shallowCompare(obj1, obj2)).toBe(true);
    expect(shallowCompare(obj1, obj3)).toBe(false);

    const arr1 = [1, subObj1];
    const arr2 = [1, subObj1];
    const arr3 = [1, { c: 2 }];

    expect(shallowCompare(arr1, arr2)).toBe(true);
    expect(shallowCompare(arr1, arr3)).toBe(false);
  });
});
