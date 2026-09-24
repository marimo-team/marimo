/* Copyright 2026 Marimo. All rights reserved. */

import { gzipSync } from "node:zlib";
import { expect, it } from "vitest";
import { initialBundleSize } from "../../vite-plugins/bundle-budget";

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
