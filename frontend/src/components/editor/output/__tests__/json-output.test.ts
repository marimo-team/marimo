/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { determineMaxDisplayLength, getCopyValue } from "../JsonOutput";

describe("getCopyValue", () => {
  it("should handle strings without MIME prefixes", () => {
    const value = "simple string";
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`""simple string""`);
  });

  it("should handle strings with MIME prefixes", () => {
    const value = "text/plain:Hello, World!";
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`""Hello, World!""`);
  });

  it("should handle booleans", () => {
    expect(getCopyValue(true)).toMatchInlineSnapshot(`"True"`);
    expect(getCopyValue(false)).toMatchInlineSnapshot(`"False"`);
  });

  it("should handle null and undefined", () => {
    expect(getCopyValue(null)).toMatchInlineSnapshot(`"None"`);
    expect(getCopyValue(undefined)).toMatchInlineSnapshot(`"None"`);
  });

  it("should handle arrays", () => {
    const value = ["text/plain:Hello", true, null];
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`
      "[
        "Hello",
        True,
        None
      ]"
    `);
  });

  it("should handle objects", () => {
    const value = {
      key1: "text/plain:Hello",
      key2: false,
      key3: null,
    };
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(
      `
      "{
        "key1": "Hello",
        "key2": False,
        "key3": None
      }"
    `,
    );
  });

  it("should handle a string called true and None", () => {
    const value = {
      true: "true",
      None: "none",
      null: "null",
      sentence: "something true none null something",
    };
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(
      `
      "{
        "true": "true",
        "None": "none",
        "null": "null",
        "sentence": "something true none null something"
      }"
    `,
    );
  });

  it("should handle nested objects", () => {
    const value = {
      key1: {
        nestedKey1: "text/plain:Nested Hello",
        nestedKey2: true,
      },
      key2: false,
    };
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(
      `
      "{
        "key1": {
          "nestedKey1": "Nested Hello",
          "nestedKey2": True
        },
        "key2": False
      }"
    `,
    );
  });

  it("should handle nested arrays", () => {
    const value = ["text/plain:Hello", [true, null, "text/plain:World"]];
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`
      "[
        "Hello",
        [
          True,
          None,
          "World"
        ]
      ]"
    `);
  });

  it("should handle empty objects", () => {
    const value = {};
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`"{}"`);
  });

  it("should handle empty arrays", () => {
    const value: string[] = [];
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`"[]"`);
  });

  it("should handle numbers", () => {
    const value = 42;
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`"42"`);
  });

  it("should handle special characters in strings", () => {
    const value = "text/plain:Hello, \nWorld!";
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`""Hello, \\nWorld!""`);
  });

  it("should handle mixed types in arrays", () => {
    const value = [42, "text/plain:Hello", true, null];
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`
      "[
        42,
        "Hello",
        True,
        None
      ]"
    `);
  });

  it("should handle mixed types in objects", () => {
    const value = {
      key1: 42,
      key2: "text/plain:Hello",
      key3: true,
      key4: null,
      key5: "text/plain+float:1.23",
    };
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(
      `
      "{
        "key1": 42,
        "key2": "Hello",
        "key3": True,
        "key4": None,
        "key5": 1.23
      }"
    `,
    );
  });

  it("should handle sets", () => {
    const value = "text/plain+set:[1,2,3]";
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`"{1, 2, 3}"`);
  });

  it("should handle empty set", () => {
    // Empty set literal in Python is `set()`, not `{}` (which is a dict).
    expect(getCopyValue("text/plain+set:[]")).toMatchInlineSnapshot(`"set()"`);
  });

  it("should handle frozenset values", () => {
    expect(getCopyValue("text/plain+frozenset:[1,2]")).toMatchInlineSnapshot(
      `"frozenset({1, 2})"`,
    );
    expect(getCopyValue("text/plain+frozenset:[]")).toMatchInlineSnapshot(
      `"frozenset()"`,
    );
  });

  it("should handle sets in mixed types", () => {
    const value = {
      key1: 42,
      key2: "text/plain+set:[1,2,3]",
      key3: true,
    };
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(
      `
      "{
        "key1": 42,
        "key2": {1, 2, 3},
        "key3": True
      }"
    `,
    );
  });

  it("should handle tuples", () => {
    const value = "text/plain+tuple:[1,2,3]";
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`"(1,2,3)"`);
  });

  it("should handle tuples in mixed types", () => {
    const value = {
      key1: 42,
      key2: "text/plain+tuple:[1,2,3]",
      key3: true,
    };
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(
      `
      "{
        "key1": 42,
        "key2": (1,2,3),
        "key3": True
      }"
    `,
    );
  });

  it("should handle bigint", () => {
    const bigint = String(BigInt(2 ** 64));
    const value = `text/plain+bigint:${bigint}`;
    const result = getCopyValue(value);
    expect(result).toMatchInlineSnapshot(`"18446744073709551616"`);

    const nestedBigInt = {
      key1: bigint, // this will be just a string
      key2: `text/plain+bigint:${bigint}`, // this will convert to number
      key3: true,
    };
    const nestedResult = getCopyValue(nestedBigInt);
    expect(nestedResult).toMatchInlineSnapshot(
      `
      "{
        "key1": "18446744073709551616",
        "key2": 18446744073709551616,
        "key3": True
      }"
      `,
    );

    const bigintRaw = BigInt(2 ** 64);
    const bigintRawResult = getCopyValue(bigintRaw);
    expect(bigintRawResult).toMatchInlineSnapshot(`"18446744073709551616"`);

    const nestedBigIntRaw = {
      key1: bigintRaw, // raw number
      key2: `text/plain+bigint:${bigintRaw}`,
      key3: true,
    };
    const nestedBigIntRawResult = getCopyValue(nestedBigIntRaw);
    expect(nestedBigIntRawResult).toMatchInlineSnapshot(
      `
      "{
        "key1": 18446744073709551616,
        "key2": 18446744073709551616,
        "key3": True
      }"
      `,
    );
  });
});

describe("determineMaxDisplayLength", () => {
  const sample2DArray = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
    [10, 11, 12],
    [13, 14, 15],
    [16, 17, 18],
    [19, 20, 21],
    [22, 23, 24],
    [25, 26, 27],
    [28, 29, 30],
  ];

  it("should return undefined for 1 level arrays", () => {
    const value = [1, 2, 3];
    const result = determineMaxDisplayLength(value);
    expect(result).toBeUndefined();
  });

  it("should return undefined for 2 level arrays with less than 20 items", () => {
    const value = sample2DArray;
    const result = determineMaxDisplayLength(value);
    expect(result).toBeUndefined();
  });

  it("should return 10 for 2 level arrays with more than 20 items", () => {
    const longArray = Array.from({ length: 21 }, (_, i) => i);
    const value = [...sample2DArray, longArray];
    const result = determineMaxDisplayLength(value);
    expect(result).toBe(10);
  });

  it("should return 5 for 2 level arrays with more than 50 items", () => {
    const longArray = Array.from({ length: 51 }, (_, i) => i);
    const value = [...sample2DArray, longArray];
    const result = determineMaxDisplayLength(value);
    expect(result).toBe(5);
  });

  it("should return 5 for 3 level arrays with more than 20 items", () => {
    const longArray = Array.from({ length: 21 }, (_, i) => i);
    const value = [[...sample2DArray], [...sample2DArray, longArray]];
    const result = determineMaxDisplayLength(value);
    expect(result).toBe(5);
  });
});

describe("getCopyValue with encoded non-string keys", () => {
  // Keys are encoded by _key_formatter in
  // marimo/_output/formatters/structures.py. Frontend must round-trip them
  // to Python literals in the copy output.

  it("decodes int keys unquoted", () => {
    // JS reorders integer-like string keys to the front of object iteration
    // (spec-mandated), so `"2"` appears before `"text/plain+int:2"` here.
    // This is pre-existing and unrelated to the encoding — both entries
    // survive, which is the regression this guards.
    const value = { "text/plain+int:2": "no", "2": "oh" };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        "2": "oh",
        2: "no"
      }"
    `);
  });

  it("decodes large int keys unquoted (no BigInt precision concern)", () => {
    const value = { "text/plain+int:18446744073709551616": "v" };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        18446744073709551616: "v"
      }"
    `);
  });

  it("decodes float, bool, None, tuple, frozenset keys", () => {
    const value = {
      "text/plain+float:2.5": "f",
      "text/plain+bool:True": "t",
      "text/plain+bool:False": "b",
      "text/plain+none:": "n",
      "text/plain+tuple:[1, 2]": "tup",
      "text/plain+frozenset:[3, 4]": "fs",
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        2.5: "f",
        True: "t",
        False: "b",
        None: "n",
        (1, 2): "tup",
        frozenset({3, 4}): "fs"
      }"
    `);
  });

  it("emits 1-element tuple keys with a trailing comma (Python syntax)", () => {
    // `(1)` is just `1` in Python — a 1-tuple needs `(1,)`.
    const value = {
      "text/plain+tuple:[1]": "one",
      "text/plain+tuple:[]": "empty",
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        (1,): "one",
        (): "empty"
      }"
    `);
  });

  it("emits empty frozenset keys as `frozenset()` not `frozenset({})`", () => {
    // `frozenset({})` reads like it's constructing from an empty dict.
    const value = {
      "text/plain+frozenset:[]": "empty",
      "text/plain+frozenset:[1]": "single",
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        frozenset(): "empty",
        frozenset({1}): "single"
      }"
    `);
  });

  it("decodes NaN/Inf float keys to valid Python literals", () => {
    const value = {
      "text/plain+float:nan": "n",
      "text/plain+float:inf": "p",
      "text/plain+float:-inf": "m",
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        float('nan'): "n",
        float('inf'): "p",
        -float('inf'): "m"
      }"
    `);
  });

  it("parses tuple/frozenset payloads containing bare NaN/Infinity", () => {
    // Python's json.dumps emits bare `NaN`/`Infinity` inside the embedded
    // tuple/frozenset payload strings (JSON spec violation, but ECMA-262-
    // friendly via the fallback in jsonParseWithSpecialChar). The outer
    // JSON stays strict because those tokens live inside a JSON string
    // key/value. Regression for tuple-key payloads that previously broke
    // the frontend's `JSON.parse` and threw.
    const value = {
      "text/plain+tuple:[NaN]": "tn",
      "text/plain+tuple:[Infinity, -Infinity]": "ti",
      k: "text/plain+frozenset:[Infinity, 1]",
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        (float('nan'),): "tn",
        (float('inf'), -float('inf')): "ti",
        "k": frozenset({float('inf'), 1})
      }"
    `);
  });

  it("unescapes string keys that looked encoded", () => {
    const value = {
      "text/plain+str:text/plain+int:2": "hello",
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        "text/plain+int:2": "hello"
      }"
    `);
  });

  it("decodes keys at every nesting level", () => {
    const value = {
      outer: {
        "text/plain+int:1": "inner",
        "text/plain+tuple:[2, 3]": "tup",
      },
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        "outer": {
          1: "inner",
          (2, 3): "tup"
        }
      }"
    `);
  });

  it("leaves plain string keys untouched", () => {
    const value = { foo: 1, bar: 2 };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        "foo": 1,
        "bar": 2
      }"
    `);
  });
});

describe("getCopyValue with application/ mimetypes", () => {
  it("should strip application/ mimetype prefix from leaf data", () => {
    expect(getCopyValue("application/json:{data}")).toBe('"{data}"');
    expect(getCopyValue("application/custom:some-data")).toBe('"some-data"');
    expect(getCopyValue("application/vnd.marimo+error:error")).toBe('"error"');
  });

  it("should handle application/ mimetypes in mixed objects", () => {
    const value = {
      appMime: "application/custom:data",
      plainText: "text/plain:hello",
      number: 42,
    };
    const result = getCopyValue(value);
    expect(result).toContain('"appMime": "data"');
    expect(result).toContain('"plainText": "hello"');
    expect(result).toContain('"number": 42');
  });
});
