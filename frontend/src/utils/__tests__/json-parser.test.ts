/* Copyright 2024 Marimo. All rights reserved. */
import { expect, it } from "vitest";
import {
  jsonParseWithSpecialChar,
  jsonToMarkdown,
  jsonToTSV,
} from "../json/json-parser";

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

it("can parse bigInts", () => {
  const bigint = JSON.stringify({ bigint: { $bigint: "123456" } });
  expect(jsonParseWithSpecialChar(bigint)).toEqual({ bigint: BigInt(123_456) });

  const arrayOfBigInts = JSON.stringify([{ $bigint: "123456" }]);
  expect(jsonParseWithSpecialChar(arrayOfBigInts)).toEqual([BigInt(123_456)]);

  const nestedBigInt = JSON.stringify({ bigint: [{ $bigint: "123456" }] });
  expect(jsonParseWithSpecialChar(nestedBigInt)).toEqual({
    bigint: [BigInt(123_456)],
  });
});

it("can convert json to tsv with en-US locale", () => {
  const locale = "en-US";

  expect(jsonToTSV([], locale)).toEqual("");

  expect(jsonToTSV([{ a: 1, b: 2 }], locale)).toEqual("a\tb\n1\t2");

  expect(
    jsonToTSV(
      [
        { a: 1, b: 2 },
        { a: 3, b: 4 },
      ],
      locale,
    ),
  ).toEqual("a\tb\n1\t2\n3\t4");

  // Does not handle sparse arrays
  expect(jsonToTSV([{ a: 1 }, { a: 2, b: 3 }], locale)).toMatchInlineSnapshot(
    '"a\n1\n2"',
  );

  // Handles special characters
  expect(
    jsonToTSV([{ a: "hello\tworld", b: "new\nline" }], locale),
  ).toMatchInlineSnapshot('"a\tb\nhello\tworld\tnew\nline"');

  // Handles floats with en-US locale (uses . as decimal separator)
  expect(jsonToTSV([{ a: 1.5, b: 2.7 }], locale)).toEqual("a\tb\n1.5\t2.7");
});

it("can convert json to tsv with de-DE locale", () => {
  const locale = "de-DE";

  // Handles floats with de-DE locale (uses , as decimal separator)
  expect(jsonToTSV([{ a: 1.5, b: 2.7 }], locale)).toEqual("a\tb\n1,5\t2,7");

  // Handles integers (no change)
  expect(jsonToTSV([{ a: 1, b: 2 }], locale)).toEqual("a\tb\n1\t2");
});

it("can convert json to tsv with fr-FR locale", () => {
  const locale = "fr-FR";

  // Handles floats with fr-FR locale (uses , as decimal separator)
  expect(jsonToTSV([{ a: 3.14, b: 2.123_45 }], locale)).toEqual(
    "a\tb\n3,14\t2,12345",
  );
});

it("handles null and undefined values in TSV", () => {
  const locale = "en-US";

  expect(jsonToTSV([{ a: null, b: undefined, c: 1 }], locale)).toEqual(
    "a\tb\tc\n\t\t1",
  );
});

it("handles NaN values in TSV", () => {
  const locale = "en-US";

  expect(jsonToTSV([{ a: Number.NaN, b: 1 }], locale)).toEqual("a\tb\nNaN\t1");
});

it("can convert json to markdown - basic table", () => {
  expect(jsonToMarkdown([])).toMatchInlineSnapshot(`""`);

  expect(jsonToMarkdown([{ a: 1, b: 2 }])).toMatchInlineSnapshot(`
    "| a | b |
    |---|---|
    | 1 | 2 |"
  `);

  expect(
    jsonToMarkdown([
      { a: 1, b: 2 },
      { a: 3, b: 4 },
    ]),
  ).toMatchInlineSnapshot(`
    "| a | b |
    |---|---|
    | 1 | 2 |
    | 3 | 4 |"
  `);

  expect(
    jsonToMarkdown([
      { name: "Alice", age: 30 },
      { name: "Bob", age: 25 },
    ]),
  ).toMatchInlineSnapshot(`
    "| name | age |
    |---|---|
    | Alice | 30 |
    | Bob | 25 |"
  `);
});

it("can convert json to markdown - with URLs", () => {
  expect(
    jsonToMarkdown([
      { name: "Google", url: "https://google.com" },
      { name: "GitHub", url: "https://github.com" },
    ]),
  ).toMatchInlineSnapshot(`
    "| name | url |
    |---|---|
    | Google | [https://google.com](https://google.com) |
    | GitHub | [https://github.com](https://github.com) |"
  `);

  // Mixed content - URL and text in same cell
  expect(
    jsonToMarkdown([{ info: "Visit https://example.com for more" }]),
  ).toMatchInlineSnapshot(`
    "| info |
    |---|
    | Visit [https://example.com](https://example.com) for more |"
  `);

  // Multiple URLs in one cell
  expect(
    jsonToMarkdown([{ links: "https://google.com and https://github.com" }]),
  ).toMatchInlineSnapshot(`
    "| links |
    |---|
    | [https://google.com](https://google.com) and [https://github.com](https://github.com) |"
  `);
});

it("can convert json to markdown - handles nulls and undefined", () => {
  expect(
    jsonToMarkdown([{ a: null, b: undefined, c: 1 }]),
  ).toMatchInlineSnapshot(`
    "| a | b | c |
    |---|---|---|
    |  |  | 1 |"
  `);

  expect(
    jsonToMarkdown([
      { a: 1, b: 2 },
      { a: null, b: 3 },
    ]),
  ).toMatchInlineSnapshot(`
    "| a | b |
    |---|---|
    | 1 | 2 |
    |  | 3 |"
  `);
});

it("can convert json to markdown - handles special characters", () => {
  // Pipes need to be escaped since they're markdown table delimiters
  expect(
    jsonToMarkdown([{ a: "value|with|pipes", b: "normal" }]),
  ).toMatchInlineSnapshot(`
    "| a | b |
    |---|---|
    | value\\|with\\|pipes | normal |"
  `);

  // Newlines should be replaced with spaces
  expect(
    jsonToMarkdown([{ a: "line1\nline2", b: "normal" }]),
  ).toMatchInlineSnapshot(`
    "| a | b |
    |---|---|
    | line1 line2 | normal |"
  `);

  // Backslashes should be escaped
  expect(jsonToMarkdown([{ path: "C:\\Users\\Name" }])).toMatchInlineSnapshot(`
    "| path |
    |---|
    | C:\\\\Users\\\\Name |"
  `);
});

it("can convert json to markdown - handles different data types", () => {
  expect(
    jsonToMarkdown([{ str: "text", num: 42, bool: true, nil: null }]),
  ).toMatchInlineSnapshot(`
    "| str | num | bool | nil |
    |---|---|---|---|
    | text | 42 | true |  |"
  `);

  // Numbers (including NaN and Infinity)
  expect(
    jsonToMarkdown([
      {
        a: Number.NaN,
        b: Number.POSITIVE_INFINITY,
        c: Number.NEGATIVE_INFINITY,
      },
    ]),
  ).toMatchInlineSnapshot(`
    "| a | b | c |
    |---|---|---|
    | NaN | Infinity | -Infinity |"
  `);

  // Arrays and objects should be stringified
  expect(jsonToMarkdown([{ data: [1, 2, 3] }])).toMatchInlineSnapshot(`
    "| data |
    |---|
    | [1,2,3] |"
  `);

  expect(
    jsonToMarkdown([{ data: { nested: "value" } }]),
  ).toMatchInlineSnapshot(`
    "| data |
    |---|
    | {"nested":"value"} |"
  `);
});
