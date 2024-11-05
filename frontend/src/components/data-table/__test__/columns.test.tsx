/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "vitest";
import { uniformSample } from "../uniformSample";
import { UrlDetector } from "../url-detector";
import { render } from "@testing-library/react";
import { inferFieldTypes } from "../columns";

test("uniformSample", () => {
  const items = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];

  expect(uniformSample(items, 2)).toMatchInlineSnapshot(`
    [
      "A",
      "J",
    ]
  `);
  expect(uniformSample(items, 4)).toMatchInlineSnapshot(`
    [
      "A",
      "C",
      "F",
      "J",
    ]
  `);
  expect(uniformSample(items, 100)).toBe(items);
});

test("UrlDetector renders URLs as hyperlinks", () => {
  const text = "Check this link: https://example.com";
  const { container } = render(<UrlDetector text={text} />);
  const link = container.querySelector("a");
  expect(link).toBeTruthy();
  expect(link?.href).toBe("https://example.com/");
});

test("inferFieldTypes", () => {
  const data = [
    {
      a: 1,
      b: "foo",
      c: null,
      d: { mime: "text/csv" },
      e: [1, 2, 3],
      f: true,
      g: false,
      h: new Date(),
    },
  ];
  const fieldTypes = inferFieldTypes(data);
  expect(fieldTypes).toMatchInlineSnapshot(`
    {
      "a": [
        "number",
        "number",
      ],
      "b": [
        "string",
        "string",
      ],
      "c": [
        "unknown",
        "unknown",
      ],
      "d": [
        "unknown",
        "unknown",
      ],
      "e": [
        "unknown",
        "unknown",
      ],
      "f": [
        "boolean",
        "boolean",
      ],
      "g": [
        "boolean",
        "boolean",
      ],
      "h": [
        "datetime",
        "datetime",
      ],
    }
  `);
});

test("inferFieldTypes with nulls", () => {
  const data = [{ a: 1, b: null }];
  const fieldTypes = inferFieldTypes(data);
  expect(fieldTypes).toMatchInlineSnapshot(`
    {
      "a": [
        "number",
        "number",
      ],
      "b": [
        "unknown",
        "unknown",
      ],
    }
  `);
});

test("inferFieldTypes with mimetypes", () => {
  const data = [{ a: { mime: "text/csv" }, b: { mime: "image/png" } }];
  const fieldTypes = inferFieldTypes(data);
  expect(fieldTypes).toMatchInlineSnapshot(`
    {
      "a": [
        "unknown",
        "unknown",
      ],
      "b": [
        "unknown",
        "unknown",
      ],
    }
  `);
});
