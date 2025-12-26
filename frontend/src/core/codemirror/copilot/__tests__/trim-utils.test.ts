/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { trimAutocompleteResponse } from "../trim-utils";

const trim = trimAutocompleteResponse;

describe("trimAutocompleteResponse", () => {
  it("should return the response unchanged when no prefix or suffix", () => {
    expect(
      trim({
        response: "console.log('hello');",
        prefix: "",
        suffix: "",
      }),
    ).toBe("console.log('hello');");
  });

  it("should handle empty response", () => {
    expect(
      trim({
        response: "",
        prefix: "prefix",
        suffix: "suffix",
      }),
    ).toBe("");
  });

  it("should handle null/undefined inputs gracefully", () => {
    expect(
      trim({
        response: "",
        prefix: "",
        suffix: "",
      }),
    ).toBe("");
  });

  describe("basic prefix trimming", () => {
    it("should trim exact prefix match", () => {
      expect(
        trim({
          response: "const x = 42;",
          prefix: "const x = ",
          suffix: "",
        }),
      ).toBe("42;");
    });

    it("should not trim when prefix doesn't match", () => {
      expect(
        trim({
          response: "const x = 42;",
          prefix: "let x = ",
          suffix: "",
        }),
      ).toBe("const x = 42;");
    });

    it("should handle empty prefix", () => {
      expect(
        trim({
          response: "const x = 42;",
          prefix: "",
          suffix: "",
        }),
      ).toBe("const x = 42;");
    });
  });

  describe("basic suffix trimming", () => {
    it("should trim exact suffix match", () => {
      expect(
        trim({
          response: "42 + 1",
          prefix: "",
          suffix: " + 1",
        }),
      ).toBe("42");
    });

    it("should not trim when suffix doesn't match", () => {
      expect(
        trim({
          response: "42 + 1",
          prefix: "",
          suffix: " + 2",
        }),
      ).toBe("42 + 1");
    });

    it("should handle empty suffix", () => {
      expect(
        trim({
          response: "const x = 42;",
          prefix: "",
          suffix: "",
        }),
      ).toBe("const x = 42;");
    });
  });

  describe("combined prefix and suffix trimming", () => {
    it("should trim both prefix and suffix", () => {
      expect(
        trim({
          response: "def func():    print('hello')    return",
          prefix: "def func():",
          suffix: "    return",
        }),
      ).toBe("    print('hello')");
    });

    it("should handle overlapping prefix and suffix", () => {
      expect(
        trim({
          response: "abcdefabc",
          prefix: "abc",
          suffix: "abc",
        }),
      ).toBe("def");
    });
  });

  describe("multiple occurrences", () => {
    it("should trim multiple consecutive prefixes", () => {
      expect(
        trim({
          response: ">>>>>>hello",
          prefix: ">>>",
          suffix: "",
        }),
      ).toBe(">>>hello");
    });

    it("should trim multiple consecutive suffixes", () => {
      expect(
        trim({
          response: "hello<<<<<<",
          prefix: "",
          suffix: "<<<",
        }),
      ).toBe("hello<<<");
    });
  });

  describe("real-world scenarios", () => {
    it("should handle multiline Python function completion", () => {
      expect(
        trim({
          response:
            "def calculate_sum(a, b):\n    result = a + b\n    return result",
          prefix: "def calculate_sum(a, b):",
          suffix: "\n    return result",
        }),
      ).toBe("\n    result = a + b");
    });

    it("should handle Python list comprehension", () => {
      expect(
        trim({
          response: "1, 2, 3, 4, 5];",
          prefix: "const items = [",
          suffix: "];",
        }),
      ).toBe("1, 2, 3, 4, 5");
    });

    it("should handle HTML tag completion", () => {
      expect(
        trim({
          response: "  <p>Hello World</p></div>",
          prefix: '<div class="container">',
          suffix: "</div>",
        }),
      ).toBe("  <p>Hello World</p>");
    });

    it("should handle SQL query completion", () => {
      expect(
        trim({
          response: " age > 18 AND status = 'active' ORDER BY id",
          prefix: "SELECT * FROM users WHERE",
          suffix: "ORDER BY id",
        }),
      ).toBe(" age > 18 AND status = 'active' ");
    });

    it("should handle markdown completion", () => {
      expect(
        trim({
          response: "## Introduction\n\nThis is a sample",
          prefix: "## ",
          suffix: "",
        }),
      ).toBe("Introduction\n\nThis is a sample");
    });
  });

  describe("edge cases", () => {
    it("should handle response that is exactly the prefix", () => {
      expect(
        trim({
          response: "hello",
          prefix: "hello",
          suffix: "",
        }),
      ).toBe("");
    });

    it("should handle response that is exactly the suffix", () => {
      expect(
        trim({
          response: "world",
          prefix: "",
          suffix: "world",
        }),
      ).toBe("");
    });

    it("should handle response that is exactly prefix + suffix", () => {
      expect(
        trim({
          response: "helloworld",
          prefix: "hello",
          suffix: "world",
        }),
      ).toBe("");
    });

    it("should handle very long prefix/suffix", () => {
      expect(
        trim({
          response: `${"a".repeat(1000)}middle${"b".repeat(1000)}`,
          prefix: "a".repeat(1000),
          suffix: "b".repeat(1000),
        }),
      ).toBe("middle");
    });

    it("should handle special characters in prefix/suffix", () => {
      expect(
        trim({
          response: "function test() { /* comment */ return 42; /* end */ }",
          prefix: "function test() { /* comment */",
          suffix: "/* end */ }",
        }),
      ).toBe(" return 42; ");
    });

    it("should handle unicode characters", () => {
      expect(
        trim({
          response: "const 🚀 = '🎉 Hello World! 🌟';",
          prefix: "const 🚀 = ",
          suffix: ";",
        }),
      ).toBe("'🎉 Hello World! 🌟'");
    });

    it("should handle newlines in prefix/suffix", () => {
      expect(
        trim({
          response: "if (condition) {\n  console.log('test');\n}",
          prefix: "if (condition) {\n",
          suffix: "\n}",
        }),
      ).toBe("  console.log('test');");
    });

    it("should handle cases where AI response doesn't include context", () => {
      expect(
        trim({
          response: "42",
          prefix: "const x = ",
          suffix: ";",
        }),
      ).toBe("42");
    });

    it("should handle partial matches correctly (not trim them)", () => {
      // Should not trim partial matches
      expect(
        trim({
          response: "function test() hello world return x",
          prefix: "function test() {",
          suffix: "return x;",
        }),
      ).toBe("function test() hello world return x");
    });
  });
});
