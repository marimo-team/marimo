/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { memoizeLastValue, once } from "../once";

describe("once", () => {
  it("should call function only once", () => {
    const fn = vi.fn(() => "result");
    const onceFn = once(fn);

    const result1 = onceFn();
    const result2 = onceFn();

    expect(result1).toBe("result");
    expect(result2).toBe("result");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("should return the same result on subsequent calls", () => {
    let counter = 0;
    const fn = () => ++counter;
    const onceFn = once(fn);

    expect(onceFn()).toBe(1);
    expect(onceFn()).toBe(1);
    expect(onceFn()).toBe(1);
  });
});

describe("memoizeLastValue", () => {
  it("should memoize result for same arguments", () => {
    const fn = vi.fn((a: number, b: string) => `${a}-${b}`);
    const memoizedFn = memoizeLastValue(fn);

    const result1 = memoizedFn(1, "test");
    const result2 = memoizedFn(1, "test");

    expect(result1).toBe("1-test");
    expect(result2).toBe("1-test");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("should recompute for different arguments", () => {
    const fn = vi.fn((a: number) => a * 2);
    const memoizedFn = memoizeLastValue(fn);

    const result1 = memoizedFn(5);
    const result2 = memoizedFn(10);
    const result3 = memoizedFn(5); // Should recompute since args changed from previous call

    expect(result1).toBe(10);
    expect(result2).toBe(20);
    expect(result3).toBe(10);
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("should handle no arguments", () => {
    const fn = vi.fn(() => "no-args");
    const memoizedFn = memoizeLastValue(fn);

    const result1 = memoizedFn();
    const result2 = memoizedFn();

    expect(result1).toBe("no-args");
    expect(result2).toBe("no-args");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("should handle single argument", () => {
    const fn = vi.fn((x: number) => x + 1);
    const memoizedFn = memoizeLastValue(fn);

    expect(memoizedFn(5)).toBe(6);
    expect(memoizedFn(5)).toBe(6);
    expect(memoizedFn(3)).toBe(4);

    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("should handle multiple arguments", () => {
    const fn = vi.fn((a: number, b: string, c: boolean) => ({ a, b, c }));
    const memoizedFn = memoizeLastValue(fn);

    const result1 = memoizedFn(1, "hello", true);
    const result2 = memoizedFn(1, "hello", true);
    const result3 = memoizedFn(1, "hello", false);

    expect(result1).toEqual({ a: 1, b: "hello", c: true });
    expect(result2).toEqual({ a: 1, b: "hello", c: true });
    expect(result3).toEqual({ a: 1, b: "hello", c: false });
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("should use shallow comparison for objects", () => {
    const fn = vi.fn((obj: { x: number }) => obj.x * 2);
    const memoizedFn = memoizeLastValue(fn);

    const obj1 = { x: 5 };
    const obj2 = { x: 5 }; // Different reference but same content

    const result1 = memoizedFn(obj1);
    const result2 = memoizedFn(obj1); // Same reference
    const result3 = memoizedFn(obj2); // Different reference

    expect(result1).toBe(10);
    expect(result2).toBe(10);
    expect(result3).toBe(10);
    expect(fn).toHaveBeenCalledTimes(2); // obj1 (twice with same ref) and obj2 (different ref)
  });

  it("should handle arrays", () => {
    const fn = vi.fn((arr: number[]) => arr.reduce((sum, x) => sum + x, 0));
    const memoizedFn = memoizeLastValue(fn);

    const result1 = memoizedFn([1, 2, 3]);
    const result2 = memoizedFn([1, 2, 3]); // Different array reference but same content
    const result3 = memoizedFn([1, 2, 4]); // Different content

    expect(result1).toBe(6);
    expect(result2).toBe(6);
    expect(result3).toBe(7);
    expect(fn).toHaveBeenCalledTimes(3); // Each call has different array reference
  });

  it("should handle mixed argument types", () => {
    const fn = vi.fn(
      (num: number, str: string, arr: number[], obj: { key: string }) =>
        `${num}-${str}-${arr.length}-${obj.key}`,
    );
    const memoizedFn = memoizeLastValue(fn);

    const arr = [1, 2, 3];
    const obj = { key: "test" };

    const result1 = memoizedFn(42, "hello", arr, obj);
    const result2 = memoizedFn(42, "hello", arr, obj); // Same references
    const result3 = memoizedFn(42, "hello", [1, 2, 3], { key: "test" }); // Different references

    expect(result1).toBe("42-hello-3-test");
    expect(result2).toBe("42-hello-3-test");
    expect(result3).toBe("42-hello-3-test");
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("should handle undefined and null arguments", () => {
    const fn = vi.fn((a?: string, b?: null) => `${a}-${b}`);
    const memoizedFn = memoizeLastValue(fn);

    const result1 = memoizedFn(undefined, null);
    const result2 = memoizedFn(undefined, null);
    const result3 = memoizedFn("test", null);

    expect(result1).toBe("undefined-null");
    expect(result2).toBe("undefined-null");
    expect(result3).toBe("test-null");
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("should preserve function context", () => {
    const context = {
      value: 10,
      fn: vi.fn(function (this: { value: number }, multiplier: number) {
        return this.value * multiplier;
      }),
    };

    const memoizedFn = memoizeLastValue(context.fn);

    const result1 = memoizedFn.call(context, 2);
    const result2 = memoizedFn.call(context, 2);

    expect(result1).toBe(20);
    expect(result2).toBe(20);
    expect(context.fn).toHaveBeenCalledTimes(1);
  });

  it("should handle functions that throw errors", () => {
    const error = new Error("test error");
    const fn = vi.fn(() => {
      throw error;
    });
    const memoizedFn = memoizeLastValue(fn);

    expect(() => memoizedFn()).toThrow("test error");
    expect(() => memoizedFn()).toThrow("test error"); // Should throw cached error
    expect(fn).toHaveBeenCalledTimes(1); // Error should be memoized too
  });
});
