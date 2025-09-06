/* Copyright 2024 Marimo. All rights reserved. */
import { expect, it } from "vitest";
import { jsonParseWithSpecialChar, jsonToTSV } from "../json/json-parser";

it("can jsonParseWithSpecialChar happy path", () => {
  expect(jsonParseWithSpecialChar('"hello"')).toEqual("hello");
  expect(
    jsonParseWithSpecialChar(
      '[false,{"a":1},true,0,1,[{"a":1},{"b":2}],"hello",""]',
    ),
  ).toEqual([false, { a: 1 }, true, 0, 1, [{ a: 1 }, { b: 2 }], "hello", ""]);

  expect(jsonParseWithSpecialChar("10")).toEqual(10);
  expect(jsonParseWithSpecialChar("null")).toEqual(null);
});

it("can jsonParseWithSpecialChar NaN, Infinity, -Infinity", () => {
  expect(jsonParseWithSpecialChar("NaN")).toEqual(Number.NaN);
  expect(jsonParseWithSpecialChar('{"A":NaN}')).toEqual({ A: Number.NaN });
  expect(jsonParseWithSpecialChar("[NaN]")).toEqual([Number.NaN]);
  expect(jsonParseWithSpecialChar("[-Infinity]")).toEqual([
    Number.NEGATIVE_INFINITY,
  ]);
  expect(jsonParseWithSpecialChar("[Infinity]")).toEqual([
    Number.POSITIVE_INFINITY,
  ]);
  expect(
    jsonParseWithSpecialChar('[NaN,Infinity,-Infinity,{"A": NaN}]'),
  ).toEqual([
    Number.NaN,
    Number.POSITIVE_INFINITY,
    Number.NEGATIVE_INFINITY,
    { A: Number.NaN },
  ]);

  // Prevent false positives as text
  expect(jsonParseWithSpecialChar('"NaN"')).toEqual("NaN");
  expect(jsonParseWithSpecialChar('"Infinity"')).toEqual("Infinity");
  expect(jsonParseWithSpecialChar('"-Infinity"')).toEqual("-Infinity");

  expect(jsonParseWithSpecialChar('"This is NaN"')).toEqual("This is NaN");
  expect(jsonParseWithSpecialChar('"To Infinity and Beyond"')).toEqual(
    "To Infinity and Beyond",
  );
  expect(jsonParseWithSpecialChar('"To -Infinity and Beyond"')).toEqual(
    "To -Infinity and Beyond",
  );
});

it("can fail to jsonParseWithSpecialChar", () => {
  // Fail to parse
  expect(jsonParseWithSpecialChar("")).toMatchInlineSnapshot("{}");
  expect(jsonParseWithSpecialChar("undefined")).toMatchInlineSnapshot("{}");
  expect(jsonParseWithSpecialChar(undefined!)).toMatchInlineSnapshot("{}");
  expect(jsonParseWithSpecialChar("[nan]")).toMatchInlineSnapshot("{}");
});

it("can convert large integer strings to BigInt", () => {
  // Large positive integer
  const largeInt = "599087340098420735";
  const result = jsonParseWithSpecialChar(`{"value": "${largeInt}"}`);
  expect(result).toEqual({ value: BigInt(largeInt) });

  // Large negative integer
  const largeNegInt = "-599087340098420735";
  const resultNeg = jsonParseWithSpecialChar(`{"value": "${largeNegInt}"}`);
  expect(resultNeg).toEqual({ value: BigInt(largeNegInt) });

  // Array of large integers
  const arrayResult = jsonParseWithSpecialChar(
    `[{"big_list": ["${largeInt}", "${largeNegInt}"]}]`,
  );
  expect(arrayResult).toEqual([
    { big_list: [BigInt(largeInt), BigInt(largeNegInt)] },
  ]);

  // Mixed data with regular integers (should not be converted)
  const mixedResult = jsonParseWithSpecialChar(
    `{"regular": "42", "large": "${largeInt}", "float": "3.14"}`,
  );
  expect(mixedResult).toEqual({
    regular: "42", // Small integer string should remain string
    large: BigInt(largeInt), // Large integer string should become BigInt
    float: "3.14", // Float string should remain string
  });

  // Nested objects
  const nestedResult = jsonParseWithSpecialChar(
    `{"data": {"values": ["${largeInt}", "999742000000000000"]}}`,
  );
  expect(nestedResult).toEqual({
    data: { values: [BigInt(largeInt), BigInt("999742000000000000")] },
  });
});

it("should not convert non-large integer strings", () => {
  // Small integers should remain as strings if they're already strings
  const smallIntResult = jsonParseWithSpecialChar('{"value": "42"}');
  expect(smallIntResult).toEqual({ value: "42" });

  // Non-integer strings should remain unchanged
  const textResult = jsonParseWithSpecialChar('{"value": "hello world"}');
  expect(textResult).toEqual({ value: "hello world" });

  // Float strings should remain unchanged
  const floatResult = jsonParseWithSpecialChar('{"value": "3.14159"}');
  expect(floatResult).toEqual({ value: "3.14159" });

  // Scientific notation should remain unchanged
  const sciResult = jsonParseWithSpecialChar('{"value": "1e10"}');
  expect(sciResult).toEqual({ value: "1e10" });

  // Empty string should remain unchanged
  const emptyResult = jsonParseWithSpecialChar('{"value": ""}');
  expect(emptyResult).toEqual({ value: "" });
});

it("should handle edge cases for BigInt conversion", () => {
  // At the boundary of safe integers
  const maxSafeResult = jsonParseWithSpecialChar(
    `{"value": "${Number.MAX_SAFE_INTEGER}"}`,
  );
  expect(maxSafeResult).toEqual({ value: `${Number.MAX_SAFE_INTEGER}` }); // Should remain string

  const overMaxSafeResult = jsonParseWithSpecialChar(
    `{"value": "${Number.MAX_SAFE_INTEGER + 1}"}`,
  );
  expect(overMaxSafeResult).toEqual({
    value: BigInt(Number.MAX_SAFE_INTEGER + 1),
  }); // Should become BigInt

  // Invalid BigInt strings should remain as strings
  const invalidResult = jsonParseWithSpecialChar('{"value": "not-a-number"}');
  expect(invalidResult).toEqual({ value: "not-a-number" });
});

it("can convert json to tsv", () => {
  expect(jsonToTSV([])).toEqual("");

  expect(jsonToTSV([{ a: 1, b: 2 }])).toEqual("a\tb\n1\t2");

  expect(
    jsonToTSV([
      { a: 1, b: 2 },
      { a: 3, b: 4 },
    ]),
  ).toEqual("a\tb\n1\t2\n3\t4");

  // Does not handle sparse arrays
  expect(jsonToTSV([{ a: 1 }, { a: 2, b: 3 }])).toMatchInlineSnapshot(
    '"a\n1\n2"',
  );

  // Handles special characters
  expect(
    jsonToTSV([{ a: "hello\tworld", b: "new\nline" }]),
  ).toMatchInlineSnapshot('"a\tb\nhello\tworld\tnew\nline"');
});
