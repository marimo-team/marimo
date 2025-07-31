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
