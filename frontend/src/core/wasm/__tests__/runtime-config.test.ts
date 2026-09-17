/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it } from "vitest";
import { getWasmRuntimeConfig } from "../runtime-config";

afterEach(() => {
  document.head.innerHTML = "";
});

describe("getWasmRuntimeConfig", () => {
  it("uses runtime defaults when no URLs are configured", () => {
    expect(getWasmRuntimeConfig()).toEqual({
      pyodideIndexUrl: undefined,
      pyodideLockfileUrl: undefined,
      pypiIndexUrl: undefined,
    });
  });

  it("resolves URLs against the page base and preserves micropip placeholders", () => {
    document.head.innerHTML = `
      <base href="https://example.com/blog/post/">
      <marimo-wasm
        data-pyodide-index-url="../runtime/"
        data-pyodide-lockfile-url="/locks/pyodide.json?v=1&amp;x=2"
        data-pypi-index-url="https://packages.example.com/{package_name}/json"
      ></marimo-wasm>`;
    expect(getWasmRuntimeConfig()).toEqual({
      pyodideIndexUrl: "https://example.com/blog/runtime/",
      pyodideLockfileUrl: "https://example.com/locks/pyodide.json?v=1&x=2",
      pypiIndexUrl: "https://packages.example.com/{package_name}/json",
    });
  });
});
