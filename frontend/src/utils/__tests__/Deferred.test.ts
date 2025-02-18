/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { Deferred } from "../Deferred";

describe("Deferred", () => {
  it("should resolve correctly", async () => {
    const deferred = new Deferred<number>();
    expect(deferred.status).toBe("pending");

    const value = 42;
    deferred.resolve(value);
    expect(deferred.status).toBe("resolved");

    const result = await deferred.promise;
    expect(result).toBe(value);
  });

  it("should reject correctly", async () => {
    const deferred = new Deferred<number>();
    expect(deferred.status).toBe("pending");

    const error = new Error("test error");
    deferred.reject(error);
    expect(deferred.status).toBe("rejected");

    await expect(deferred.promise).rejects.toThrow(error);
  });

  it("should handle promise-like values in resolve", async () => {
    const deferred = new Deferred<string>();
    const promiseValue = Promise.resolve("test");
    deferred.resolve(promiseValue);
    expect(deferred.status).toBe("resolved");

    const result = await deferred.promise;
    expect(result).toBe("test");
  });
});
