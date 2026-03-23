/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { handleDragging } from "../utils";

describe("handleDragging", () => {
  it("should dispatch a resize event after dragging ends", async () => {
    const listener = vi.fn();
    window.addEventListener("resize", listener);

    handleDragging(false);

    // raf2: wait two animation frames
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await new Promise((resolve) => requestAnimationFrame(resolve));

    expect(listener).toHaveBeenCalledTimes(1);

    window.removeEventListener("resize", listener);
  });

  it("should not dispatch a resize event while dragging", async () => {
    const listener = vi.fn();
    window.addEventListener("resize", listener);

    handleDragging(true);

    await new Promise((resolve) => requestAnimationFrame(resolve));
    await new Promise((resolve) => requestAnimationFrame(resolve));

    expect(listener).not.toHaveBeenCalled();

    window.removeEventListener("resize", listener);
  });
});
