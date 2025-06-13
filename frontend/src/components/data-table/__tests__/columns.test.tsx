/* Copyright 2024 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it, test } from "vitest";
import { generateColumns, inferFieldTypes } from "../columns";
import { getMimeValues, isMimeValue, MimeCell } from "../mime-cell";
import type { FieldTypesWithExternalType } from "../types";
import { uniformSample } from "../uniformSample";
import { parseContent, UrlDetector } from "../url-detector";

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
  const { container } = render(<UrlDetector parts={parseContent(text)} />);
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
    [
      [
        "a",
        [
          "number",
          "number",
        ],
      ],
      [
        "b",
        [
          "string",
          "string",
        ],
      ],
      [
        "c",
        [
          "unknown",
          "object",
        ],
      ],
      [
        "d",
        [
          "unknown",
          "object",
        ],
      ],
      [
        "e",
        [
          "unknown",
          "object",
        ],
      ],
      [
        "f",
        [
          "boolean",
          "boolean",
        ],
      ],
      [
        "g",
        [
          "boolean",
          "boolean",
        ],
      ],
      [
        "h",
        [
          "datetime",
          "datetime",
        ],
      ],
    ]
  `);
});

test("inferFieldTypes with nulls", () => {
  const data = [{ a: 1, b: null }];
  const fieldTypes = inferFieldTypes(data);
  expect(fieldTypes).toMatchInlineSnapshot(`
    [
      [
        "a",
        [
          "number",
          "number",
        ],
      ],
      [
        "b",
        [
          "unknown",
          "object",
        ],
      ],
    ]
  `);
});

test("inferFieldTypes with mimetypes", () => {
  const data = [{ a: { mime: "text/csv" }, b: { mime: "image/png" } }];
  const fieldTypes = inferFieldTypes(data);
  expect(fieldTypes).toMatchInlineSnapshot(`
    [
      [
        "a",
        [
          "unknown",
          "object",
        ],
      ],
      [
        "b",
        [
          "unknown",
          "object",
        ],
      ],
    ]
  `);
});

describe("generateColumns", () => {
  const fieldTypes: FieldTypesWithExternalType = [
    ["name", ["string", "text"]],
    ["age", ["number", "integer"]],
  ];

  it("should generate columns with row headers", () => {
    const columns = generateColumns({
      rowHeaders: ["name"],
      selection: null,
      fieldTypes,
    });

    expect(columns).toHaveLength(3);
    expect(columns[0].id).toBe("name");
    expect(columns[0].meta?.rowHeader).toBe(true);
    expect(columns[0].enableSorting).toBe(true);
  });

  it("should generate columns with nameless row headers", () => {
    const columns = generateColumns({
      rowHeaders: [""],
      selection: null,
      fieldTypes,
    });

    expect(columns).toHaveLength(3);
    expect(columns[0].id).toMatchInlineSnapshot(`"__m_column__0"`);
    expect(columns[0].meta?.rowHeader).toBe(true);
    expect(columns[0].enableSorting).toBe(false);
  });

  it("should include selection column for multi selection", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: "multi",
      fieldTypes,
    });

    expect(columns[0].id).toBe("__select__");
    expect(columns[0].enableSorting).toBe(false);
  });

  it("should generate columns with correct meta data", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
    });

    expect(columns.length).toBe(2);
    expect(columns[0].meta?.dataType).toBe("string");
    expect(columns[1].meta?.dataType).toBe("number");
  });

  it("should handle text justification and wrapping", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
      textJustifyColumns: { name: "center" },
      wrappedColumns: ["age"],
    });

    // Assuming getCellStyleClass is a function that returns a class name
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const cell = (columns[0].cell as any)({
      column: columns[0],
      renderValue: () => "John",
      getValue: () => "John",
    });
    expect(cell?.props.className).toContain("center");
  });

  it("should not include index column if it exists", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes: [...fieldTypes, ["_marimo_row_id", ["string", "text"]]],
    });

    expect(columns).toHaveLength(2);
    expect(columns[0].id).toBe("name");
    expect(columns[1].id).toBe("age");
  });
});

describe("MimeCell", () => {
  it("renders with correct mime data", () => {
    const value = { mimetype: "text/plain", data: "Hello World" };
    const { container } = render(<MimeCell value={value} />);
    expect(container.textContent).toContain("Hello World");
  });
});

describe("isMimeValue", () => {
  it("should return true for valid MimeValue objects", () => {
    const value = { mimetype: "text/plain", data: "test data" };
    expect(isMimeValue(value)).toBe(true);
  });

  it("should return false for null", () => {
    expect(isMimeValue(null)).toBe(false);
  });

  it("should return false for primitive values", () => {
    expect(isMimeValue("string")).toBe(false);
    expect(isMimeValue(123)).toBe(false);
    expect(isMimeValue(true)).toBe(false);
  });

  it("should return false for objects missing required properties", () => {
    expect(isMimeValue({})).toBe(false);
    expect(isMimeValue({ mimetype: "text/plain" })).toBe(false);
    expect(isMimeValue({ data: "test data" })).toBe(false);
  });
});

describe("getMimeValues", () => {
  it("should return array with single MimeValue when input is a MimeValue", () => {
    const value = { mimetype: "text/plain", data: "test data" };
    expect(getMimeValues(value)).toEqual([value]);
  });

  it("should return array with MimeValue when input has serialized_mime_bundle", () => {
    const mimeValue = { mimetype: "text/plain", data: "test data" };
    const value = { serialized_mime_bundle: mimeValue };
    expect(getMimeValues(value)).toEqual([mimeValue]);
  });

  it("should return array with MimeValue when input has _serialized_mime_bundle", () => {
    const mimeValue = { mimetype: "text/plain", data: "test data" };
    const value = { _serialized_mime_bundle: mimeValue };
    expect(getMimeValues(value)).toEqual([mimeValue]);
  });

  it("should return array of MimeValues when input is an array of MimeValues", () => {
    const values = [
      { mimetype: "text/plain", data: "test data 1" },
      { mimetype: "text/html", data: "<p>test data 2</p>" },
    ];
    expect(getMimeValues(values)).toEqual(values);
  });

  it("should return undefined for null input", () => {
    expect(getMimeValues(null)).toBeUndefined();
  });

  it("should return undefined for primitive values", () => {
    expect(getMimeValues("string")).toBeUndefined();
    expect(getMimeValues(123)).toBeUndefined();
    expect(getMimeValues(true)).toBeUndefined();
  });

  it("should return undefined for objects that don't match any pattern", () => {
    expect(getMimeValues({})).toBeUndefined();
    expect(getMimeValues({ random: "property" })).toBeUndefined();
  });

  it("should return undefined for invalid serialized_mime_bundle", () => {
    expect(
      getMimeValues({ serialized_mime_bundle: "not a mime value" }),
    ).toBeUndefined();
  });

  it("should return undefined for invalid _serialized_mime_bundle", () => {
    expect(
      getMimeValues({ _serialized_mime_bundle: "not a mime value" }),
    ).toBeUndefined();
  });

  it("should return undefined for array with non-MimeValue items", () => {
    const values = [
      { mimetype: "text/plain", data: "test data" },
      "not a mime value",
    ];
    expect(getMimeValues(values)).toBeUndefined();
  });
});
