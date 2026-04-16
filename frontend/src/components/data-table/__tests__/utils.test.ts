/* Copyright 2026 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import { describe, expect, it } from "vitest";
import {
  detectSentinel,
  getClipboardContent,
  getPageIndexForRow,
  getRawValue,
  stringifyUnknownValue,
} from "../utils";

describe("getPageIndexForRow", () => {
  it("should return null when row is on current page", () => {
    // Page 0, rows 0-9
    expect(getPageIndexForRow(0, 0, 10)).toBeNull();
    expect(getPageIndexForRow(5, 0, 10)).toBeNull();
    expect(getPageIndexForRow(9, 0, 10)).toBeNull();

    // Page 1, rows 10-19
    expect(getPageIndexForRow(10, 1, 10)).toBeNull();
    expect(getPageIndexForRow(15, 1, 10)).toBeNull();
    expect(getPageIndexForRow(19, 1, 10)).toBeNull();
  });

  it("should return new page index when row is on a different page", () => {
    // Row 15 should be on page 1 when viewing page 0
    expect(getPageIndexForRow(15, 0, 10)).toBe(1);

    // Row 5 should be on page 0 when viewing page 1
    expect(getPageIndexForRow(5, 1, 10)).toBe(0);

    // Row 25 should be on page 2 when viewing page 0
    expect(getPageIndexForRow(25, 0, 10)).toBe(2);

    // Row 0 should be on page 0 when viewing page 5
    expect(getPageIndexForRow(0, 5, 10)).toBe(0);
  });

  it("should handle different page sizes", () => {
    // Page size of 20
    expect(getPageIndexForRow(0, 0, 20)).toBeNull();
    expect(getPageIndexForRow(19, 0, 20)).toBeNull();
    expect(getPageIndexForRow(20, 0, 20)).toBe(1);
    expect(getPageIndexForRow(39, 0, 20)).toBe(1);
    expect(getPageIndexForRow(40, 0, 20)).toBe(2);

    // Page size of 5
    expect(getPageIndexForRow(0, 0, 5)).toBeNull();
    expect(getPageIndexForRow(4, 0, 5)).toBeNull();
    expect(getPageIndexForRow(5, 0, 5)).toBe(1);
    expect(getPageIndexForRow(9, 0, 5)).toBe(1);
    expect(getPageIndexForRow(10, 0, 5)).toBe(2);
  });

  it("should handle boundary cases", () => {
    // First row of next page
    expect(getPageIndexForRow(10, 0, 10)).toBe(1);

    // Last row of previous page
    expect(getPageIndexForRow(9, 1, 10)).toBe(0);

    // First row of current page
    expect(getPageIndexForRow(10, 1, 10)).toBeNull();

    // Last row of current page
    expect(getPageIndexForRow(19, 1, 10)).toBeNull();

    // Last row of last page
    expect(getPageIndexForRow(99, 9, 10)).toBeNull();
  });

  it("should handle edge case of row 0", () => {
    expect(getPageIndexForRow(0, 0, 10)).toBeNull();
    expect(getPageIndexForRow(0, 1, 10)).toBe(0);
    expect(getPageIndexForRow(0, 5, 10)).toBe(0);
  });

  it("should handle large page numbers and row indices", () => {
    // Page 100, rows 1000-1009 (page size 10)
    expect(getPageIndexForRow(1000, 100, 10)).toBeNull();
    expect(getPageIndexForRow(1009, 100, 10)).toBeNull();
    expect(getPageIndexForRow(1010, 100, 10)).toBe(101);
    expect(getPageIndexForRow(999, 100, 10)).toBe(99);
  });
});

describe("stringifyUnknownValue", () => {
  it("should stringify primitives", () => {
    expect(stringifyUnknownValue({ value: "hello" })).toBe("hello");
    expect(stringifyUnknownValue({ value: 42 })).toBe("42");
    expect(stringifyUnknownValue({ value: true })).toBe("true");
    expect(stringifyUnknownValue({ value: null })).toBe("null");
    expect(stringifyUnknownValue({ value: undefined })).toBe("undefined");
  });

  it("should stringify null as empty string when flag is set", () => {
    expect(
      stringifyUnknownValue({ value: null, nullAsEmptyString: true }),
    ).toBe("");
  });

  it("should JSON-stringify plain objects", () => {
    expect(stringifyUnknownValue({ value: { x: 1 } })).toBe('{"x":1}');
  });
});

describe("getClipboardContent", () => {
  it("should use rawValue for text when it differs from displayedValue", () => {
    const displayed = {
      _serialized_mime_bundle: {
        mimetype: "text/html",
        data: '<a href="https://example.com">42</a>',
      },
    };
    const result = getClipboardContent(42, displayed);
    expect(result.text).toBe("42");
    expect(result.html).toBe('<a href="https://example.com">42</a>');
  });

  it("should strip html for text when rawValue equals displayedValue", () => {
    const mimeBundle = {
      _serialized_mime_bundle: {
        mimetype: "text/html",
        data: "<b>bold</b>",
      },
    };
    const result = getClipboardContent(mimeBundle, mimeBundle);
    expect(result.text).toBe("bold");
    expect(result.html).toBe("<b>bold</b>");
  });

  it("should handle undefined rawValue", () => {
    const displayed = {
      _serialized_mime_bundle: {
        mimetype: "text/html",
        data: "<b>hello</b>",
      },
    };
    const result = getClipboardContent(undefined, displayed);
    expect(result.text).toBe("hello");
    expect(result.html).toBe("<b>hello</b>");
  });

  it("should return no html for plain values", () => {
    const result = getClipboardContent(undefined, "plain text");
    expect(result.text).toBe("plain text");
    expect(result.html).toBeUndefined();
  });

  it("should treat text/markdown as html since mo.md() data is rendered html", () => {
    const displayed = {
      _serialized_mime_bundle: {
        mimetype: "text/markdown",
        data: '<span class="markdown"><strong>Hello</strong></span>',
      },
    };
    const result = getClipboardContent(undefined, displayed);
    expect(result.text).toBe("Hello");
    expect(result.html).toBe(
      '<span class="markdown"><strong>Hello</strong></span>',
    );
  });

  it("should return no html for non-html mime bundles", () => {
    const displayed = {
      _serialized_mime_bundle: {
        mimetype: "text/plain",
        data: "just text",
      },
    };
    const result = getClipboardContent(undefined, displayed);
    expect(result.text).toBe("just text");
    expect(result.html).toBeUndefined();
  });

  it("should handle null rawValue as a real value", () => {
    const displayed = {
      _serialized_mime_bundle: {
        mimetype: "text/html",
        data: "<i>N/A</i>",
      },
    };
    const result = getClipboardContent(null, displayed);
    expect(result.text).toBe("null");
    expect(result.html).toBe("<i>N/A</i>");
  });
});

describe("detectSentinel", () => {
  it("should detect null and undefined", () => {
    expect(detectSentinel(null, undefined)).toEqual({
      type: "null",
      value: null,
    });
    expect(detectSentinel(undefined, undefined)).toEqual({
      type: "null",
      value: undefined,
    });
  });

  it("should detect empty string", () => {
    expect(detectSentinel("", "string")).toEqual({
      type: "empty-string",
      value: "",
    });
  });

  it("should detect whitespace-only strings", () => {
    expect(detectSentinel(" ", "string")).toEqual({
      type: "whitespace",
      value: " ",
    });
    expect(detectSentinel("   ", "string")).toEqual({
      type: "whitespace",
      value: "   ",
    });
    expect(detectSentinel("\t", "string")).toEqual({
      type: "whitespace",
      value: "\t",
    });
    expect(detectSentinel("\n", "string")).toEqual({
      type: "whitespace",
      value: "\n",
    });
    expect(detectSentinel("\t \n", "string")).toEqual({
      type: "whitespace",
      value: "\t \n",
    });
  });

  it("should detect NaN", () => {
    expect(detectSentinel(Number.NaN, "number")).toEqual({
      type: "nan",
      value: Number.NaN,
    });
  });

  it("should detect Infinity", () => {
    expect(detectSentinel(Number.POSITIVE_INFINITY, "number")).toEqual({
      type: "positive-infinity",
      value: Number.POSITIVE_INFINITY,
    });
    expect(detectSentinel(Number.NEGATIVE_INFINITY, "number")).toEqual({
      type: "negative-infinity",
      value: Number.NEGATIVE_INFINITY,
    });
  });

  it("should return null for normal values", () => {
    expect(detectSentinel("hello", "string")).toBeNull();
    expect(detectSentinel(42, "number")).toBeNull();
    expect(detectSentinel(0, "number")).toBeNull();
    expect(detectSentinel(-1.5, "number")).toBeNull();
    expect(detectSentinel(true, "boolean")).toBeNull();
    expect(detectSentinel(false, "boolean")).toBeNull();
    expect(detectSentinel({}, "unknown")).toBeNull();
    expect(detectSentinel([], "unknown")).toBeNull();
  });

  it("should not match literal null-like strings", () => {
    expect(detectSentinel("null", "string")).toBeNull();
    expect(detectSentinel("NULL", "string")).toBeNull();
    expect(detectSentinel("None", "string")).toBeNull();
  });

  it("should not match string NaN/Infinity in non-numeric columns", () => {
    expect(detectSentinel("NaN", "string")).toBeNull();
    expect(detectSentinel("Infinity", "string")).toBeNull();
    expect(detectSentinel("-Infinity", "string")).toBeNull();
  });

  it("should match string NaN/Infinity in numeric columns", () => {
    expect(detectSentinel("NaN", "number")).toEqual({
      type: "nan",
      value: "NaN",
    });
    expect(detectSentinel("Infinity", "number")).toEqual({
      type: "positive-infinity",
      value: "Infinity",
    });
    expect(detectSentinel("-Infinity", "number")).toEqual({
      type: "negative-infinity",
      value: "-Infinity",
    });
    expect(detectSentinel("inf", "number")).toEqual({
      type: "positive-infinity",
      value: "inf",
    });
    expect(detectSentinel("-inf", "number")).toEqual({
      type: "negative-infinity",
      value: "-inf",
    });
  });

  it("should still not match normal strings in numeric columns", () => {
    expect(detectSentinel("hello", "number")).toBeNull();
    expect(detectSentinel("42", "number")).toBeNull();
  });

  it("should not match NaT in non-temporal columns", () => {
    expect(detectSentinel("NaT", "string")).toBeNull();
  });

  it("should match NaT in temporal columns", () => {
    expect(detectSentinel("NaT", "datetime")).toEqual({
      type: "nat",
      value: "NaT",
    });
    expect(detectSentinel("NaT", "date")).toEqual({
      type: "nat",
      value: "NaT",
    });
  });
});

function createMockTableWithMeta<TData>(rawData?: TData[]): Table<TData> {
  return {
    options: {
      meta: { rawData },
    },
  } as unknown as Table<TData>;
}

describe("getRawValue", () => {
  it("should return raw value when rawData is available", () => {
    const table = createMockTableWithMeta([
      { a: 10, b: 20 },
      { a: 30, b: 40 },
    ]);
    expect(getRawValue(table, 0, "a")).toBe(10);
    expect(getRawValue(table, 1, "b")).toBe(40);
  });

  it("should return undefined when rawData is not set", () => {
    const table = createMockTableWithMeta(undefined);
    expect(getRawValue(table, 0, "a")).toBeUndefined();
  });

  it("should return undefined when row index is out of bounds", () => {
    const table = createMockTableWithMeta([{ a: 1 }]);
    expect(getRawValue(table, 5, "a")).toBeUndefined();
  });
});
