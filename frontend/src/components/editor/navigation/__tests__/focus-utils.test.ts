/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { raf2 } from "../focus-utils";

describe("raf2", () => {
  it("should call callback after two animation frames", async () => {
    const callback = vi.fn();

    raf2(callback);

    expect(callback).not.toHaveBeenCalled();

    await new Promise((resolve) => requestAnimationFrame(resolve));
    expect(callback).not.toHaveBeenCalled();

    await new Promise((resolve) => requestAnimationFrame(resolve));
    expect(callback).toHaveBeenCalledTimes(1);
  });
});
