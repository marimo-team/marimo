/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { areLogicallyDifferent } from "../edited";

describe("areLogicallyDifferent - same code", () => {
  test("identical code returns false", () => {
    const code = "def foo(): return 42";
    expect(areLogicallyDifferent(code, code)).toBe(false);
  });

  test("different whitespace returns false", () => {
    const code1 = "def foo():\n\n\n    return 42";
    const code2 = "def foo(): return 42";
    expect(areLogicallyDifferent(code1, code2)).toBe(false);
  });

  test("different comments return false", () => {
    const code1 = "def foo(): # first comment\n    return 42";
    const code2 = "def foo(): # different comment\n    return 42";
    expect(areLogicallyDifferent(code1, code2)).toBe(false);
  });

  test("new lines before and after return statements are ignored", () => {
    const code1 = "def foo(): return 42\n";
    const code2 = "def foo(): return 42\n\n";
    const code3 = "\n\ndef foo(): return 42";
    expect(areLogicallyDifferent(code1, code2)).toBe(false);
    expect(areLogicallyDifferent(code1, code3)).toBe(false);
    expect(areLogicallyDifferent(code2, code3)).toBe(false);
  });

  test("handles unicode characters", () => {
    const code1 = 'print("Hello 世界")';
    const code2 = 'print("Hello 世界")';
    expect(areLogicallyDifferent(code1, code2)).toBe(false);
  });

  test("complex class definitions", () => {
    const code1 = `
      class MyClass:
          def __init__(self):
              self.x = 42

          def method(self):
              return self.x
    `;
    const code2 = `
      class MyClass:
          def __init__(self):  # Initialize
              self.x = 42      # Set x

          def method(self):    # Get x
              return self.x    # Return it
    `;
    expect(areLogicallyDifferent(code1, code2)).toBe(false);
  });

  test("function with types", () => {
    expect(
      areLogicallyDifferent(
        "def foo(x: int) -> int: return x",
        "def foo(x: int) -> int: return x",
      ),
    ).toBe(false);
  });
});

describe("areLogicallyDifferent - different code", () => {
  test("multiline comments return true", () => {
    const code1 = `"""
      This is a long docstring
      with multiple lines
    """
    def foo(): return 42`;
    const code2 = `"""Different docstring"""
    def foo(): return 42`;
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("different function names return true", () => {
    const code1 = "def foo(): return 42";
    const code2 = "def bar(): return 42";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("function with parsing error", () => {
    const code1 = "def foo(): return 42";
    const code2 = "def foo():\nreturn 42";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("different string literals return true", () => {
    const code1 = 'print("hello")';
    const code2 = 'print("world")';
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("different number literals return true", () => {
    const code1 = "x = 42";
    const code2 = "x = 43";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("different operators return true", () => {
    const code1 = "x + y";
    const code2 = "x - y";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("different control flow returns true", () => {
    const code1 = "if x: pass";
    const code2 = "while x: pass";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("different indentation structure returns true", () => {
    const code1 = "if x:\n    if y: pass";
    const code2 = "if x:\n    pass\nif y: pass";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("handles invalid Python syntax", () => {
    const code1 = "this is not python";
    const code2 = "also not python";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("decorators are preserved", () => {
    const code1 = "@decorator\ndef func(): pass";
    const code2 = "def func(): pass";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("type hints affect comparison", () => {
    const code1 = "def func(x: int) -> int: return x";
    const code2 = "def func(x): return x";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("different string quote styles return true", () => {
    const code1 = 'x = "hello"';
    const code2 = "x = 'hello'";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });
});

describe("areLogicallyDifferent - advanced Python features", () => {
  test("lambda functions", () => {
    expect(
      areLogicallyDifferent("x = lambda a: a + 1", "x = lambda b: b + 1"),
    ).toBe(true);

    expect(
      areLogicallyDifferent("x = lambda a: a + 1", "x = lambda a: a - 1"),
    ).toBe(true);
  });

  test("list comprehensions", () => {
    expect(
      areLogicallyDifferent(
        "[x for x in range(10) if x % 2 == 0]",
        "[x for x in range(10) if x % 2 == 1]",
      ),
    ).toBe(true);
  });

  test("try/except blocks", () => {
    const code1 = `
      try:
        raise ValueError()
      except ValueError:
        pass
    `;
    const code2 = `
      try:
        raise ValueError()
      except Exception:
        pass
    `;
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("multiline strings with different line endings", () => {
    expect(
      areLogicallyDifferent(
        'x = """hello\nworld\n"""',
        'x = """hello\r\nworld\r\n"""',
      ),
    ).toBe(true);
  });

  test("nested function definitions", () => {
    const code1 = `
      def outer():
        def inner(): pass
        return inner
    `;
    const code2 = `
      def outer():
        def different(): pass
        return different
    `;
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("number literals in different bases", () => {
    expect(areLogicallyDifferent("x = 0xFF", "x = 255")).toBe(true);

    expect(areLogicallyDifferent("x = 0o10", "x = 8")).toBe(true);
  });

  test("f-strings vs regular strings", () => {
    expect(areLogicallyDifferent('x = f"hello {42}"', 'x = "hello 42"')).toBe(
      true,
    );
  });

  test("async functions", () => {
    const code1 = "async def foo(): pass";
    const code2 = "def foo(): pass";
    expect(areLogicallyDifferent(code1, code2)).toBe(true);
  });

  test("multiple assignments", () => {
    expect(areLogicallyDifferent("a = b = c = 1", "a, b, c = 1, 1, 1")).toBe(
      true,
    );
  });

  test("walrus operator", () => {
    expect(
      areLogicallyDifferent("if (x := 42) > 0: pass", "x = 42\nif x > 0: pass"),
    ).toBe(true);
  });

  test("function with types", () => {
    expect(
      areLogicallyDifferent(
        "def foo(x: int) -> int: return x",
        "def foo(x: float) -> int: return x",
      ),
    ).toBe(true);
  });
});

test("handles empty strings", () => {
  expect(areLogicallyDifferent("", "")).toBe(false);
  expect(areLogicallyDifferent("pass", "")).toBe(true);
});

test("handles invalid python code", () => {
  const code1 = "x = 1 +";
  const code2 = "x = 1 +";
  expect(areLogicallyDifferent(code1, code2)).toBe(false);

  const code3 = "x = 1 +";
  const code4 = "x = 1 -";
  expect(areLogicallyDifferent(code3, code4)).toBe(true);
});
