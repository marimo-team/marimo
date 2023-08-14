/* Copyright 2023 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseAttrValue, parseInitialValue } from "../htmlUtils";

describe("htmlUtils", () => {
  it.each([false, { a: 1 }, true, 0, 1, [{ a: 1 }, { b: 2 }], "hello", ""])(
    "can parse element.dataset.initialValue",
    (initialValue) => {
      const div = document.createElement("div");
      div.dataset.initialValue = JSON.stringify(initialValue);
      expect(parseInitialValue(div)).toEqual(initialValue);
    }
  );

  it("can parse an element with no initialValue", () => {
    const div = document.createElement("div");
    expect(parseInitialValue(div)).toEqual({});
  });
});

it("can parseAttrValue happy path", () => {
  expect(parseAttrValue('"hello"')).toEqual("hello");
  expect(
    parseAttrValue('[false,{"a":1},true,0,1,[{"a":1},{"b":2}],"hello",""]')
  ).toEqual([false, { a: 1 }, true, 0, 1, [{ a: 1 }, { b: 2 }], "hello", ""]);

  expect(parseAttrValue("10")).toEqual(10);
  expect(parseAttrValue("null")).toEqual(null);
});

it("can parseAttrValue NaN, Infinity, -Infinity", () => {
  expect(parseAttrValue("NaN")).toEqual(Number.NaN);
  expect(parseAttrValue('{"A":NaN}')).toEqual({ A: Number.NaN });
  expect(parseAttrValue("[NaN]")).toEqual([Number.NaN]);
  expect(parseAttrValue("[-Infinity]")).toEqual([Number.NEGATIVE_INFINITY]);
  expect(parseAttrValue("[Infinity]")).toEqual([Number.POSITIVE_INFINITY]);
  expect(parseAttrValue('[NaN,Infinity,-Infinity,{"A": NaN}]')).toEqual([
    Number.NaN,
    Number.POSITIVE_INFINITY,
    Number.NEGATIVE_INFINITY,
    { A: Number.NaN },
  ]);

  // Prevent false positives as text
  expect(parseAttrValue('"NaN"')).toEqual("NaN");
  expect(parseAttrValue('"Infinity"')).toEqual("Infinity");
  expect(parseAttrValue('"-Infinity"')).toEqual("-Infinity");

  expect(parseAttrValue('"This is NaN"')).toEqual("This is NaN");
  expect(parseAttrValue('"To Infinity and Beyond"')).toEqual(
    "To Infinity and Beyond"
  );
  expect(parseAttrValue('"To -Infinity and Beyond"')).toEqual(
    "To -Infinity and Beyond"
  );
});

it("can fail to parseAttrValue", () => {
  // Fail to parse
  expect(parseAttrValue("")).toMatchInlineSnapshot("{}");
  expect(parseAttrValue("undefined")).toMatchInlineSnapshot("{}");
  expect(parseAttrValue(undefined)).toMatchInlineSnapshot("{}");
  expect(parseAttrValue("[nan]")).toMatchInlineSnapshot("{}");
});
