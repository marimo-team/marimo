/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { describe, expect, test } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { VariableName, Variables } from "@/core/variables/types";
import { findReactiveVariables } from "../analyzer";

/**
 * Helper function to create an EditorState with Python code
 */
function createPythonEditorState(code: string): EditorState {
  return EditorState.create({
    doc: code,
    extensions: [python()],
  });
}

/**
 * Helper function to create a Variables object for testing
 */
function createVariables(
  variableNames: string[],
  declaredByCellId = "other-cell",
): Variables {
  const variables: Variables = {};

  for (const name of variableNames) {
    variables[name as VariableName] = {
      name: name as VariableName,
      declaredBy: [declaredByCellId as CellId],
      usedBy: [],
      value: "test-value",
      dataType: "str",
    };
  }

  return variables;
}

describe("findReactiveVariables - Lexical Scoping", () => {
  const currentCellId = "current-cell" as CellId;

  test("should highlight global variable but not function parameter", () => {
    const code = `def foo(a):
    return a + b`;

    const state = createPythonEditorState(code);
    const variables = createVariables(["a", "b"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should only highlight 'b', not 'a' (since 'a' is a function parameter)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("b");
  });

  test("should highlight both variables when no shadowing", () => {
    const code = `def foo(x):
    return a + b`;

    const state = createPythonEditorState(code);
    const variables = createVariables(["a", "b"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should highlight both 'a' and 'b' since 'x' doesn't shadow either
    expect(ranges).toHaveLength(2);
    const variableNames = ranges.map((r) => r.variableName).sort();
    expect(variableNames).toEqual(["a", "b"]);
  });

  test("should handle lambda parameters", () => {
    const code = "result = lambda a: a + b";

    const state = createPythonEditorState(code);
    const variables = createVariables(["a", "b"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should only highlight 'b', not 'a' (lambda parameter)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("b");
  });

  test("should handle comprehension variables", () => {
    const code = "result = [a for a in data]";

    const state = createPythonEditorState(code);
    const variables = createVariables(["a", "data"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should only highlight 'data', not 'a' (comprehension variable)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("data");
  });

  test("should handle nested scopes", () => {
    const code = `def outer(a):
    def inner(b):
        return a + b + c
    return inner`;

    const state = createPythonEditorState(code);
    const variables = createVariables(["a", "b", "c"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should only highlight 'c' since 'a' and 'b' are parameters
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("c");
  });

  test("should return empty array for syntax errors", () => {
    const code = `def foo(a:
    return a + b`; // Missing closing paren

    const state = createPythonEditorState(code);
    const variables = createVariables(["a", "b"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should return no ranges due to syntax error
    expect(ranges).toHaveLength(0);
  });

  test("should handle multiple parameters", () => {
    const code = `def foo(a, b, c):
    return a + b + c + d`;

    const state = createPythonEditorState(code);
    const variables = createVariables(["a", "b", "c", "d"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should only highlight 'd' since a, b, c are parameters
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("d");
  });

  test("should handle recursive function", () => {
    const code = `def factorial(n):
    if n <= 1:
        return base
    return n * factorial(n - 1)`;

    const state = createPythonEditorState(code);
    const variables = createVariables(["n", "base"]);

    const ranges = findReactiveVariables({
      state,
      cellId: currentCellId,
      variables,
    });

    // Should only highlight 'base', not 'n' (parameter)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("base");
  });
});
