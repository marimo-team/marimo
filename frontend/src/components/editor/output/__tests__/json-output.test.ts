/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  decodeShowMore,
  determineMaxDisplayLength,
  encodeShowMore,
  estimateExpandedLines,
  getCopyValue,
  jsonCopyValue,
  stripSentinels,
  truncateNode,
} from "../JsonOutput";

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
  it("should strip sentinels from data with show-more markers", () => {
    const sentinel = encodeShowMore(10, "$.foo");
    // Array: sentinel → undefined → null in JSON → None in Python copy
    expect(getCopyValue([1, 2, sentinel])).toMatchInlineSnapshot(`
      "[
        1,
        2,
        null
      ]"
    `);
    // Object: sentinel key is fully omitted
    const obj: Record<string, unknown> = { a: 1 };
    obj[sentinel] = sentinel;
    expect(getCopyValue(obj)).toMatchInlineSnapshot(`
      "{
        "a": 1
      }"
    `);
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

  it("falls back to the raw payload for malformed tuple/frozenset", () => {
    // `jsonParseWithSpecialChar` returns `{}` on parse failure rather
    // than throwing; without an `Array.isArray` guard, the formatters
    // would crash on `.length`/`.map`. Pass the raw payload through so
    // a malformed wire form doesn't break the whole render.
    const value = {
      "text/plain+tuple:not a json list": "t",
      k: "text/plain+frozenset:also broken",
    };
    expect(getCopyValue(value)).toMatchInlineSnapshot(`
      "{
        not a json list: "t",
        "k": also broken
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

describe("estimateExpandedLines", () => {
  it("scalars count as 1", () => {
    expect(estimateExpandedLines(42, 100)).toBe(1);
    expect(estimateExpandedLines(null, 100)).toBe(1);
  });

  it("flat containers = child count", () => {
    expect(estimateExpandedLines({ a: 1, b: 2, c: 3 }, 100)).toBe(3);
    expect(estimateExpandedLines([1, 2, 3, 4], 100)).toBe(4);
  });

  it("small nested children expand recursively", () => {
    expect(estimateExpandedLines({ a: { x: 1, y: 2 }, b: 3 }, 100)).toBe(3);
  });

  it("large children count as 1 collapsed line", () => {
    const big = Array.from({ length: 20 }, (_, i) => i);
    expect(estimateExpandedLines({ a: big, b: 1 }, 100)).toBe(2);
  });

  it("bails at cap", () => {
    const big = Array.from({ length: 500 }, (_, i) => i);
    expect(estimateExpandedLines(big, 50)).toBe(50);
  });

  it("bails at max depth", () => {
    // 6 levels deep, each 1 child — should bail at depth 4
    const data = { a: { b: { c: { d: { e: { f: 1 } } } } } };
    expect(estimateExpandedLines(data, 100)).toBe(1);
  });
});

describe("truncateNode", () => {
  const wm = () => new WeakMap<object, object>();

  it("passes through primitives", () => {
    expect(truncateNode(42, {}, "$", 0, wm())).toBe(42);
    expect(truncateNode("hi", {}, "$", 0, wm())).toBe("hi");
    expect(truncateNode(null, {}, "$", 0, wm())).toBe(null);
  });

  it("truncates arrays > PAGE_SIZE and appends sentinel", () => {
    const arr = Array.from({ length: 60 }, (_, i) => i);
    const originals = wm();
    const result = truncateNode(arr, {}, "$", 0, originals) as unknown[];
    expect(result).toHaveLength(31); // 30 items + 1 sentinel
    expect(result.slice(0, 30)).toEqual(arr.slice(0, 30));
    expect(decodeShowMore(result[30])).toEqual({
      remaining: "30",
      path: "$",
    });
    // originals map points back to the full array
    expect(originals.get(result)).toBe(arr);
  });

  it("truncates objects > PAGE_SIZE and appends sentinel key", () => {
    const obj: Record<string, number> = {};
    for (let i = 0; i < 60; i++) {
      obj[`k${i}`] = i;
    }
    const originals = wm();
    const result = truncateNode(obj, {}, "$", 0, originals) as Record<
      string,
      unknown
    >;
    const keys = Object.keys(result);
    expect(keys).toHaveLength(31); // 30 keys + 1 sentinel key
    const lastVal = result[keys[keys.length - 1]];
    expect(decodeShowMore(lastVal)).toEqual({ remaining: "30", path: "$" });
    // originals map points back to the full object
    expect(originals.get(result)).toBe(obj);
  });

  it("respects custom limits", () => {
    const arr = Array.from({ length: 20 }, (_, i) => i);
    const result = truncateNode(arr, { $: 5 }, "$", 0, wm()) as unknown[];
    expect(result).toHaveLength(6); // 5 + sentinel
    expect(decodeShowMore(result[5])).toEqual({ remaining: "15", path: "$" });
  });

  it("does not truncate small containers", () => {
    expect(truncateNode([1, 2, 3], {}, "$", 0, wm())).toEqual([1, 2, 3]);
  });

  it("registers parent containers so copying includes truncated descendants", () => {
    const arr = [{ rows: Array.from({ length: 70 }, (_, i) => i) }];
    const originals = wm();
    const result = truncateNode(arr, {}, "$", 0, originals);
    expect(originals.get(result as object)).toBe(arr);
  });
  it("keeps pagination paths distinct for dotted keys and nested keys", () => {
    const values = Array.from({ length: 70 }, (_, i) => i);
    const data = { "a.b": values, a: { b: values } };
    const result = truncateNode(data, { '$."a.b"': 100 }, "$", 0, wm());
    expect(result).toEqual({
      "a.b": values,
      a: { b: [...values.slice(0, 30), encodeShowMore(40, '$."a"."b"')] },
    });
  });

  it("preserves own __proto__ keys", () => {
    const data = JSON.parse('{"__proto__":{"value":1}}');
    expect(JSON.stringify(truncateNode(data, {}, "$", 0, wm()))).toBe(
      JSON.stringify(data),
    );
  });

  it("uses smaller page sizes throughout a matrix", () => {
    const matrix = Array.from({ length: 30 }, () =>
      Array.from({ length: 60 }, (_, i) => i),
    );
    const result = truncateNode(matrix, {}, "$", 0, wm(), 5);
    expect(result).toEqual([
      ...Array.from({ length: 5 }, (_, i) => [
        0,
        1,
        2,
        3,
        4,
        encodeShowMore(55, `$.${i}`),
      ]),
      encodeShowMore(25, "$"),
    ]);
  });
});

describe("sentinel encode/decode round-trip", () => {
  it("round-trips", () => {
    const encoded = encodeShowMore(42, "$.foo.bar");
    const decoded = decodeShowMore(encoded);
    expect(decoded).toEqual({ remaining: "42", path: "$.foo.bar" });
  });

  it("returns null for non-sentinels", () => {
    expect(decodeShowMore("hello")).toBeNull();
    expect(decodeShowMore(42)).toBeNull();
    expect(decodeShowMore(null)).toBeNull();
  });
});

describe("stripSentinels", () => {
  it("strips sentinel keys", () => {
    const key = encodeShowMore(5, "$.x");
    expect(stripSentinels(key, "anything")).toBeUndefined();
  });

  it("strips sentinel values", () => {
    const val = encodeShowMore(5, "$.x");
    expect(stripSentinels("normalKey", val)).toBeUndefined();
  });

  it("passes through normal data", () => {
    expect(stripSentinels("key", "value")).toBe("value");
    expect(stripSentinels("key", 42)).toBe(42);
  });
});

describe("jsonCopyValue", () => {
  it("strips sentinels from arrays (replaced with null per JSON spec)", () => {
    const sentinel = encodeShowMore(10, "$");
    expect(JSON.parse(jsonCopyValue([1, 2, sentinel]))).toEqual([1, 2, null]);
  });

  it("strips sentinel keys from objects", () => {
    const sentinel = encodeShowMore(10, "$");
    const obj: Record<string, unknown> = { a: 1 };
    obj[sentinel] = sentinel;
    expect(JSON.parse(jsonCopyValue(obj))).toEqual({ a: 1 });
  });
});
