/* Copyright 2026 Marimo. All rights reserved. */

import { gzipSync } from "node:zlib";
import { assert, expect, it, vi } from "vitest";
import {
  bundleBudget,
  initialBundleSize,
} from "../../vite-plugins/bundle-budget";

it("counts shared static imports once across entries and excludes lazy chunks", () => {
  const size = initialBundleSize([
    {
      fileName: "a.js",
      isEntry: true,
      imports: ["shared.js"],
      code: "entry A",
    },
    {
      fileName: "b.js",
      isEntry: true,
      imports: ["shared.js"],
      code: "entry B",
    },
    {
      fileName: "shared.js",
      isEntry: false,
      imports: ["a.js", "external.js"],
      code: "shared 🐍",
    },
    { fileName: "lazy.js", isEntry: false, imports: [], code: "lazy renderer" },
  ]);

  const initial = ["entry A", "entry B", "shared 🐍"];
  expect(size).toEqual({
    bytes: initial.reduce((sum, code) => sum + Buffer.byteLength(code), 0),
    gzipBytes: initial.reduce(
      (sum, code) => sum + gzipSync(code).byteLength,
      0,
    ),
  });
});

it.each([
  { maxGzipKiB: 0.001, exceedsBudget: true },
  { maxGzipKiB: 100, exceedsBudget: false },
])(
  "enforces a $maxGzipKiB KiB gzip budget",
  ({ maxGzipKiB, exceedsBudget }) => {
    const plugin = bundleBudget({ name: "Test app", maxGzipKiB });
    const hook = plugin.generateBundle;
    assert(hook && typeof hook !== "function");
    const error = vi.fn();
    const bundle = {
      "entry.js": {
        type: "chunk",
        fileName: "entry.js",
        isEntry: true,
        imports: [],
        code: "console.log('hello');",
      },
      "style.css": {
        type: "asset",
        fileName: "style.css",
        source: "body { color: red; }",
      },
    };

    Reflect.apply(hook.handler, { error }, [{}, bundle, false]);

    expect(error).toHaveBeenCalledTimes(exceedsBudget ? 1 : 0);
  },
);
