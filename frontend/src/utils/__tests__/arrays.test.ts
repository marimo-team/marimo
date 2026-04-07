/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  Arrays,
  arrayDelete,
  arrayInsert,
  arrayInsertMany,
  arrayMove,
  arrayShallowEquals,
  arrayToggle,
  getNextIndex,
  partition,
  range,
  sortBy,
  uniq,
} from "../arrays";

describe("arrays", () => {
  describe("arrayDelete", () => {
    it("should delete an element at the specified index", () => {
      expect(arrayDelete([1, 2, 3], 1)).toEqual([1, 3]);
    });

    it("should handle first and last elements", () => {
      expect(arrayDelete([1, 2, 3], 0)).toEqual([2, 3]);
      expect(arrayDelete([1, 2, 3], 2)).toEqual([1, 2]);
    });
  });

  describe("arrayInsert", () => {
    it("should insert an element at the specified index", () => {
      expect(arrayInsert([1, 2, 3], 1, 4)).toEqual([1, 4, 2, 3]);
    });

    it("should clamp index to array bounds", () => {
      expect(arrayInsert([1, 2, 3], -1, 4)).toEqual([4, 1, 2, 3]);
      expect(arrayInsert([1, 2, 3], 5, 4)).toEqual([1, 2, 3, 4]);
    });

    it("should handle empty arrays", () => {
      expect(arrayInsert([], 0, 1)).toEqual([1]);
    });
  });

  describe("arrayMove", () => {
    it("should move an element from one index to another", () => {
      expect(arrayMove([1, 2, 3], 0, 2)).toEqual([2, 3, 1]);
      expect(arrayMove([1, 2, 3], 2, 0)).toEqual([3, 1, 2]);
    });

    it("should handle adjacent moves", () => {
      expect(arrayMove([1, 2, 3], 0, 1)).toEqual([2, 1, 3]);
      expect(arrayMove([1, 2, 3], 1, 0)).toEqual([2, 1, 3]);
    });
  });

  describe("arrayInsertMany", () => {
    it("should insert multiple elements at the specified index", () => {
      expect(arrayInsertMany([1, 2, 3], 1, [4, 5])).toEqual([1, 4, 5, 2, 3]);
    });

    it("should handle empty target array", () => {
      expect(arrayInsertMany([], 0, [1, 2])).toEqual([1, 2]);
    });

    it("should handle empty insert array", () => {
      expect(arrayInsertMany([1, 2, 3], 1, [])).toEqual([1, 2, 3]);
    });

    it("should clamp index to array bounds", () => {
      expect(arrayInsertMany([1, 2, 3], -1, [4, 5])).toEqual([4, 5, 1, 2, 3]);
      expect(arrayInsertMany([1, 2, 3], 5, [4, 5])).toEqual([1, 2, 3, 4, 5]);
    });
  });

  describe("arrayShallowEquals", () => {
    it("should return true for identical arrays", () => {
      expect(arrayShallowEquals([1, 2, 3], [1, 2, 3])).toBe(true);
    });

    it("should return false for arrays with different lengths", () => {
      expect(arrayShallowEquals([1, 2], [1, 2, 3])).toBe(false);
    });

    it("should return false for arrays with same length but different elements", () => {
      expect(arrayShallowEquals([1, 2, 3], [1, 2, 4])).toBe(false);
    });

    it("should handle empty arrays", () => {
      expect(arrayShallowEquals([], [])).toBe(true);
    });

    it("should use strict equality for objects", () => {
      const obj = { a: 1 };
      expect(arrayShallowEquals([obj], [obj])).toBe(true);
      expect(arrayShallowEquals([obj], [{ a: 1 }])).toBe(false);
    });
  });

  describe("Arrays.zip", () => {
    it("should zip two arrays of equal length", () => {
      expect(Arrays.zip([1, 2], ["a", "b"])).toEqual([
        [1, "a"],
        [2, "b"],
      ]);
    });

    it("should throw for arrays of different lengths", () => {
      expect(() => Arrays.zip([1, 2], ["a"])).toThrow();
    });

    it("should handle empty arrays", () => {
      expect(Arrays.zip([], [])).toEqual([]);
    });
  });

  describe("arrayToggle", () => {
    it("should add item if not present", () => {
      expect(arrayToggle([1, 2], 3)).toEqual([1, 2, 3]);
    });

    it("should remove item if present", () => {
      expect(arrayToggle([1, 2, 3], 2)).toEqual([1, 3]);
    });

    it("should handle undefined/null array", () => {
      // oxlint-disable-next-line typescript/no-explicit-any
      expect(arrayToggle(undefined as any, 1)).toEqual([1]);
    });

    it("should handle empty array", () => {
      expect(arrayToggle([], 1)).toEqual([1]);
    });
  });
});

describe("range", () => {
  it("should create an array of numbers from 0 to length - 1", () => {
    expect(range(5)).toEqual([0, 1, 2, 3, 4]);
  });

  it("should return empty array for 0", () => {
    expect(range(0)).toEqual([]);
  });

  it("should return single element for 1", () => {
    expect(range(1)).toEqual([0]);
  });
});

describe("uniq", () => {
  it("should remove duplicate numbers", () => {
    expect(uniq([1, 2, 2, 3, 1])).toEqual([1, 2, 3]);
  });

  it("should remove duplicate strings", () => {
    expect(uniq(["a", "b", "a", "c"])).toEqual(["a", "b", "c"]);
  });

  it("should handle empty array", () => {
    expect(uniq([])).toEqual([]);
  });

  it("should preserve order of first occurrence", () => {
    expect(uniq([3, 1, 2, 1, 3])).toEqual([3, 1, 2]);
  });
});

describe("sortBy", () => {
  it("should sort by a numeric key", () => {
    const items = [{ n: 3 }, { n: 1 }, { n: 2 }];
    expect(sortBy(items, (x) => x.n)).toEqual([{ n: 1 }, { n: 2 }, { n: 3 }]);
  });

  it("should sort by a string key", () => {
    const items = [{ name: "charlie" }, { name: "alice" }, { name: "bob" }];
    expect(sortBy(items, (x) => x.name)).toEqual([
      { name: "alice" },
      { name: "bob" },
      { name: "charlie" },
    ]);
  });

  it("should not mutate the original array", () => {
    const arr = [3, 1, 2];
    sortBy(arr, (x) => x);
    expect(arr).toEqual([3, 1, 2]);
  });

  it("should handle empty array", () => {
    expect(sortBy([], (x) => x)).toEqual([]);
  });

  it("should sort null/undefined keys last", () => {
    const items = [
      { name: "b", v: undefined },
      { name: "a", v: 1 },
      { name: "c", v: null },
      { name: "d", v: 2 },
    ];
    const result = sortBy(items, (x) => x.v);
    expect(result.map((x) => x.name)).toEqual(["a", "d", "b", "c"]);
  });

  it("should sort numeric keys correctly", () => {
    const items = [{ v: 10 }, { v: 2 }, { v: 1 }, { v: 20 }];
    expect(sortBy(items, (x) => x.v)).toEqual([
      { v: 1 },
      { v: 2 },
      { v: 10 },
      { v: 20 },
    ]);
  });
});

describe("partition", () => {
  it("should split array by predicate", () => {
    const [evens, odds] = partition([1, 2, 3, 4, 5], (n) => n % 2 === 0);
    expect(evens).toEqual([2, 4]);
    expect(odds).toEqual([1, 3, 5]);
  });

  it("should handle all matching", () => {
    const [pass, fail] = partition([2, 4, 6], (n) => n % 2 === 0);
    expect(pass).toEqual([2, 4, 6]);
    expect(fail).toEqual([]);
  });

  it("should handle none matching", () => {
    const [pass, fail] = partition([1, 3, 5], (n) => n % 2 === 0);
    expect(pass).toEqual([]);
    expect(fail).toEqual([1, 3, 5]);
  });

  it("should handle empty array", () => {
    const [pass, fail] = partition([], () => true);
    expect(pass).toEqual([]);
    expect(fail).toEqual([]);
  });

  it("should work with string predicates", () => {
    const [long, short] = partition(
      ["hi", "hello", "yo", "greetings"],
      (s) => s.length > 3,
    );
    expect(long).toEqual(["hello", "greetings"]);
    expect(short).toEqual(["hi", "yo"]);
  });
});

describe("getNextIndex", () => {
  it("should return 0 if listLength is 0", () => {
    expect(getNextIndex(null, 0, "up")).toBe(0);
    expect(getNextIndex(null, 0, "down")).toBe(0);
    expect(getNextIndex(0, 0, "up")).toBe(0);
    expect(getNextIndex(0, 0, "down")).toBe(0);
  });

  it("should return 0 if currentIndex is null and direction is up", () => {
    expect(getNextIndex(null, 10, "up")).toBe(0);
  });

  it("should return last index if currentIndex is null and direction is down", () => {
    expect(getNextIndex(null, 10, "down")).toBe(9);
  });

  it("should return the next index in the list", () => {
    expect(getNextIndex(0, 10, "up")).toBe(1);
  });

  it("should wrap around to the start of the list", () => {
    expect(getNextIndex(9, 10, "up")).toBe(0);
  });

  it("should return next index in middle of list", () => {
    expect(getNextIndex(5, 10, "up")).toBe(6);
  });

  it("should return previous index in middle of list", () => {
    expect(getNextIndex(5, 10, "down")).toBe(4);
  });

  it("should wrap around to the end of the list", () => {
    expect(getNextIndex(0, 10, "down")).toBe(9);
  });

  it("should return the previous index in the list", () => {
    expect(getNextIndex(1, 10, "down")).toBe(0);
  });
});
