/* Copyright 2026 Marimo. All rights reserved. */

import type { Cell, Column, Row, Table } from "@tanstack/react-table";
import { describe, expect, it } from "vitest";
import {
  getClipboardContent,
  getPageIndexForRow,
  getRawCellValue,
  getRawRowValue,
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

function createMockCellWithMeta<TData>(opts: {
  value: unknown;
  rowIndex: number;
  columnId: string;
  rawData?: TData[];
}): Cell<TData, unknown> {
  const table = {
    options: {
      meta: { rawData: opts.rawData },
    },
  } as unknown as Table<TData>;

  return {
    getValue: () => opts.value,
    row: { index: opts.rowIndex } as Row<TData>,
    column: { id: opts.columnId } as Column<TData>,
    getContext: () =>
      ({ table }) as ReturnType<Cell<TData, unknown>["getContext"]>,
  } as unknown as Cell<TData, unknown>;
}

describe("getRawCellValue", () => {
  it("should return raw value when rawData is available", () => {
    const cell = createMockCellWithMeta({
      value: {
        _serialized_mime_bundle: {
          mimetype: "text/html",
          data: "<b>formatted</b>",
        },
      },
      rowIndex: 0,
      columnId: "score",
      rawData: [{ score: 42 }],
    });
    expect(getRawCellValue(cell)).toBe(42);
  });

  it("should fall back to cell.getValue() when rawData is undefined", () => {
    const cell = createMockCellWithMeta({
      value: "displayed",
      rowIndex: 0,
      columnId: "name",
      rawData: undefined,
    });
    expect(getRawCellValue(cell)).toBe("displayed");
  });

  it("should fall back to cell.getValue() when raw row is missing", () => {
    const cell = createMockCellWithMeta({
      value: "displayed",
      rowIndex: 5,
      columnId: "name",
      rawData: [{ name: "only-row-0" }],
    });
    expect(getRawCellValue(cell)).toBe("displayed");
  });
});

function createMockTableWithMeta<TData>(rawData?: TData[]): Table<TData> {
  return {
    options: {
      meta: { rawData },
    },
  } as unknown as Table<TData>;
}

describe("getRawRowValue", () => {
  it("should return raw value when rawData is available", () => {
    const table = createMockTableWithMeta([
      { a: 10, b: 20 },
      { a: 30, b: 40 },
    ]);
    expect(getRawRowValue(table, 0, "a")).toBe(10);
    expect(getRawRowValue(table, 1, "b")).toBe(40);
  });

  it("should return undefined when rawData is not set", () => {
    const table = createMockTableWithMeta(undefined);
    expect(getRawRowValue(table, 0, "a")).toBeUndefined();
  });

  it("should return undefined when row index is out of bounds", () => {
    const table = createMockTableWithMeta([{ a: 1 }]);
    expect(getRawRowValue(table, 5, "a")).toBeUndefined();
  });
});
