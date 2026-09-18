/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, assert, describe, expect, it } from "vitest";
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

  it.each(["pyodideIndexUrl", "pyodideLockfileUrl", "pypiIndexUrl"])(
    "ignores malformed %s while preserving valid overrides",
    (key) => {
      document.head.innerHTML = `
        <base href="https://example.com/notebook/">
        <marimo-wasm
          data-pyodide-index-url="./pyodide/"
          data-pyodide-lockfile-url="./lockfile/pyodide.json"
          data-pypi-index-url="./packages/{package_name}.json"
        ></marimo-wasm>`;
      const element = document.querySelector<HTMLElement>("marimo-wasm");
      assert(element);
      element.dataset[key] = "https://invalid host/";

      expect(getWasmRuntimeConfig()).toEqual({
        pyodideIndexUrl: "https://example.com/notebook/pyodide/",
        pyodideLockfileUrl:
          "https://example.com/notebook/lockfile/pyodide.json",
        pypiIndexUrl:
          "https://example.com/notebook/packages/{package_name}.json",
        [key]: undefined,
      });
    },
  );
});
