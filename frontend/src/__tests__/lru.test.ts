/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { LRUCache } from "../utils/lru";

describe("LRUCache", () => {
  test("basic get/set operations", () => {
    const cache = new LRUCache<string, number>(3);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.set("c", 3);

    expect(cache.get("a")).toBe(1);
    expect(cache.get("b")).toBe(2);
    expect(cache.get("c")).toBe(3);
  });

  test("evicts least recently used item when over capacity", () => {
    const cache = new LRUCache<string, number>(3);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.set("c", 3);
    cache.set("d", 4);

    // "a" should be evicted as it was the least recently used
    expect(cache.get("a")).toBeUndefined();
    expect(cache.get("b")).toBe(2);
    expect(cache.get("c")).toBe(3);
    expect(cache.get("d")).toBe(4);
  });

  test("accessing an item makes it most recently used", () => {
    const cache = new LRUCache<string, number>(3);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.set("c", 3);

    // Access "a", making it most recently used
    cache.get("a");
    cache.set("d", 4);

    // "b" should be evicted as it becomes the least recently used
    expect(cache.get("b")).toBeUndefined();
    expect(cache.get("a")).toBe(1);
    expect(cache.get("c")).toBe(3);
    expect(cache.get("d")).toBe(4);
  });

  test("updating existing key maintains order", () => {
    const cache = new LRUCache<string, number>(3);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.set("c", 3);

    // Update "a"
    cache.set("a", 10);
    cache.set("d", 4);

    // "b" should be evicted as "a" was moved to most recent
    expect(cache.get("b")).toBeUndefined();
    expect(cache.get("a")).toBe(10);
    expect(cache.get("c")).toBe(3);
    expect(cache.get("d")).toBe(4);
  });

  test("keys() returns iterator in order", () => {
    const cache = new LRUCache<string, number>(3);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.set("c", 3);

    const keys = [...cache.keys()];
    expect(keys).toEqual(["a", "b", "c"]);
  });
});
