/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { MultiMap } from "../multi-map";

describe("MultiMap", () => {
  let multiMap: MultiMap<string, number>;

  beforeEach(() => {
    multiMap = new MultiMap<string, number>();
  });

  describe("constructor", () => {
    it("should create an empty MultiMap", () => {
      expect(multiMap.size).toBe(0);
    });
  });

  describe("get", () => {
    it("should return empty array for non-existent key", () => {
      expect(multiMap.get("nonexistent")).toEqual([]);
    });

    it("should return values for existing key", () => {
      multiMap.add("key1", 1);
      multiMap.add("key1", 2);
      expect(multiMap.get("key1")).toEqual([1, 2]);
    });
  });

  describe("set", () => {
    it("should set values for a key", () => {
      multiMap.set("key1", [1, 2, 3]);
      expect(multiMap.get("key1")).toEqual([1, 2, 3]);
    });

    it("should overwrite existing values", () => {
      multiMap.add("key1", 1);
      multiMap.set("key1", [4, 5, 6]);
      expect(multiMap.get("key1")).toEqual([4, 5, 6]);
    });

    it("should set empty array", () => {
      multiMap.set("key1", []);
      expect(multiMap.get("key1")).toEqual([]);
      expect(multiMap.has("key1")).toBe(true);
    });
  });

  describe("add", () => {
    it("should add value to new key", () => {
      multiMap.add("key1", 1);
      expect(multiMap.get("key1")).toEqual([1]);
    });

    it("should add value to existing key", () => {
      multiMap.add("key1", 1);
      multiMap.add("key1", 2);
      expect(multiMap.get("key1")).toEqual([1, 2]);
    });

    it("should handle multiple keys", () => {
      multiMap.add("key1", 1);
      multiMap.add("key2", 2);
      multiMap.add("key1", 3);
      expect(multiMap.get("key1")).toEqual([1, 3]);
      expect(multiMap.get("key2")).toEqual([2]);
    });
  });

  describe("has", () => {
    it("should return false for non-existent key", () => {
      expect(multiMap.has("nonexistent")).toBe(false);
    });

    it("should return true for existing key", () => {
      multiMap.add("key1", 1);
      expect(multiMap.has("key1")).toBe(true);
    });

    it("should return true for key with empty array", () => {
      multiMap.set("key1", []);
      expect(multiMap.has("key1")).toBe(true);
    });
  });

  describe("delete", () => {
    it("should return false for non-existent key", () => {
      expect(multiMap.delete("nonexistent")).toBe(false);
    });

    it("should delete existing key and return true", () => {
      multiMap.add("key1", 1);
      expect(multiMap.delete("key1")).toBe(true);
      expect(multiMap.has("key1")).toBe(false);
      expect(multiMap.get("key1")).toEqual([]);
    });

    it("should not affect other keys", () => {
      multiMap.add("key1", 1);
      multiMap.add("key2", 2);
      multiMap.delete("key1");
      expect(multiMap.has("key2")).toBe(true);
      expect(multiMap.get("key2")).toEqual([2]);
    });
  });

  describe("clear", () => {
    it("should clear empty MultiMap", () => {
      multiMap.clear();
      expect(multiMap.size).toBe(0);
    });

    it("should clear all keys and values", () => {
      multiMap.add("key1", 1);
      multiMap.add("key2", 2);
      multiMap.clear();
      expect(multiMap.size).toBe(0);
      expect(multiMap.has("key1")).toBe(false);
      expect(multiMap.has("key2")).toBe(false);
    });
  });

  describe("keys", () => {
    it("should return empty iterator for empty MultiMap", () => {
      const keys = [...multiMap.keys()];
      expect(keys).toEqual([]);
    });

    it("should return all keys", () => {
      multiMap.add("key1", 1);
      multiMap.add("key2", 2);
      multiMap.add("key3", 3);
      const keys = [...multiMap.keys()];
      expect(keys.sort()).toEqual(["key1", "key2", "key3"]);
    });
  });

  describe("values", () => {
    it("should return empty iterator for empty MultiMap", () => {
      const values = [...multiMap.values()];
      expect(values).toEqual([]);
    });

    it("should return all value arrays", () => {
      multiMap.add("key1", 1);
      multiMap.add("key1", 2);
      multiMap.add("key2", 3);
      const values = [...multiMap.values()];
      expect(values).toHaveLength(2);
      expect(values).toContainEqual([1, 2]);
      expect(values).toContainEqual([3]);
    });
  });

  describe("entries", () => {
    it("should return empty iterator for empty MultiMap", () => {
      const entries = [...multiMap.entries()];
      expect(entries).toEqual([]);
    });

    it("should return all key-value pairs", () => {
      multiMap.add("key1", 1);
      multiMap.add("key1", 2);
      multiMap.add("key2", 3);
      const entries = [...multiMap.entries()];
      expect(entries).toHaveLength(2);
      expect(entries).toContainEqual(["key1", [1, 2]]);
      expect(entries).toContainEqual(["key2", [3]]);
    });
  });

  describe("forEach", () => {
    it("should not call callback for empty MultiMap", () => {
      const callback = vi.fn();
      multiMap.forEach(callback);
      expect(callback).not.toHaveBeenCalled();
    });

    it("should call callback for each key-value pair", () => {
      multiMap.add("key1", 1);
      multiMap.add("key1", 2);
      multiMap.add("key2", 3);

      const callback = vi.fn();
      multiMap.forEach(callback);

      expect(callback).toHaveBeenCalledTimes(2);
      expect(callback).toHaveBeenCalledWith([1, 2], "key1", expect.any(Map));
      expect(callback).toHaveBeenCalledWith([3], "key2", expect.any(Map));
    });
  });

  describe("flatValues", () => {
    it("should return empty array for empty MultiMap", () => {
      expect(multiMap.flatValues()).toEqual([]);
    });

    it("should flatten all values into single array", () => {
      multiMap.add("key1", 1);
      multiMap.add("key1", 2);
      multiMap.add("key2", 3);
      multiMap.add("key3", 4);
      multiMap.add("key3", 5);

      const flattened = multiMap.flatValues();
      expect(flattened.sort()).toEqual([1, 2, 3, 4, 5]);
    });

    it("should handle empty arrays in values", () => {
      multiMap.set("key1", []);
      multiMap.add("key2", 1);
      multiMap.add("key2", 2);

      const flattened = multiMap.flatValues();
      expect(flattened.sort()).toEqual([1, 2]);
    });
  });

  describe("size", () => {
    it("should return 0 for empty MultiMap", () => {
      expect(multiMap.size).toBe(0);
    });

    it("should return number of keys", () => {
      multiMap.add("key1", 1);
      expect(multiMap.size).toBe(1);

      multiMap.add("key1", 2);
      expect(multiMap.size).toBe(1);

      multiMap.add("key2", 3);
      expect(multiMap.size).toBe(2);
    });

    it("should update when keys are deleted", () => {
      multiMap.add("key1", 1);
      multiMap.add("key2", 2);
      expect(multiMap.size).toBe(2);

      multiMap.delete("key1");
      expect(multiMap.size).toBe(1);

      multiMap.clear();
      expect(multiMap.size).toBe(0);
    });
  });

  describe("different key and value types", () => {
    it("should work with number keys and string values", () => {
      const numberKeyMap = new MultiMap<number, string>();
      numberKeyMap.add(1, "one");
      numberKeyMap.add(1, "uno");
      numberKeyMap.add(2, "two");

      expect(numberKeyMap.get(1)).toEqual(["one", "uno"]);
      expect(numberKeyMap.get(2)).toEqual(["two"]);
      expect(numberKeyMap.flatValues()).toEqual(["one", "uno", "two"]);
    });

    it("should work with object keys and values", () => {
      interface TestObj {
        id: number;
        name: string;
      }

      const objMap = new MultiMap<string, TestObj>();
      const obj1 = { id: 1, name: "test1" };
      const obj2 = { id: 2, name: "test2" };

      objMap.add("group1", obj1);
      objMap.add("group1", obj2);

      expect(objMap.get("group1")).toEqual([obj1, obj2]);
    });
  });

  describe("edge cases", () => {
    it("should handle undefined and null values", () => {
      const nullMap = new MultiMap<string, null | undefined>();
      nullMap.add("key1", null);
      nullMap.add("key1", undefined);

      expect(nullMap.get("key1")).toEqual([null, undefined]);
    });

    it("should handle duplicate values", () => {
      multiMap.add("key1", 1);
      multiMap.add("key1", 1);
      multiMap.add("key1", 1);

      expect(multiMap.get("key1")).toEqual([1, 1, 1]);
    });
  });
});
