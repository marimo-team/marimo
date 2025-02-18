/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { Maps } from "../maps";

describe("Maps", () => {
  describe("keyBy", () => {
    it("should create a map from an array using a key function", () => {
      const items = [
        { id: "1", value: "a" },
        { id: "2", value: "b" },
      ];
      const result = Maps.keyBy(items, (item) => item.id);
      expect(result.get("1")).toEqual({ id: "1", value: "a" });
      expect(result.get("2")).toEqual({ id: "2", value: "b" });
    });

    it("should handle duplicate keys by keeping the last value", () => {
      const items = [
        { id: "1", value: "a" },
        { id: "1", value: "b" },
      ];
      const result = Maps.keyBy(items, (item) => item.id);
      expect(result.size).toBe(1);
      expect(result.get("1")).toEqual({ id: "1", value: "b" });
    });
  });

  describe("collect", () => {
    it("should create a map with transformed values", () => {
      const items = [
        { id: "1", value: "a" },
        { id: "2", value: "b" },
      ];
      const result = Maps.collect(
        items,
        (item) => item.id,
        (item) => item.value.toUpperCase(),
      );
      expect(result.get("1")).toBe("A");
      expect(result.get("2")).toBe("B");
    });
  });

  describe("filterMap", () => {
    it("should filter map entries based on predicate", () => {
      const map = new Map([
        ["1", "a"],
        ["2", "b"],
        ["3", "c"],
      ]);
      const result = Maps.filterMap(map, (value) => value !== "b");
      expect(result.size).toBe(2);
      expect(result.get("1")).toBe("a");
      expect(result.get("2")).toBeUndefined();
      expect(result.get("3")).toBe("c");
    });

    it("should handle predicate with key", () => {
      const map = new Map([
        ["1", "a"],
        ["2", "b"],
        ["3", "c"],
      ]);
      const result = Maps.filterMap(map, (_, key) => key !== "2");
      expect(result.size).toBe(2);
      expect([...result.keys()]).toEqual(["1", "3"]);
    });
  });

  describe("mapValues", () => {
    it("should transform map values using mapper function", () => {
      const map = new Map([
        ["1", "a"],
        ["2", "b"],
      ]);
      const result = Maps.mapValues(map, (value) => value.toUpperCase());
      expect(result.get("1")).toBe("A");
      expect(result.get("2")).toBe("B");
    });

    it("should handle mapper with key", () => {
      const map = new Map([
        ["1", "a"],
        ["2", "b"],
      ]);
      const result = Maps.mapValues(map, (value, key) => `${key}:${value}`);
      expect(result.get("1")).toBe("1:a");
      expect(result.get("2")).toBe("2:b");
    });
  });
});
