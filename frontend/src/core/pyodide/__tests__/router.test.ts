/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/unbound-method */
import { beforeEach, afterEach, expect, test, describe, vi } from "vitest";
import { PyodideRouter } from "../router";

describe("URLPyodideRouter", () => {
  const originalLocation = window.location;
  const originalReplaceState = window.history.replaceState;

  beforeEach(() => {
    window.location = { href: "https://marimo.app" } as Location;
    window.history.replaceState = vi.fn();
  });

  afterEach(() => {
    window.location = originalLocation;
    window.history.replaceState = originalReplaceState;
  });

  test("getFilename returns correct filename from URL", () => {
    window.location.href = "https://marimo.app?filename=test.py";
    expect(PyodideRouter.getFilename()).toBe("test.py");
  });

  test("getFilename returns null when filename is not in URL", () => {
    window.location.href = "https://marimo.app";
    expect(PyodideRouter.getFilename()).toBeNull();
  });

  test("getCode returns correct code from URL", () => {
    window.location.href = 'https://marimo.app?code=print("Hello, World!")';
    expect(PyodideRouter.getCode()).toBe('print("Hello, World!")');
  });

  test("setFilename correctly modifies URL", () => {
    PyodideRouter.setFilename("newfile.py");
    expect(window.history.replaceState).toHaveBeenCalledWith(
      {},
      "",
      "https://marimo.app/?filename=newfile.py",
    );
  });
});
