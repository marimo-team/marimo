/* Copyright 2024 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { TimedCache } from "../timed-cache";

describe("TimedCache", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("basic get/set operations", () => {
    const cache = new TimedCache<string>({ ttl: 1000 });

    cache.set("key1", "value1");
    cache.set("key2", "value2");

    expect(cache.get("key1")).toBe("value1");
    expect(cache.get("key2")).toBe("value2");
    expect(cache.get("nonexistent")).toBeUndefined();
  });

  test("returns undefined for expired entries", () => {
    const cache = new TimedCache<string>({ ttl: 1000 });

    cache.set("key1", "value1");
    expect(cache.get("key1")).toBe("value1");

    vi.advanceTimersByTime(1001);
    expect(cache.get("key1")).toBeUndefined();
  });

  test("entries within TTL remain accessible", () => {
    const cache = new TimedCache<string>({ ttl: 1000 });

    cache.set("key1", "value1");

    // within TTL
    vi.advanceTimersByTime(500);

    expect(cache.get("key1")).toBe("value1");

    // still within TTL
    vi.advanceTimersByTime(499);

    expect(cache.get("key1")).toBe("value1");
  });

  test("cleanup removes expired entries", () => {
    const cache = new TimedCache<string>({ ttl: 1000 });

    cache.set("key1", "value1");
    cache.set("key2", "value2");

    // expire key1
    vi.advanceTimersByTime(1001);

    // new key triggers cleanup
    cache.set("key3", "value3");

    // key2 triggers cleanup
    expect(cache.get("key2")).toBeUndefined();
    expect(cache.get("key3")).toBe("value3");
  });

  test("mixed expiry scenarios", () => {
    const cache = new TimedCache<number>({ ttl: 1000 });

    cache.set("early", 1);

    vi.advanceTimersByTime(500);
    cache.set("mid", 2);

    vi.advanceTimersByTime(500);
    cache.set("late", 3);

    // At this point: early is at 1000ms (not yet expired), mid is at 500ms, late is fresh
    expect(cache.get("early")).toBe(1);
    expect(cache.get("mid")).toBe(2);
    expect(cache.get("late")).toBe(3);

    // Advance 1ms more to expire early (1001ms total)
    vi.advanceTimersByTime(1);

    expect(cache.get("early")).toBeUndefined();
    expect(cache.get("mid")).toBe(2);
    expect(cache.get("late")).toBe(3);

    // Advance another 500ms to expire mid (1001ms total)
    vi.advanceTimersByTime(500);

    expect(cache.get("mid")).toBeUndefined();
    expect(cache.get("late")).toBe(3);
  });

  test("updating existing key resets timestamp", () => {
    const cache = new TimedCache<string>({ ttl: 1000 });

    cache.set("key1", "value1");

    // Advance time close to expiry
    vi.advanceTimersByTime(900);

    // Update the key
    cache.set("key1", "updated_value");

    // Advance time past original expiry
    vi.advanceTimersByTime(200);

    // Should still be accessible with updated value
    expect(cache.get("key1")).toBe("updated_value");
  });

  test("clear removes all entries", () => {
    const cache = new TimedCache<string>({ ttl: 1000 });

    cache.set("key1", "value1");
    cache.set("key2", "value2");
    cache.set("key3", "value3");

    expect(cache.get("key1")).toBe("value1");
    expect(cache.get("key2")).toBe("value2");

    cache.clear();

    expect(cache.get("key1")).toBeUndefined();
    expect(cache.get("key2")).toBeUndefined();
    expect(cache.get("key3")).toBeUndefined();
  });

  test("zero TTL expires immediately", () => {
    const cache = new TimedCache<string>({ ttl: 0 });

    cache.set("key1", "value1");

    // With TTL 0, any passage of time should expire the entry
    vi.advanceTimersByTime(1);
    expect(cache.get("key1")).toBeUndefined();
  });
});
