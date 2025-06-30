/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/unbound-method */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { PyodideRouter } from "../router";

describe("URLPyodideRouter", () => {
  const originalLocation = globalThis.location;
  const originalReplaceState = globalThis.history.replaceState;

  beforeEach(() => {
    globalThis.location = { href: "https://marimo.app" } as never;
    globalThis.history.replaceState = vi.fn();
  });

  afterEach(() => {
    globalThis.location = originalLocation as never;
    globalThis.history.replaceState = originalReplaceState;
  });

  test("getFilename returns correct filename from URL", () => {
    globalThis.location.href = "https://marimo.app?filename=test.py";
    expect(PyodideRouter.getFilename()).toBe("test.py");
  });

  test("getFilename returns null when filename is not in URL", () => {
    globalThis.location.href = "https://marimo.app";
    expect(PyodideRouter.getFilename()).toBeNull();
  });

  test("getCode returns correct code from URL", () => {
    globalThis.location.href = 'https://marimo.app?code=print("Hello, World!")';
    expect(PyodideRouter.getCodeFromSearchParam()).toBe(
      'print("Hello, World!")',
    );
  });

  test("getCode from hash returns correct code", () => {
    globalThis.location.href = "https://marimo.app";
    globalThis.location.hash = "#code/print('Hello, World!')";
    expect(PyodideRouter.getCodeFromHash()).toBe("print('Hello, World!')");
  });

  test("getCode from hash with query params returns correct code", () => {
    globalThis.location.href = "https://marimo.app?filename=test.py";
    globalThis.location.hash = "#code/print('Hello, World!')";
    expect(PyodideRouter.getCodeFromHash()).toBe("print('Hello, World!')");
    expect(PyodideRouter.getFilename()).toBe("test.py");
  });

  test("setFilename correctly modifies URL", () => {
    PyodideRouter.setFilename("newfile.py");
    expect(globalThis.history.replaceState).toHaveBeenCalledWith(
      {},
      "",
      "https://marimo.app/?filename=newfile.py",
    );
  });
});
