/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { Sets } from "../sets";

describe("Sets", () => {
  describe("merge", () => {
    it("should merge empty sets", () => {
      const result = Sets.merge(new Set(), new Set());
      expect(result.size).toBe(0);
    });

    it("should merge sets with unique values", () => {
      const set1 = new Set([1, 2]);
      const set2 = new Set([3, 4]);
      const result = Sets.merge(set1, set2);
      expect([...result]).toEqual([1, 2, 3, 4]);
    });

    it("should handle overlapping values", () => {
      const set1 = new Set([1, 2, 3]);
      const set2 = new Set([2, 3, 4]);
      const result = Sets.merge(set1, set2);
      expect([...result]).toEqual([1, 2, 3, 4]);
    });

    it("should merge multiple sets", () => {
      const set1 = new Set([1]);
      const set2 = new Set([2]);
      const set3 = new Set([3]);
      const result = Sets.merge(set1, set2, set3);
      expect([...result]).toEqual([1, 2, 3]);
    });

    it("should handle sets with different types", () => {
      const set1 = new Set(["a", "b"]);
      const set2 = new Set(["b", "c"]);
      const result = Sets.merge(set1, set2);
      expect([...result]).toEqual(["a", "b", "c"]);
    });
  });
});
