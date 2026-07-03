/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { Logger } from "@/utils/Logger";
import { resolveWasmWheelUrls } from "../wheel-urls";

describe("resolveWasmWheelUrls", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resolves same-origin wheel URLs", () => {
    const result = resolveWasmWheelUrls(
      [
        "public/wheels/demo_pkg-0.1.0-py3-none-any.whl",
        "https://notebook.example/public/wheels/extra_pkg-0.1.0-py3-none-any.whl",
        "blob:https://notebook.example/4ecae2a9-2f34-4c21-8f0f-7a7df1f73f8c",
      ],
      {
        allowedOrigin: "https://notebook.example",
        baseUrl: "https://notebook.example/notebooks/main.html",
      },
    );

    expect(result).toEqual([
      "https://notebook.example/notebooks/public/wheels/demo_pkg-0.1.0-py3-none-any.whl",
      "https://notebook.example/public/wheels/extra_pkg-0.1.0-py3-none-any.whl",
      "blob:https://notebook.example/4ecae2a9-2f34-4c21-8f0f-7a7df1f73f8c",
    ]);
  });

  it("filters empty, invalid, cross-origin, and non-wheel URLs", () => {
    const warn = vi.spyOn(Logger, "warn").mockImplementation(() => undefined);

    const result = resolveWasmWheelUrls(
      [
        "",
        "http://[::1",
        "https://cdn.example/demo_pkg-0.1.0-py3-none-any.whl",
        "data:text/plain,not-a-wheel",
        "public/wheels/not-a-wheel.txt",
        "public/wheels/demo_pkg-0.1.0-py3-none-any.whl",
      ],
      {
        allowedOrigin: "https://notebook.example",
        baseUrl: "https://notebook.example/notebooks/main.html",
      },
    );

    expect(result).toEqual([
      "https://notebook.example/notebooks/public/wheels/demo_pkg-0.1.0-py3-none-any.whl",
    ]);
    expect(warn).toHaveBeenCalledTimes(5);
  });
});
