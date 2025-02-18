/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import {
  arrayDelete,
  arrayInsert,
  arrayMove,
  arrayInsertMany,
  arrayShallowEquals,
  Arrays,
  arrayToggle,
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect(arrayToggle(undefined as any, 1)).toEqual([1]);
    });

    it("should handle empty array", () => {
      expect(arrayToggle([], 1)).toEqual([1]);
    });
  });
});
