/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { withTimeout } from "../utils";

describe("withTimeout", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns an operation result and clears the timeout", async () => {
    vi.useFakeTimers();

    await expect(
      withTimeout(Promise.resolve("done"), 1_000, "Timed out"),
    ).resolves.toBe("done");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("rejects when an operation does not finish in time", async () => {
    vi.useFakeTimers();
    const pending = new Promise<never>(() => undefined);
    const result = expect(
      withTimeout(pending, 1_000, "Timed out"),
    ).rejects.toThrow("Timed out");

    await vi.advanceTimersByTimeAsync(1_000);
    await result;
  });
});
