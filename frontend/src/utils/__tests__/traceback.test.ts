/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { Tracebacks } from "@/__mocks__/tracebacks";
import { extractAllTracebackInfo } from "../traceback";

describe("traceback", () => {
  test("extracts cell-link", () => {
    const errors = extractAllTracebackInfo(Tracebacks.raw);
    expect(
      errors[0].kind === "file" &&
        errors[0].filePath.endsWith("marimo/_runtime/executor.py"),
    ).toBe(true);
    expect(errors.slice(1)).toMatchInlineSnapshot(`
      [
        {
          "cellId": "Hbol",
          "kind": "cell",
          "lineNumber": 4,
        },
        {
          "cellId": "Hbol",
          "kind": "cell",
          "lineNumber": 2,
        },
      ]
    `);
  });

  test("extracts cell-link from assertion", () => {
    const info = extractAllTracebackInfo(Tracebacks.assertion);
    expect(
      info[0].kind === "file" &&
        info[0].filePath.endsWith("marimo/_runtime/executor.py"),
    ).toBe(true);
    expect(info.slice(1)).toMatchInlineSnapshot(`
      [
        {
          "cellId": "Hbol",
          "kind": "cell",
          "lineNumber": 1,
        },
      ]
    `);
  });
});
