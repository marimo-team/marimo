/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { batch } from "../batch-requests";

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

describe("batch", () => {
  it("should return the same promise for calls with the same key", async () => {
    const loader = vi.fn().mockImplementation(async (arg) => {
      await sleep(10);
      return "response";
    });
    const batchedLoader = batch(loader, JSON.stringify);

    const promise1 = batchedLoader("arg1");
    const promise2 = batchedLoader("arg1");

    expect(promise1).toBe(promise2);
    expect(loader).toHaveBeenCalledTimes(1);

    const result = await promise1;
    expect(result).toBe("response");
  });

  it("should call loader again after the first promise resolves", async () => {
    const loader = vi.fn().mockImplementation(async (arg) => {
      await sleep(10);
      return "response";
    });
    const batchedLoader = batch(loader, JSON.stringify);

    const promise1 = batchedLoader("arg1");
    await promise1;

    const promise2 = batchedLoader("arg1");
    expect(promise1).not.toBe(promise2);
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("should handle different keys separately", async () => {
    const loader = vi.fn().mockImplementation(async (arg) => {
      await sleep(10);
      return "response";
    });
    const batchedLoader = batch(loader, JSON.stringify);

    const promise1 = batchedLoader("arg1");
    const promise2 = batchedLoader("arg2");

    expect(promise1).not.toBe(promise2);
    expect(loader).toHaveBeenCalledTimes(2);

    const result1 = await promise1;
    const result2 = await promise2;
    expect(result1).toBe("response");
    expect(result2).toBe("response");
  });
});
