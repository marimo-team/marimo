/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { Tracebacks } from "@/__mocks__/tracebacks";
import { extractAllTracebackInfo } from "../traceback";

describe("traceback", () => {
  test("extracts cell-link", () => {
    const errors = extractAllTracebackInfo(Tracebacks.raw);
    expect(errors).toMatchInlineSnapshot(`
      [
        {
          "cellId": "Hbol",
          "lineNumber": 4,
        },
        {
          "cellId": "Hbol",
          "lineNumber": 2,
        },
      ]
    `);
  });

  test("extracts cell-link from assertion", () => {
    const info = extractAllTracebackInfo(Tracebacks.assertion);
    expect(info).toMatchInlineSnapshot(`
      [
        {
          "cellId": "Hbol",
          "lineNumber": 1,
        },
      ]
    `);
  });
});
