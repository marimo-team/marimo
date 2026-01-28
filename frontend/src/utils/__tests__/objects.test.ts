/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { Objects } from "../objects";

describe("Objects", () => {
  describe("EMPTY", () => {
    it("should be an empty frozen object", () => {
      expect(Objects.EMPTY).toEqual({});
      expect(Object.isFrozen(Objects.EMPTY)).toBe(true);
    });
  });

  describe("mapValues", () => {
    it("should map values of an object", () => {
      const obj = { a: 1, b: 2, c: 3 };
      const result = Objects.mapValues(obj, (v) => v * 2);
      expect(result).toEqual({ a: 2, b: 4, c: 6 });
    });

    it("should pass key as second argument", () => {
      const obj = { a: 1, b: 2 };
      const result = Objects.mapValues(obj, (v, k) => `${k}:${v}`);
      expect(result).toEqual({ a: "a:1", b: "b:2" });
    });

    it("should handle empty objects", () => {
      const result = Objects.mapValues({}, (v) => v);
      expect(result).toEqual({});
    });

    it("should return falsy input unchanged", () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect(Objects.mapValues(null as any, (v) => v)).toBe(null);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect(Objects.mapValues(undefined as any, (v) => v)).toBe(undefined);
    });
  });

  describe("fromEntries", () => {
    it("should create object from entries", () => {
      const entries: [string, number][] = [
        ["a", 1],
        ["b", 2],
      ];
      expect(Objects.fromEntries(entries)).toEqual({ a: 1, b: 2 });
    });

    it("should handle empty entries", () => {
      expect(Objects.fromEntries([])).toEqual({});
    });

    it("should handle numeric keys", () => {
      const entries: [number, string][] = [
        [1, "a"],
        [2, "b"],
      ];
      expect(Objects.fromEntries(entries)).toEqual({ 1: "a", 2: "b" });
    });
  });

  describe("entries", () => {
    it("should return entries of an object", () => {
      const obj = { a: 1, b: 2 };
      const entries = Objects.entries(obj);
      expect(entries).toContainEqual(["a", 1]);
      expect(entries).toContainEqual(["b", 2]);
      expect(entries).toHaveLength(2);
    });

    it("should handle empty objects", () => {
      expect(Objects.entries({})).toEqual([]);
    });
  });

  describe("keys", () => {
    it("should return keys of an object", () => {
      const obj = { a: 1, b: 2, c: 3 };
      const keys = Objects.keys(obj);
      expect(keys).toContain("a");
      expect(keys).toContain("b");
      expect(keys).toContain("c");
      expect(keys).toHaveLength(3);
    });

    it("should handle empty objects", () => {
      expect(Objects.keys({})).toEqual([]);
    });
  });

  describe("size", () => {
    it("should return the number of keys", () => {
      expect(Objects.size({ a: 1, b: 2, c: 3 })).toBe(3);
    });

    it("should return 0 for empty objects", () => {
      expect(Objects.size({})).toBe(0);
    });
  });

  describe("keyBy", () => {
    it("should key items by specified key function", () => {
      const items = [
        { id: "a", value: 1 },
        { id: "b", value: 2 },
      ];
      const result = Objects.keyBy(items, (item) => item.id);
      expect(result).toEqual({
        a: { id: "a", value: 1 },
        b: { id: "b", value: 2 },
      });
    });

    it("should skip items with undefined keys", () => {
      const items = [
        { id: "a", value: 1 },
        { id: undefined as unknown as string, value: 2 },
        { id: "c", value: 3 },
      ];
      const result = Objects.keyBy(items, (item) => item.id);
      expect(result).toEqual({
        a: { id: "a", value: 1 },
        c: { id: "c", value: 3 },
      });
    });

    it("should handle empty arrays", () => {
      expect(Objects.keyBy([], (item) => item)).toEqual({});
    });

    it("should use last item when keys collide", () => {
      const items = [
        { id: "a", value: 1 },
        { id: "a", value: 2 },
      ];
      const result = Objects.keyBy(items, (item) => item.id);
      expect(result).toEqual({ a: { id: "a", value: 2 } });
    });
  });

  describe("collect", () => {
    it("should collect and transform items", () => {
      const items = [
        { id: "a", value: 1 },
        { id: "b", value: 2 },
      ];
      const result = Objects.collect(
        items,
        (item) => item.id,
        (item) => item.value * 2,
      );
      expect(result).toEqual({ a: 2, b: 4 });
    });

    it("should handle empty arrays", () => {
      const result = Objects.collect(
        [],
        (item) => item,
        (item) => item,
      );
      expect(result).toEqual({});
    });
  });

  describe("groupBy", () => {
    it("should group items by key", () => {
      const items = [
        { category: "a", value: 1 },
        { category: "b", value: 2 },
        { category: "a", value: 3 },
      ];
      const result = Objects.groupBy(
        items,
        (item) => item.category,
        (item) => item.value,
      );
      expect(result).toEqual({
        a: [1, 3],
        b: [2],
      });
    });

    it("should skip items with undefined keys", () => {
      const items = [
        { category: "a", value: 1 },
        { category: undefined as unknown as string, value: 2 },
        { category: "a", value: 3 },
      ];
      const result = Objects.groupBy(
        items,
        (item) => item.category,
        (item) => item.value,
      );
      expect(result).toEqual({ a: [1, 3] });
    });

    it("should handle empty arrays", () => {
      const result = Objects.groupBy(
        [],
        (item) => item,
        (item) => item,
      );
      expect(result).toEqual({});
    });
  });

  describe("filter", () => {
    it("should filter object entries by predicate", () => {
      const obj = { a: 1, b: 2, c: 3, d: 4 };
      const result = Objects.filter(obj, (v) => v % 2 === 0);
      expect(result).toEqual({ b: 2, d: 4 });
    });

    it("should pass key as second argument", () => {
      const obj = { a: 1, b: 2, c: 3 };
      const result = Objects.filter(obj, (_, k) => k !== "b");
      expect(result).toEqual({ a: 1, c: 3 });
    });

    it("should handle empty objects", () => {
      const result = Objects.filter({}, () => true);
      expect(result).toEqual({});
    });

    it("should return empty object when nothing matches", () => {
      const obj = { a: 1, b: 2 };
      const result = Objects.filter(obj, () => false);
      expect(result).toEqual({});
    });
  });

  describe("omit", () => {
    it("should omit specified keys from object", () => {
      const obj = { a: 1, b: 2, c: 3 };
      const result = Objects.omit(obj, ["b"]);
      expect(result).toEqual({ a: 1, c: 3 });
    });

    it("should omit multiple keys", () => {
      const obj = { a: 1, b: 2, c: 3, d: 4 };
      const result = Objects.omit(obj, ["a", "c"]);
      expect(result).toEqual({ b: 2, d: 4 });
    });

    it("should handle keys provided as Set", () => {
      const obj = { a: 1, b: 2, c: 3 };
      const result = Objects.omit(obj, new Set(["a", "c"] as const));
      expect(result).toEqual({ b: 2 });
    });

    it("should handle omitting non-existent keys", () => {
      const obj = { a: 1, b: 2 };
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const result = Objects.omit(obj, ["c" as any]);
      expect(result).toEqual({ a: 1, b: 2 });
    });

    it("should return all properties when omitting empty array", () => {
      const obj = { a: 1, b: 2 };
      const result = Objects.omit(obj, []);
      expect(result).toEqual({ a: 1, b: 2 });
    });
  });
});
