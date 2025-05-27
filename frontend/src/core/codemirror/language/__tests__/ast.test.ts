/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { parseArgsKwargs } from "../utils/ast";
import { parser } from "@lezer/python";
import type { TreeCursor } from "@lezer/common";

function moveToArgList(cursor: TreeCursor) {
  cursor.next();
  cursor.next();
  cursor.next();
  cursor.next();
  expect(cursor.name).toBe("ArgList");
}

function createCursor(code: string) {
  const tree = parser.parse(code);
  const cursor = tree.cursor();
  moveToArgList(cursor);
  return cursor;
}

function printResults(
  results: ReturnType<typeof parseArgsKwargs>,
  code: string,
) {
  return {
    args: results.args.map(
      (arg) =>
        `"${arg.name}" (${arg.from}, ${arg.to}, ${code.slice(arg.from, arg.to)})`,
    ),
    kwargs: results.kwargs.map((kwarg) => ({
      key: kwarg.key,
      value: kwarg.value,
    })),
  };
}

describe("parseArgsKwargs", () => {
  it("should parse empty arglist", () => {
    const code = "fn()";
    const cursor = createCursor(code);
    expect(
      printResults(parseArgsKwargs(cursor, code), code),
    ).toMatchInlineSnapshot(`
      {
        "args": [],
        "kwargs": [],
      }
    `);
  });

  it("should parse positional arguments", () => {
    const code = "fn(a, b)";
    const cursor = createCursor(code);
    expect(
      printResults(parseArgsKwargs(cursor, code), code),
    ).toMatchInlineSnapshot(`
      {
        "args": [
          ""VariableName" (3, 4, a)",
          ""VariableName" (6, 7, b)",
        ],
        "kwargs": [],
      }
    `);
  });

  it("should parse keyword arguments", () => {
    const code = "fn(a=b, c=d)";
    const cursor = createCursor(code);
    expect(
      printResults(parseArgsKwargs(cursor, code), code),
    ).toMatchInlineSnapshot(`
      {
        "args": [],
        "kwargs": [
          {
            "key": "a",
            "value": "b",
          },
          {
            "key": "c",
            "value": "d",
          },
        ],
      }
    `);
  });

  it("should parse mixed arguments", () => {
    const code = "fn(a, b=c)";
    const cursor = createCursor(code);
    expect(
      printResults(parseArgsKwargs(cursor, code), code),
    ).toMatchInlineSnapshot(`
      {
        "args": [
          ""VariableName" (3, 4, a)",
        ],
        "kwargs": [
          {
            "key": "b",
            "value": "c",
          },
        ],
      }
    `);
  });

  it("should handle non-ArgList input", () => {
    const code = "x";
    const tree = parser.parse(code);
    const cursor = tree.cursor();
    expect(
      printResults(parseArgsKwargs(cursor, code), code),
    ).toMatchInlineSnapshot(`
      {
        "args": [],
        "kwargs": [],
      }
    `);
  });
});
