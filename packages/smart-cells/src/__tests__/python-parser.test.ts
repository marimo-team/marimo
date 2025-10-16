/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { PythonParser } from "../parsers/python-parser.js";

const parser = new PythonParser();

describe("PythonParser", () => {
  it("should pass through code unchanged", () => {
    const code = 'print("Hello, World!")';
    const { code: result, offset, metadata } = parser.transformIn(code);
    expect(result).toBe(code);
    expect(offset).toBe(0);
    expect(metadata).toEqual({});
  });

  it("should support any code", () => {
    expect(parser.isSupported("anything goes")).toBe(true);
    expect(parser.isSupported("")).toBe(true);
  });

  it("should roundtrip correctly", () => {
    const code = "x = 42\nprint(x)";
    const { code: transformed, metadata } = parser.transformIn(code);
    const { code: backToOriginal } = parser.transformOut(transformed, metadata);
    expect(backToOriginal).toBe(code);
  });
});
