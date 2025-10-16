/* Copyright 2024 Marimo. All rights reserved. */

import type { TreeCursor } from "@lezer/common";
import { describe, expect, it } from "vitest";
import {
  getPrefixLength,
  getStringContent,
  parseArgsKwargs,
  parsePythonAST,
} from "../utils/python-ast.js";

function moveToArgList(cursor: TreeCursor) {
  cursor.next();
  cursor.next();
  cursor.next();
  cursor.next();
  expect(cursor.name).toBe("ArgList");
}

function createCursor(code: string) {
  const tree = parsePythonAST(code);
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

describe("parsePythonAST", () => {
  it("should parse valid Python code", () => {
    const tree = parsePythonAST("print('hello')");
    expect(tree).toBeDefined();
    expect(tree.length).toBeGreaterThan(0);
  });

  it("should parse empty code", () => {
    const tree = parsePythonAST("");
    expect(tree).toBeDefined();
  });
});

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
    const tree = parsePythonAST(code);
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

  it("should parse complex keyword arguments", () => {
    const code = "fn(output=True, engine=postgres_engine)";
    const cursor = createCursor(code);
    const result = parseArgsKwargs(cursor, code);
    expect(result.args).toHaveLength(0);
    expect(result.kwargs).toHaveLength(2);
    expect(result.kwargs[0]).toEqual({ key: "output", value: "True" });
    expect(result.kwargs[1]).toEqual({
      key: "engine",
      value: "postgres_engine",
    });
  });

  it("should parse string literal arguments", () => {
    const code = 'fn("hello", x=42)';
    const cursor = createCursor(code);
    const result = parseArgsKwargs(cursor, code);
    expect(result.args).toHaveLength(1);
    expect(result.kwargs).toHaveLength(1);
    expect(result.kwargs[0]).toEqual({ key: "x", value: "42" });
  });
});

describe("getStringContent", () => {
  function findStringNode(code: string) {
    const tree = parsePythonAST(code);
    const cursor = tree.cursor();
    while (cursor.next()) {
      if (cursor.name === "String" || cursor.name === "FormatString") {
        return cursor.node;
      }
    }
    return null;
  }

  it("should extract content from triple double-quoted strings", () => {
    const code = '"""hello world"""';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello world");
    }
  });

  it("should extract content from triple single-quoted strings", () => {
    const code = "'''hello world'''";
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello world");
    }
  });

  it("should extract content from single double-quoted strings", () => {
    const code = '"hello"';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello");
    }
  });

  it("should extract content from single single-quoted strings", () => {
    const code = "'hello'";
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello");
    }
  });

  it("should extract content from f-strings with triple quotes", () => {
    const code = 'f"""hello {world}"""';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello {world}");
    }
  });

  it("should extract content from f-strings with single quotes", () => {
    const code = 'f"hello {world}"';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello {world}");
    }
  });

  it("should extract content from rf-strings", () => {
    const code = 'rf"""hello {world}"""';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello {world}");
    }
  });

  it("should extract content from fr-strings", () => {
    const code = 'fr"""hello {world}"""';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello {world}");
    }
  });

  it("should extract content from r-strings with triple quotes", () => {
    const code = 'r"""hello\\nworld"""';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello\\nworld");
    }
  });

  it("should extract content from r-strings with single quotes", () => {
    const code = 'r"hello\\nworld"';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("hello\\nworld");
    }
  });

  it("should return null for non-string nodes", () => {
    const code = "42";
    const tree = parsePythonAST(code);
    const node = tree.topNode.firstChild;
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBeNull();
    }
  });

  it("should handle empty strings", () => {
    const code = '""';
    const node = findStringNode(code);
    expect(node).not.toBeNull();
    if (node) {
      const content = getStringContent(node, code);
      expect(content).toBe("");
    }
  });
});

describe("getPrefixLength", () => {
  it("should return 0 for empty string", () => {
    expect(getPrefixLength("")).toBe(0);
  });

  it("should return correct length for triple double quotes", () => {
    expect(getPrefixLength('"""hello"""')).toBe(3);
  });

  it("should return correct length for triple single quotes", () => {
    expect(getPrefixLength("'''hello'''")).toBe(3);
  });

  it("should return correct length for single double quote", () => {
    expect(getPrefixLength('"hello"')).toBe(1);
  });

  it("should return correct length for single single quote", () => {
    expect(getPrefixLength("'hello'")).toBe(1);
  });

  it("should return correct length for f-strings with triple quotes", () => {
    expect(getPrefixLength('f"""hello"""')).toBe(4);
    expect(getPrefixLength("f'''hello'''")).toBe(4);
  });

  it("should return correct length for f-strings with single quotes", () => {
    expect(getPrefixLength('f"hello"')).toBe(2);
    expect(getPrefixLength("f'hello'")).toBe(2);
  });

  it("should return correct length for r-strings with triple quotes", () => {
    expect(getPrefixLength('r"""hello"""')).toBe(4);
    expect(getPrefixLength("r'''hello'''")).toBe(4);
  });

  it("should return correct length for r-strings with single quotes", () => {
    expect(getPrefixLength('r"hello"')).toBe(2);
    expect(getPrefixLength("r'hello'")).toBe(2);
  });

  it("should return correct length for rf-strings with triple quotes", () => {
    expect(getPrefixLength('rf"""hello"""')).toBe(5);
    expect(getPrefixLength("rf'''hello'''")).toBe(5);
  });

  it("should return correct length for rf-strings with single quotes", () => {
    expect(getPrefixLength('rf"hello"')).toBe(3);
    expect(getPrefixLength("rf'hello'")).toBe(3);
  });

  it("should return correct length for fr-strings with triple quotes", () => {
    expect(getPrefixLength('fr"""hello"""')).toBe(5);
    expect(getPrefixLength("fr'''hello'''")).toBe(5);
  });

  it("should return correct length for fr-strings with single quotes", () => {
    expect(getPrefixLength('fr"hello"')).toBe(3);
    expect(getPrefixLength("fr'hello'")).toBe(3);
  });

  it("should return 0 for non-string content", () => {
    expect(getPrefixLength("hello")).toBe(0);
    expect(getPrefixLength("42")).toBe(0);
  });
});
