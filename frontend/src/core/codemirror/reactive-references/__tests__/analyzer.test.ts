/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { describe, expect, test } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { VariableName, Variables } from "@/core/variables/types";
import { findReactiveVariables, type ReactiveVariableRange } from "../analyzer";

describe("findReactiveVariables - Lexical Scoping", () => {
  test("should highlight global variable but not function parameter", () => {
    expect(
      runHighlight(
        ["a", "b"],
        `
def foo(a):
    return a + b
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def foo(a):
          return a + b
                     ^
      "
    `);
  });

  test("should highlight both variables when no shadowing", () => {
    expect(
      runHighlight(
        ["a", "b"],
        `
def foo(x):
    return a + b
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def foo(x):
          return a + b
                 ^   ^
      "
    `);
  });

  test("should handle lambda parameters", () => {
    expect(
      runHighlight(["a", "b"], "result = lambda a: a + b"),
    ).toMatchInlineSnapshot(`
      "
      result = lambda a: a + b
                             ^
      "
    `);
  });

  test("should handle comprehension variables", () => {
    expect(
      runHighlight(["a", "data"], "result = [a for a in data]"),
    ).toMatchInlineSnapshot(`
      "
      result = [a for a in data]
                           ^^^^
      "
    `);
  });

  test("should handle nested scopes", () => {
    expect(
      runHighlight(
        ["a", "b", "c"],
        `
def outer(a):
    def inner(b):
        return a + b + c
    return inner
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def outer(a):
          def inner(b):
              return a + b + c
                             ^
          return inner
      "
    `);
  });

  test("should return no highlight for syntax errors", () => {
    expect(
      runHighlight(
        ["a", "b"],
        `
def foo(a:
    return a + b
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def foo(a:
          return a + b
      "
    `);
  });

  test("should handle multiple parameters", () => {
    expect(
      runHighlight(
        ["a", "b", "c", "d"],
        `
def foo(a, b, c):
    return a + b + c + d
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def foo(a, b, c):
          return a + b + c + d
                             ^
      "
    `);
  });

  test("should handle recursive function", () => {
    expect(
      runHighlight(
        ["n", "base"],
        `
def factorial(n):
    if n <= 1:
        return base
    return n * factorial(n - 1)
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def factorial(n):
          if n <= 1:
              return base
                     ^^^^
          return n * factorial(n - 1)
      "
    `);
  });

  test("function param vs global", () => {
    expect(
      runHighlight(["a", "b"], "def foo(a): return a + b"),
    ).toMatchInlineSnapshot(`
      "
      def foo(a): return a + b
                             ^
      "
    `);
  });

  test("lambda param vs global", () => {
    expect(
      runHighlight(["x", "b"], "func = lambda x: x + b"),
    ).toMatchInlineSnapshot(`
      "
      func = lambda x: x + b
                           ^
      "
    `);
  });

  test("lambda with multiple params", () => {
    expect(
      runHighlight(["x", "y", "z"], "f = lambda x, y: x + y + z"),
    ).toMatchInlineSnapshot(`
      "
      f = lambda x, y: x + y + z
                               ^
      "
    `);
  });

  test("comprehension shadows global", () => {
    expect(runHighlight(["a"], "[a for a in range(5)]")).toMatchInlineSnapshot(`
      "
      [a for a in range(5)]
      "
    `);
  });

  test("nested comprehension", () => {
    expect(
      runHighlight(["a", "b"], "[(a + b) for a, b in [(1,2), (3,4)]]"),
    ).toMatchInlineSnapshot(`
      "
      [(a + b) for a, b in [(1,2), (3,4)]]
      "
    `);
  });

  test("dict comprehension using global", () => {
    expect(
      runHighlight(
        ["k", "v", "offset"],
        `{k: v + offset for k, v in [("a", 1), ("b", 2)]}`,
      ),
    ).toMatchInlineSnapshot(`
      "
      {k: v + offset for k, v in [("a", 1), ("b", 2)]}
              ^^^^^^
      "
    `);
  });

  test("generator expression", () => {
    expect(
      runHighlight(
        ["x", "threshold", "global_list"],
        "(x + threshold for x in global_list)",
      ),
    ).toMatchInlineSnapshot(`
      "
      (x + threshold for x in global_list)
           ^^^^^^^^^          ^^^^^^^^^^^
      "
    `);
  });

  test("class body using globals", () => {
    expect(
      runHighlight(["a", "b"], "class MyClass:\n  value = a + b"),
    ).toMatchInlineSnapshot(`
      "
      class MyClass:
        value = a + b
                ^   ^
      "
    `);
  });

  test("decorator using global", () => {
    expect(
      runHighlight(["logger"], "@logger\ndef decorated(): pass"),
    ).toMatchInlineSnapshot(`
      "
      @logger
       ^^^^^^
      def decorated(): pass
      "
    `);
  });

  test("try/except block using global", () => {
    expect(
      runHighlight(
        ["e", "logger"],
        `try:\n  1 / 0\nexcept Exception as e:\n  print("Error", logger)`,
      ),
    ).toMatchInlineSnapshot(`
      "
      try:
        1 / 0
      except Exception as e:
        print("Error", logger)
                       ^^^^^^
      "
    `);
  });

  test("with statement using global", () => {
    expect(
      runHighlight(["path", "f"], "with open(path) as f:\n  print(f.read())"),
    ).toMatchInlineSnapshot(`
      "
      with open(path) as f:
                ^^^^
        print(f.read())
      "
    `);
  });

  test("function reusing global name as param", () => {
    expect(
      runHighlight(["logger"], "def shadow_logger(logger): return logger + 1"),
    ).toMatchInlineSnapshot(`
      "
      def shadow_logger(logger): return logger + 1
      "
    `);
  });

  test("shadowed global in inner function", () => {
    expect(
      runHighlight(
        ["a", "b", "x", "z"],
        `
def outer():
    z = 10
    x = 20
    def inner():
        a = 2
        return a + b + z  # highlight: b
    return inner()
  `,
      ),
    ).toMatchInlineSnapshot(`
      "
      def outer():
          z = 10
          x = 20
          def inner():
              a = 2
              return a + b + z  # highlight: b
                         ^
          return inner()
        
      "
    `);
  });

  test("multiple assignment", () => {
    expect(
      runHighlight(["x", "y", "z", "a"], "x = y = z + a"),
    ).toMatchInlineSnapshot(`
      "
      x = y = z + a
              ^   ^
      "
    `);
  });

  test("nested lambdas", () => {
    expect(
      runHighlight(
        ["x", "y", "b"],
        "nested_lambda = lambda x: (lambda y: x + y + b)",
      ),
    ).toMatchInlineSnapshot(`
      "
      nested_lambda = lambda x: (lambda y: x + y + b)
                                                   ^
      "
    `);
  });

  test("function using builtin and global", () => {
    expect(
      runHighlight(["offset", "len"], "def use_len(x): return len(x) + offset"),
    ).toMatchInlineSnapshot(`
      "
      def use_len(x): return len(x) + offset
                             ^^^      ^^^^^^
      "
    `);
  });

  test("global in return", () => {
    expect(
      runHighlight(["config"], "def get_config(): return config"),
    ).toMatchInlineSnapshot(`
      "
      def get_config(): return config
                               ^^^^^^
      "
    `);
  });

  test("shadowed global in inner function 2", () => {
    expect(
      runHighlight(
        ["a", "b", "x", "z"],
        `
def outer2():
    z = 10
    x = 20
    def inner():
        a = 2
        return a + b + z  # b should be highlighted
    return inner()
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def outer2():
          z = 10
          x = 20
          def inner():
              a = 2
              return a + b + z  # b should be highlighted
                         ^
          return inner()
      "
    `);
  });

  test("global used inside class", () => {
    expect(
      runHighlight(
        ["config"],
        `
class Configurable:
    value = config
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      class Configurable:
          value = config
                  ^^^^^^
      "
    `);
  });

  test("comprehension shadows global 2", () => {
    expect(
      runHighlight(["i"], "squares = [i**2 for i in range(10)]"),
    ).toMatchInlineSnapshot(`
      "
      squares = [i**2 for i in range(10)]
      "
    `);
  });

  test("comprehension with global in condition", () => {
    expect(
      runHighlight(["x", "z"], "filtered = [x for x in [] if x > z]"),
    ).toMatchInlineSnapshot(`
      "
      filtered = [x for x in [] if x > z]
                                       ^
      "
    `);
  });

  test("dict comprehension with local destructuring", () => {
    expect(
      runHighlight(["k", "v"], `kv_map = {k: v for (k, v) in [("a", "b")]}`),
    ).toMatchInlineSnapshot(`
      "
      kv_map = {k: v for (k, v) in [("a", "b")]}
      "
    `);
  });

  test("lambda inside function accessing global", () => {
    expect(
      runHighlight(
        ["x", "g"],
        `
def make_adder(x):
    return lambda y: x + y + g
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def make_adder(x):
          return lambda y: x + y + g
                                   ^
      "
    `);
  });

  test("rebinding in list comprehension", () => {
    expect(
      runHighlight(["x"], "rebinding = [x for x in range(5)]"),
    ).toMatchInlineSnapshot(`
      "
      rebinding = [x for x in range(5)]
      "
    `);
  });

  test("global used inside nested def in comprehension", () => {
    expect(
      runHighlight(
        ["x", "z"],
        "nested_comp = [lambda: x + z for x in range(5)]",
      ),
    ).toMatchInlineSnapshot(`
      "
      nested_comp = [lambda: x + z for x in range(5)]
                                 ^
      "
    `);
  });

  test("async function using global", () => {
    expect(
      runHighlight(
        ["client", "x"],
        `
async def fetch():
    return await client.get(x)
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      async def fetch():
          return await client.get(x)
                       ^^^^^^     ^
      "
    `);
  });

  test("class method using global", () => {
    expect(
      runHighlight(
        ["x"],
        `
class Thing:
    def compute(self):
        return self.factor * x
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      class Thing:
          def compute(self):
              return self.factor * x
                                   ^
      "
    `);
  });

  test("function with multiple local scopes", () => {
    expect(
      runHighlight(
        ["external", "y", "x"],
        `
def complex(x):
    if x > 0:
        y = x * 2
    else:
        y = external
    return y
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def complex(x):
          if x > 0:
              y = x * 2
          else:
              y = external
                  ^^^^^^^^
          return y
      "
    `);
  });

  test("nested import with alias", () => {
    expect(
      runHighlight(
        ["mo", "x", "polars"],
        `
def nested_import():
    import marimo as mo
    import polars
    print(mo, x, polars)`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def nested_import():
          import marimo as mo
          import polars
          print(mo, x, polars)
                    ^
      "
    `);
  });

  test("from-import with shadowing", () => {
    expect(
      runHighlight(
        ["my_sin", "x", "my_func"],
        `
def inner():
    from math import sin as my_sin
    return my_sin(x) + my_func(x)`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def inner():
          from math import sin as my_sin
          return my_sin(x) + my_func(x)
                        ^    ^^^^^^^ ^
      "
    `);
  });

  test("shadowed global via assignment", () => {
    expect(
      runHighlight(
        ["polars", "x"],
        `
def myfunc():
    polars = "not a module"
    return x + polars`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def myfunc():
          polars = "not a module"
          return x + polars
                 ^
      "
    `);
  });

  test("multiple imports and local names", () => {
    expect(
      runHighlight(
        ["np", "pd", "x", "y"],
        `
def analyze():
    import numpy as np
    import pandas as pd
    result = x + y + np.array([1, 2])`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def analyze():
          import numpy as np
          import pandas as pd
          result = x + y + np.array([1, 2])
                   ^   ^
      "
    `);
  });

  test("import shadowed by parameter", () => {
    expect(
      runHighlight(
        ["polars", "x"],
        `
def run(polars):
    return polars + x`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def run(polars):
          return polars + x
                          ^
      "
    `);
  });

  test("mixed comprehension and outer globals", () => {
    expect(
      runHighlight(["y", "z"], "values = [y + z for y in range(5)]"),
    ).toMatchInlineSnapshot(`
      "
      values = [y + z for y in range(5)]
                    ^
      "
    `);
  });

  test("lambda inside function with outer global", () => {
    expect(
      runHighlight(
        ["x", "a", "offset"],
        `
def wrapper():
    return lambda x: x + a + offset`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def wrapper():
          return lambda x: x + a + offset
                               ^   ^^^^^^
      "
    `);
  });

  test("with statement inside function with global", () => {
    expect(
      runHighlight(
        ["path", "a"],
        `
def func():
    with open(path) as a:
        print(a.read())`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def func():
          with open(path) as a:
                    ^^^^
              print(a.read())
      "
    `);
  });

  test("redeclaration at top-level", () => {
    // These variables are redeclared locally, so they should not be highlighted
    // even though marimo may reject the redeclaration at runtime.
    expect(
      runHighlight(
        ["a", "b", "f", "i", "y"],
        `
a = 10
b = 20

with open("/test.txt") as f:
  print(f.read())

for i in range(10):
  print(i)

print(y)`,
      ),
    ).toMatchInlineSnapshot(`
      "
      a = 10
      b = 20

      with open("/test.txt") as f:
        print(f.read())

      for i in range(10):
        print(i)

      print(y)
            ^
      "
    `);
  });

  test("shadowed global method in inner function", () => {
    // These variables are redeclared locally, so they should not be highlighted
    // even though marimo may reject the redeclaration at runtime.
    expect(
      runHighlight(
        ["z", "x", "a", "b", "inner"],
        `
def outer2():
    z = 10
    x = 20

    def inner():
        a = 2
        return a + b + z  # b should be highlighted

    return inner()
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def outer2():
          z = 10
          x = 20

          def inner():
              a = 2
              return a + b + z  # b should be highlighted
                         ^

          return inner()
      "
    `);
  });

  // Pathological test cases for edge cases
  test("global statement overrides local scoping", () => {
    expect(
      runHighlight(
        ["x", "y"],
        `
def outer():
    x = 1
    def inner():
        global x  # This refers to global x, not outer's x
        return x + y
    return inner()
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def outer():
          x = 1
          def inner():
              global x  # This refers to global x, not outer's x
              return x + y
                         ^
          return inner()
      "
    `);
  });

  test("nonlocal statement accesses enclosing scope", () => {
    expect(
      runHighlight(
        ["z", "global_var"],
        `
def outer():
    z = 10
    def inner():
        nonlocal z  # This refers to outer's z, not global z
        return z + global_var
    return inner()
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def outer():
          z = 10
          def inner():
              nonlocal z  # This refers to outer's z, not global z
              return z + global_var
                         ^^^^^^^^^^
          return inner()
      "
    `);
  });

  test("star unpacking in assignment", () => {
    expect(
      runHighlight(
        ["values", "a", "b", "c"],
        `
def func():
    a, *b, c = values
    return a + len(b) + c
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def func():
          a, *b, c = values
                     ^^^^^^
          return a + len(b) + c
      "
    `);
  });

  test("nested tuple unpacking", () => {
    expect(
      runHighlight(
        ["nested_data", "x", "y", "z"],
        `
def func():
    (x, (y, z)) = nested_data
    return x + y + z
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def func():
          (x, (y, z)) = nested_data
                        ^^^^^^^^^^^
          return x + y + z
      "
    `);
  });

  test("walrus operator in comprehension", () => {
    expect(
      runHighlight(
        ["data", "threshold", "process"],
        `
result = [y for x in data if (y := process(x)) > threshold]
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      result = [y for x in data if (y := process(x)) > threshold]
                           ^^^^          ^^^^^^^       ^^^^^^^^^
      "
    `);
  });

  test("exception variable scoping", () => {
    expect(
      runHighlight(
        ["e", "logger", "risky_operation"],
        `
def func():
    try:
        risky_operation()
    except Exception as e:  # e is local to except block
        return str(e) + logger
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def func():
          try:
              risky_operation()
              ^^^^^^^^^^^^^^^
          except Exception as e:  # e is local to except block
              return str(e) + logger
                              ^^^^^^
      "
    `);
  });

  test("star import potential shadowing", () => {
    expect(
      runHighlight(
        ["x", "y", "unknown_func"],
        `
def func():
    from math import *  # Could import anything, including x
    return x + y + unknown_func()
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def func():
          from math import *  # Could import anything, including x
          return x + y + unknown_func()
                 ^   ^   ^^^^^^^^^^^^
      "
    `);
  });

  test("class variable vs instance variable", () => {
    expect(
      runHighlight(
        ["class_global", "instance_global"],
        `
class MyClass:
    class_var = class_global  # Should highlight class_global

    def __init__(self):
        self.instance_var = instance_global  # Should highlight instance_global

    def method(self):
        return self.class_var + self.instance_var
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      class MyClass:
          class_var = class_global  # Should highlight class_global
                      ^^^^^^^^^^^^

          def __init__(self):
              self.instance_var = instance_global  # Should highlight instance_global
                                  ^^^^^^^^^^^^^^^

          def method(self):
              return self.class_var + self.instance_var
      "
    `);
  });

  test("nested class with outer scope access", () => {
    expect(
      runHighlight(
        ["outer_var", "global_var"],
        `
def outer_func():
    outer_var = 1

    class InnerClass:
        # Classes can't access enclosing function scope directly
        value = global_var  # Should highlight global_var, not outer_var
        value2 = outer_var

        def method(self):
            return self.value + global_var

    return InnerClass()
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def outer_func():
          outer_var = 1

          class InnerClass:
              # Classes can't access enclosing function scope directly
              value = global_var  # Should highlight global_var, not outer_var
                      ^^^^^^^^^^
              value2 = outer_var

              def method(self):
                  return self.value + global_var
                                      ^^^^^^^^^^

          return InnerClass()
      "
    `);
  });

  test("should not highlight class keyword argument", () => {
    expect(
      runHighlight(
        ["a", "b", "c"],
        `
class Bar:
    def __init__(self, a, b):
        self.a = a
        self.b = b

Bar(a, b=b)
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      class Bar:
          def __init__(self, a, b):
              self.a = a
              self.b = b

      Bar(a, b=b)
          ^    ^
      "
    `);
  });

  test("should not highlight function keyword argument", () => {
    expect(
      runHighlight(
        ["a", "b"],
        `
def foo(a, b):
    print(a, b)

foo(a, b=b)
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def foo(a, b):
          print(a, b)

      foo(a, b=b)
          ^    ^
      "
    `);
  });

  test("should not highlight function keyword argument (with whitespace)", () => {
    expect(
      runHighlight(
        ["b"],
        `
def foo(a, b):
    print(a, b)

foo(a,
  b= b)

foo(a,
  b = b)

foo(a,
  b =

b)
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      def foo(a, b):
          print(a, b)

      foo(a,
        b= b)
           ^

      foo(a,
        b = b)
            ^

      foo(a,
        b =

      b)
      ^
      "
    `);
  });

  test("should not highlight class property", () => {
    expect(
      runHighlight(
        ["bar"],
        `
class Foo:
    bar = 10
    baz = bar
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      class Foo:
          bar = 10
          baz = bar
      "
    `);
  });

  test("class property referencing undefined then defined", () => {
    expect(
      runHighlight(
        ["bar"],
        `
class Foo:
    baz = bar
    bar = bar
    bar = 10
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      class Foo:
          baz = bar
                ^^^
          bar = bar
                ^^^
          bar = 10
      "
    `);
  });

  test("class property self-reference", () => {
    expect(
      runHighlight(
        ["bar"],
        `
class Foo:
    baz = bar
    bar = bar
    bar = bar
`,
      ),
    ).toMatchInlineSnapshot(`
      "
      class Foo:
          baz = bar
                ^^^
          bar = bar
                ^^^
          bar = bar
      "
    `);
  });
});

/**
 * Convenient helper for testing reactive variable highlighting
 */
function runHighlight(variableNames: string[], code: string): string {
  const variables: Variables = {};
  for (const name of variableNames) {
    variables[name as VariableName] = {
      name: name as VariableName,
      declaredBy: ["other-cell" as CellId],
      usedBy: [],
      value: "test-value",
      dataType: "str",
    };
  }
  const ranges = findReactiveVariables({
    cellId: "current-cell" as CellId,
    state: EditorState.create({
      doc: code,
      extensions: [python()],
    }),
    variables,
  });
  return formatCodeWithHighlights(code, ranges);
}

/**
 * Helper function to format code with highlighted ranges for snapshot testing
 * Simple format with carets pointing to reactive variables
 */
function formatCodeWithHighlights(
  code: string,
  ranges: ReactiveVariableRange[],
): string {
  const lines = code.split("\n");
  const result: string[] = [];

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
    const line = lines[lineIndex];

    // Start position of this line in the original code
    const lineStart =
      lines.slice(0, lineIndex).join("\n").length + (lineIndex > 0 ? 1 : 0);
    const lineEnd = lineStart + line.length;

    // Intersecting ranges
    const lineRanges = ranges.filter(
      (range) => range.from < lineEnd && range.to > lineStart,
    );

    result.push(line);

    if (lineRanges.length > 0) {
      // Create underline
      const underline = Array.from({ length: line.length }).fill(" ");

      for (const range of lineRanges) {
        const startInLine = Math.max(0, range.from - lineStart);
        const endInLine = Math.min(line.length, range.to - lineStart);

        for (let i = startInLine; i < endInLine; i++) {
          underline[i] = "^";
        }
      }

      // Add the underline if it has any markers
      if (underline.includes("^")) {
        result.push(underline.join("").trimEnd());
      }
    }
  }

  // Ensure result starts and ends with empty lines for nicer snapshot view
  const out = [...result];
  if (out[0] !== "") {
    out.unshift("");
  }
  if (out[out.length - 1] !== "") {
    out.push("");
  }
  return out.join("\n");
}
