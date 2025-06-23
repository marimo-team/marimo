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
  const cellId = "current-cell" as CellId;

  test("should highlight global variable but not function parameter", () => {
    const variables = createVariables(["a", "b"]);
    const code = `def foo(a):
    return a + b`;

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });
    // Should only highlight 'b', not 'a' (since 'a' is a function parameter)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("b");
  });

  test("should highlight both variables when no shadowing", () => {
    const variables = createVariables(["a", "b"]);
    const code = `def foo(x):
    return a + b`;

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });

    // Should highlight both 'a' and 'b' since 'x' doesn't shadow either
    expect(ranges).toHaveLength(2);
    const variableNames = ranges.map((r) => r.variableName).sort();
    expect(variableNames).toEqual(["a", "b"]);
  });

  test("should handle lambda parameters", () => {
    const variables = createVariables(["a", "b"]);
    const code = "result = lambda a: a + b";

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });

    // Should only highlight 'b', not 'a' (lambda parameter)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("b");
  });

  test("should handle comprehension variables", () => {
    const variables = createVariables(["a", "data"]);
    const code = "result = [a for a in data]";

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });

    // Should only highlight 'data', not 'a' (comprehension variable)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("data");
  });

  test("should handle nested scopes", () => {
    const variables = createVariables(["a", "b", "c"]);
    const code = `def outer(a):
    def inner(b):
        return a + b + c
    return inner`;

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });

    // Should only highlight 'c' since 'a' and 'b' are parameters
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("c");
  });

  test("should return empty array for syntax errors", () => {
    const variables = createVariables(["a", "b"]);
    const code = `def foo(a:
    return a + b`; // Missing closing paren

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });

    // Should return no ranges due to syntax error
    expect(ranges).toHaveLength(0);
  });

  test("should handle multiple parameters", () => {
    const variables = createVariables(["a", "b", "c", "d"]);
    const code = `def foo(a, b, c):
    return a + b + c + d`;

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });

    // Should only highlight 'd' since a, b, c are parameters
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("d");
  });

  test("should handle recursive function", () => {
    const variables = createVariables(["n", "base"]);
    const code = `def factorial(n):
    if n <= 1:
        return base
    return n * factorial(n - 1)`;

    const state = createPythonEditorState(code);

    const ranges = findReactiveVariables({ state, cellId, variables });

    // Should only highlight 'base', not 'n' (parameter)
    expect(ranges).toHaveLength(1);
    expect(ranges[0].variableName).toBe("base");
  });

  test("function param vs global", () => {
    const variables = createVariables(["a", "b"]);
    const code = "def foo(a): return a + b";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["b"]);
  });

  test("lambda param vs global", () => {
    const variables = createVariables(["x", "b"]);
    const code = "func = lambda x: x + b";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["b"]);
  });

  test("lambda with multiple params", () => {
    const variables = createVariables(["x", "y", "z"]);
    const code = "f = lambda x, y: x + y + z";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["z"]);
  });

  test("comprehension shadows global", () => {
    const variables = createVariables(["a"]);
    const code = "[a for a in range(5)]";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges).toHaveLength(0);
  });

  test("nested comprehension", () => {
    const variables = createVariables(["a", "b"]);
    const code = "[(a + b) for a, b in [(1,2), (3,4)]]";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges).toHaveLength(0);
  });

  test("dict comprehension using global", () => {
    const variables = createVariables(["k", "v", "offset"]);
    const code = `{k: v + offset for k, v in [("a", 1), ("b", 2)]}`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["offset"]);
  });

  test("generator expression", () => {
    const variables = createVariables(["x", "threshold", "global_list"]);
    const code = "(x + threshold for x in global_list)";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual([
      "global_list",
      "threshold",
    ]);
  });

  test("class body using globals", () => {
    const variables = createVariables(["a", "b"]);
    const code = "class MyClass:\n  value = a + b";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["a", "b"]);
  });

  test("decorator using global", () => {
    const variables = createVariables(["logger"]);
    const code = "@logger\ndef decorated(): pass";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["logger"]);
  });

  test("try/except block using global", () => {
    const variables = createVariables(["e", "logger"]);
    const code = `try:\n  1 / 0\nexcept Exception as e:\n  print("Error", logger)`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["logger"]);
  });

  test("with statement using global", () => {
    const variables = createVariables(["path", "f"]);
    const code = "with open(path) as f:\n  print(f.read())";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["path"]);
  });

  test("function reusing global name as param", () => {
    const variables = createVariables(["logger"]);
    const code = "def shadow_logger(logger): return logger + 1";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges).toHaveLength(0);
  });

  test("shadowed global in inner function", () => {
    const variables = createVariables(["a", "b", "x", "z"]);
    const code = `
def outer():
    z = 10
    x = 20
    def inner():
        a = 2
        return a + b + z  # highlight: b
    return inner()
  `;

    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });

    const highlighted = ranges.map((r) => r.variableName).sort();
    expect(highlighted).toEqual(["b"]);
  });

  test("multiple assignment", () => {
    const variables = createVariables(["x", "y", "z", "a"]);
    const code = "x = y = z + a";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["a", "z"]);
  });

  test("nested lambdas", () => {
    const variables = createVariables(["x", "y", "b"]);
    const code = "nested_lambda = lambda x: (lambda y: x + y + b)";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["b"]);
  });

  test("function using builtin and global", () => {
    const variables = createVariables(["offset", "len"]);
    const code = "def use_len(x): return len(x) + offset";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // Since len is a declared variable, it should be treated as reactive
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["len", "offset"]);
  });

  test("global in return", () => {
    const variables = createVariables(["config"]);
    const code = "def get_config(): return config";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["config"]);
  });

  test("shadowed global in inner function 2", () => {
    const variables = createVariables(["a", "b", "x", "z"]);
    const code = `
def outer2():
    z = 10
    x = 20
    def inner():
        a = 2
        return a + b + z  # b should be highlighted
    return inner()
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["b"]);
  });

  test("global used inside class", () => {
    const variables = createVariables(["config"]);
    const code = `
class Configurable:
    value = config
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["config"]);
  });

  test("comprehension shadows global 2", () => {
    const variables = createVariables(["i"]);
    const code = "squares = [i**2 for i in range(10)]";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges).toHaveLength(0);
  });

  test("comprehension with global in condition", () => {
    const variables = createVariables(["x", "z"]);
    const code = "filtered = [x for x in [] if x > z]";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["z"]);
  });

  test("dict comprehension with local destructuring", () => {
    const variables = createVariables(["k", "v"]);
    const code = `kv_map = {k: v for (k, v) in [("a", "b")]}`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges).toHaveLength(0);
  });

  test("lambda inside function accessing global", () => {
    const variables = createVariables(["x", "g"]);
    const code = `
def make_adder(x):
    return lambda y: x + y + g
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["g"]);
  });

  test("rebinding in list comprehension", () => {
    const variables = createVariables(["x"]);
    const code = "rebinding = [x for x in range(5)]";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges).toHaveLength(0);
  });

  test("global used inside nested def in comprehension", () => {
    const variables = createVariables(["x", "z"]);
    const code = "nested_comp = [lambda: x + z for x in range(5)]";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["z"]);
  });

  test("async function using global", () => {
    const variables = createVariables(["client", "x"]);
    const code = `
async def fetch():
    return await client.get(x)
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["client", "x"]);
  });

  test("class method using global", () => {
    const variables = createVariables(["x"]);
    const code = `
class Thing:
    def compute(self):
        return self.factor * x
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["x"]);
  });

  test("function with multiple local scopes", () => {
    const variables = createVariables(["external", "y", "x"]);
    const code = `
def complex(x):
    if x > 0:
        y = x * 2
    else:
        y = external
    return y
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName)).toEqual(["external"]);
  });

  test("nested import with alias", () => {
    const variables = createVariables(["mo", "x", "polars"]);
    const code = `
def nested_import():
    import marimo as mo
    import polars
    print(mo, x, polars)`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["x"]);
  });

  test("from-import with shadowing", () => {
    const variables = createVariables(["my_sin", "x", "my_func"]);
    const code = `
def inner():
    from math import sin as my_sin
    return my_sin(x) + my_func(x)`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual([
      "my_func",
      "x",
      "x",
    ]);
  });

  test("shadowed global via assignment", () => {
    const variables = createVariables(["polars", "x"]);
    const code = `
def myfunc():
    polars = "not a module"
    return x + polars`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["x"]);
  });

  test("multiple imports and local names", () => {
    const variables = createVariables(["np", "pd", "x", "y"]);
    const code = `
def analyze():
    import numpy as np
    import pandas as pd
    result = x + y + np.array([1, 2])`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["x", "y"]);
  });

  test("import shadowed by parameter", () => {
    const variables = createVariables(["polars", "x"]);
    const code = `
def run(polars):
    return polars + x`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["x"]);
  });

  test("mixed comprehension and outer globals", () => {
    const variables = createVariables(["y", "z"]);
    const code = "values = [y + z for y in range(5)]";
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["z"]);
  });

  test("lambda inside function with outer global", () => {
    const variables = createVariables(["x", "a", "offset"]);
    const code = `
def wrapper():
    return lambda x: x + a + offset`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["a", "offset"]);
  });

  test("with statement inside function with global", () => {
    const variables = createVariables(["path", "a"]);
    const code = `
def func():
    with open(path) as a:
        print(a.read())`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["path"]);
  });

  test("redeclaration at top-level", () => {
    // These variables are redeclared locally, so they should not be highlighted
    // even though marimo may reject the redeclaration at runtime.
    const variables = createVariables(["a", "b", "f", "i", "y"]);
    const code = `
a = 10
b = 20

with open("/test.txt") as f:
  print(f.read())

for i in range(10):
  print(i)

print(y)`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["y"]);
  });

  test("shadowed global method in inner function", () => {
    // These variables are redeclared locally, so they should not be highlighted
    // even though marimo may reject the redeclaration at runtime.
    const variables = createVariables(["z", "x", "a", "b", "inner"]);
    const code = `
def outer2():
    z = 10
    x = 20

    def inner():
        a = 2
        return a + b + z  # b should be highlighted

    return inner()
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["b"]);
  });

  // Pathological test cases for edge cases
  test("global statement overrides local scoping", () => {
    const variables = createVariables(["x", "y"]);
    const code = `
def outer():
    x = 1
    def inner():
        global x  # This refers to global x, not outer's x
        return x + y
    return inner()
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // Only y should be highlighted since global isn't global in marimo
    expect(ranges.map((r) => r.variableName).sort()).toEqual(["y"]);
  });

  test("nonlocal statement accesses enclosing scope", () => {
    const variables = createVariables(["z", "global_var"]);
    const code = `
def outer():
    z = 10
    def inner():
        nonlocal z  # This refers to outer's z, not global z
        return z + global_var
    return inner()
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // Only global_var should be highlighted, z is nonlocal (from outer scope)
    expect(ranges.map((r) => r.variableName)).toEqual(["global_var"]);
  });

  test("star unpacking in assignment", () => {
    const variables = createVariables(["values", "a", "b", "c"]);
    const code = `
def func():
    a, *b, c = values
    return a + len(b) + c
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // Only values should be highlighted, a, b, c are assigned locally
    expect(ranges.map((r) => r.variableName)).toEqual(["values"]);
  });

  test("nested tuple unpacking", () => {
    const variables = createVariables(["nested_data", "x", "y", "z"]);
    const code = `
def func():
    (x, (y, z)) = nested_data
    return x + y + z
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // Only nested_data should be highlighted
    expect(ranges.map((r) => r.variableName)).toEqual(["nested_data"]);
  });

  test("walrus operator in comprehension", () => {
    const variables = createVariables(["data", "threshold", "process"]);
    const code = `
result = [y for x in data if (y := process(x)) > threshold]
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // data, process, and threshold should be highlighted; y is assigned in walrus operator
    expect(ranges.map((r) => r.variableName).sort()).toEqual([
      "data",
      "process",
      "threshold",
    ]);
  });

  test("exception variable scoping", () => {
    const variables = createVariables(["e", "logger", "risky_operation"]);
    const code = `
def func():
    try:
        risky_operation()
    except Exception as e:  # e is local to except block
        return str(e) + logger
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // logger and risky_operation should be highlighted; e is local exception variable
    expect(ranges.map((r) => r.variableName).sort()).toEqual([
      "logger",
      "risky_operation",
    ]);
  });

  test("star import potential shadowing", () => {
    const variables = createVariables(["x", "y", "unknown_func"]);
    const code = `
def func():
    from math import *  # Could import anything, including x
    return x + y + unknown_func()
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    // All should be highlighted since we can't know what star import brings in
    expect(ranges.map((r) => r.variableName).sort()).toEqual([
      "unknown_func",
      "x",
      "y",
    ]);
  });

  test("class variable vs instance variable", () => {
    const variables = createVariables(["class_global", "instance_global"]);
    const code = `
class MyClass:
    class_var = class_global  # Should highlight class_global

    def __init__(self):
        self.instance_var = instance_global  # Should highlight instance_global

    def method(self):
        return self.class_var + self.instance_var
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual([
      "class_global",
      "instance_global",
    ]);
  });

  test("nested class with outer scope access", () => {
    const variables = createVariables(["outer_var", "global_var"]);
    const code = `
def outer_func():
    outer_var = 1

    class InnerClass:
        # Classes can't access enclosing function scope directly
        value = global_var  # Should highlight global_var, not outer_var
        value2 = outer_var

        def method(self):
            return self.value + global_var

    return InnerClass()
`;
    const state = createPythonEditorState(code);
    const ranges = findReactiveVariables({ state, cellId, variables });
    expect(ranges.map((r) => r.variableName).sort()).toEqual([
      "global_var",
      "global_var",
    ]);
  });
});
