/* Copyright 2026 Marimo. All rights reserved. */

import type { Column } from "@tanstack/react-table";
import { fireEvent, render } from "@testing-library/react";
import { I18nProvider } from "react-aria";
import { describe, expect, it, test, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { parseContent } from "@/utils/url-parser";
import {
  generateColumns,
  inferFieldTypes,
  LocaleNumber,
  renderCellValue,
} from "../columns";
import { getMimeValues, isMimeValue, MimeCell } from "../mime-cell";
import type { FieldTypesWithExternalType } from "../types";
import { uniformSample } from "../uniformSample";
import { UrlDetector } from "../url-detector";

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
      rowHeaders: [["name", ["string", "text"]]],
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
      rowHeaders: [["", ["string", "text"]]],
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

  it("should auto right-align numeric columns", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
    });

    // "age" is a number column — should auto right-align
    // oxlint-disable-next-line typescript/no-explicit-any
    const cell = (columns[1].cell as any)({
      column: {
        columnDef: columns[1],
      },
      renderValue: () => 25,
      getValue: () => 25,
    });
    expect(cell?.props.className).toContain("text-right");

    // "name" is a string column — should remain left-aligned
    // oxlint-disable-next-line typescript/no-explicit-any
    const nameCell = (columns[0].cell as any)({
      column: {
        columnDef: columns[0],
      },
      renderValue: () => "John",
      getValue: () => "John",
    });
    expect(nameCell?.props.className).not.toContain("text-right");
  });

  it("should respect explicit textJustifyColumns over auto alignment", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
      textJustifyColumns: { age: "left" },
    });

    // "age" is numeric but explicitly set to left
    // oxlint-disable-next-line typescript/no-explicit-any
    const cell = (columns[1].cell as any)({
      column: {
        columnDef: columns[1],
      },
      renderValue: () => 25,
      getValue: () => 25,
    });
    expect(cell?.props.className).not.toContain("text-right");
  });

  it("should set minFractionDigits from fractionDigitsByColumn", () => {
    const numericFieldTypes: FieldTypesWithExternalType = [
      ["price", ["number", "float64"]],
      ["count", ["integer", "int64"]],
    ];

    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes: numericFieldTypes,
      fractionDigitsByColumn: { price: 2 },
    });

    // price has 2 fraction digits
    expect(columns[0].meta?.minFractionDigits).toBe(2);
    // count not in fractionDigitsByColumn
    expect(columns[1].meta?.minFractionDigits).toBeUndefined();
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
    // oxlint-disable-next-line typescript/no-explicit-any
    const cell = (columns[0].cell as any)({
      column: {
        columnDef: columns[0],
      },
      renderValue: () => "John",
      getValue: () => "John",
    });
    expect(cell?.props.className).toContain("center");
  });

  it("should align column headers to match textJustifyColumns", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
      textJustifyColumns: { name: "right", age: "center" },
    });

    const mockColumn = (col: (typeof columns)[number]) => ({
      id: col.id,
      getCanSort: () => true,
      getCanFilter: () => false,
      getIsSorted: () => false,
      getSortIndex: () => -1,
      getFilterValue: () => undefined,
      columnDef: { meta: col.meta },
    });

    // Right-justified column: outer summary wrapper aligns to end, and the
    // header row uses flex-row-reverse so the title sits at the right edge.
    const { container: rightContainer } = render(
      <TooltipProvider>
        {/* oxlint-disable-next-line typescript/no-explicit-any */}
        {(columns[0].header as any)({ column: mockColumn(columns[0]) })}
      </TooltipProvider>,
    );
    expect(
      rightContainer.querySelector("[data-testid='data-table-sort-button']"),
    ).toBeTruthy();
    expect(
      rightContainer.querySelector(
        "[data-testid='data-table-column-menu-button']",
      ),
    ).toBeTruthy();
    expect(rightContainer.firstElementChild?.className).toContain("items-end");
    expect(rightContainer.querySelector(".flex-row-reverse")).toBeTruthy();

    // Center-justified column: outer summary wrapper centers; header row
    // keeps natural order.
    const { container: centerContainer } = render(
      <TooltipProvider>
        {/* oxlint-disable-next-line typescript/no-explicit-any */}
        {(columns[1].header as any)({ column: mockColumn(columns[1]) })}
      </TooltipProvider>,
    );
    expect(
      centerContainer.querySelector("[data-testid='data-table-sort-button']"),
    ).toBeTruthy();
    expect(
      centerContainer.querySelector(
        "[data-testid='data-table-column-menu-button']",
      ),
    ).toBeTruthy();
    expect(centerContainer.firstElementChild?.className).toContain(
      "items-center",
    );
    expect(centerContainer.querySelector(".flex-row-reverse")).toBeNull();
  });

  it("should not auto-align numeric column headers without explicit override", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
    });

    const mockColumn = (col: (typeof columns)[number]) => ({
      id: col.id,
      getCanSort: () => true,
      getCanFilter: () => false,
      getIsSorted: () => false,
      getSortIndex: () => -1,
      getFilterValue: () => undefined,
      columnDef: { meta: col.meta },
    });

    // "age" is numeric: cells auto right-align, but the header stays
    // left-aligned unless the user explicitly opts in via text_justify_columns.
    const { container } = render(
      <TooltipProvider>
        {/* oxlint-disable-next-line typescript/no-explicit-any */}
        {(columns[1].header as any)({ column: mockColumn(columns[1]) })}
      </TooltipProvider>,
    );
    expect(container.firstElementChild?.className).not.toContain("items-end");
    expect(container.querySelector(".flex-row-reverse")).toBeNull();
  });

  it("should cycle sort button through asc, desc, and clear on clicks", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
    });

    const toggleSorting = vi.fn();
    const clearSorting = vi.fn();
    let sortDirection: false | "asc" | "desc" = false;

    const mockColumn = (col: (typeof columns)[number]) => ({
      id: col.id,
      getCanSort: () => true,
      getCanFilter: () => false,
      getIsSorted: () => sortDirection,
      getSortIndex: () => -1,
      getFilterValue: () => undefined,
      toggleSorting,
      clearSorting,
      columnDef: { meta: col.meta },
    });

    const mock = mockColumn(columns[0]);

    const { container, rerender } = render(
      <TooltipProvider>
        {/* oxlint-disable-next-line typescript/no-explicit-any */}
        {(columns[0].header as any)({ column: mock })}
      </TooltipProvider>,
    );

    const sortButton = container.querySelector(
      "[data-testid='data-table-sort-button']",
    );
    expect(sortButton).toBeTruthy();

    // first click unsorted > asc
    fireEvent.click(sortButton!);
    expect(toggleSorting).toHaveBeenCalledWith(false, true);

    // Simulate asc state and re-render
    sortDirection = "asc";
    rerender(
      <TooltipProvider>
        {/* oxlint-disable-next-line typescript/no-explicit-any */}
        {(columns[0].header as any)({ column: mock })}
      </TooltipProvider>,
    );

    // second click asc >dsc
    fireEvent.click(sortButton!);
    expect(toggleSorting).toHaveBeenCalledWith(true, true);

    // Simulate desc state and re-render
    sortDirection = "desc";
    rerender(
      <TooltipProvider>
        {/* oxlint-disable-next-line typescript/no-explicit-any */}
        {(columns[0].header as any)({ column: mock })}
      </TooltipProvider>,
    );

    // third click back to unsorted
    fireEvent.click(sortButton!);
    expect(clearSorting).toHaveBeenCalled();
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

  it("should render header with tooltip when headerTooltip is provided", () => {
    const columns = generateColumns({
      rowHeaders: [],
      selection: null,
      fieldTypes,
      headerTooltip: { name: "Custom Name Tooltip" },
    });

    // Get the header function for the first column
    const headerFunction = columns[0].header;
    expect(headerFunction).toBeTypeOf("function");

    const mockColumn = {
      id: "name",
      getCanSort: () => false,
      getCanFilter: () => false,
      columnDef: {
        meta: {
          dtype: "string",
          dataType: "string",
        },
      },
    };

    const { container } = render(
      <TooltipProvider>
        {/* @ts-expect-error: mock column and header function */}
        {headerFunction({ column: mockColumn })}
      </TooltipProvider>,
    );

    expect(container.textContent).toContain("name");
    // The tooltip functionality is tested by verifying that the header renders correctly
    // when headerTooltip is provided.
    expect(container.firstChild).toBeTruthy();
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

describe("LocaleNumber", () => {
  it("should format numbers correctly for en-US locale", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={1_234_567.89} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"1,234,567.89"`);
  });

  it("should format numbers correctly for de-DE locale", () => {
    const { container } = render(
      <I18nProvider locale="de-DE">
        <LocaleNumber value={1_234_567.89} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"1.234.567,89"`);
  });

  it("should format integers correctly", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={1000} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"1,000"`);
  });

  it("should format zero correctly", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={0} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"0"`);
  });

  it("should format negative numbers correctly", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={-1234.56} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"-1,234.56"`);
  });

  it("should format small decimal numbers correctly", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={0.123_456_789} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"0.123456789"`);
  });

  it("should format large numbers correctly", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={999_999_999.99} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"999,999,999.99"`);
  });

  it("should format numbers correctly for fr-FR locale", () => {
    const { container } = render(
      <I18nProvider locale="fr-FR">
        <LocaleNumber value={1_234_567.89} />
      </I18nProvider>,
    );
    // oxlint-disable-next-line no-irregular-whitespace
    expect(container.textContent).toMatchInlineSnapshot(`"1 234 567,89"`);
  });

  it("should format numbers correctly for ja-JP locale", () => {
    const { container } = render(
      <I18nProvider locale="ja-JP">
        <LocaleNumber value={1_234_567.89} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"1,234,567.89"`);
  });

  it("should respect maximumFractionDigits based on locale", () => {
    // Test with a number that has many decimal places
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={1.123_456_789_012_345_7} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"1.1234567890123457"`);
  });

  it("should handle very large numbers", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={123_456_789_012_345.67} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(
      `"123,456,789,012,345.67"`,
    );
  });

  it("should handle Infinity", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={Infinity} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"∞"`);
  });

  it("should handle negative Infinity", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={-Infinity} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"-∞"`);
  });

  it("should handle NaN", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={Number.NaN} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"NaN"`);
  });

  it("should handle numbers with scientific notation", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={1e10} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"10,000,000,000"`);
  });

  it("should pad decimals with minFractionDigits", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={42} minFractionDigits={2} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"42.00"`);
  });

  it("should pad to minFractionDigits for numbers with fewer decimals", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={1234.5} minFractionDigits={3} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"1,234.500"`);
  });

  it("should not truncate decimals beyond minFractionDigits", () => {
    const { container } = render(
      <I18nProvider locale="en-US">
        <LocaleNumber value={1.234_56} minFractionDigits={2} />
      </I18nProvider>,
    );
    expect(container.textContent).toMatchInlineSnapshot(`"1.23456"`);
  });
});

describe("renderCellValue with string + edge whitespace", () => {
  const createMockStringColumn = () =>
    ({
      id: "desc",
      columnDef: {
        meta: {
          dataType: "string" as const,
          dtype: "object",
        },
      },
      getColumnFormatting: () => undefined,
      getColumnWrapping: () => undefined,
      applyColumnFormatting: (value: unknown) => value,
    }) as unknown as Column<unknown>;

  const renderWithProviders = (node: React.ReactNode) =>
    render(
      <I18nProvider locale="en-US">
        <TooltipProvider>{node}</TooltipProvider>
      </I18nProvider>,
    );

  it("renders edge whitespace markers and still detects the URL in the middle", () => {
    const mockColumn = createMockStringColumn();
    const value = "  https://example.com  ";
    const result = renderCellValue({
      column: mockColumn,
      renderValue: () => value,
      getValue: () => value,
      selectCell: undefined,
      cellStyles: "",
    });

    const { container } = renderWithProviders(result);

    // URL detection runs on the middle, so the anchor is still rendered.
    const link = container.querySelector("a");
    expect(link).toBeTruthy();
    expect(link?.href).toBe("https://example.com/");

    // The link text is exactly the URL — no leading/trailing whitespace
    // leaked into the anchor.
    expect(link?.textContent).toBe("https://example.com");

    // Both edge-whitespace marker containers are present and render
    // visible glyphs (U+2423 "open box" for regular spaces).
    const markerSpans = container.querySelectorAll(
      "span[aria-label$='space'], span[aria-label$='spaces']",
    );
    expect(markerSpans.length).toBeGreaterThanOrEqual(2);
    expect(container.textContent?.includes("\u2423")).toBe(true);
  });

  it("does not split URLs on whitespace padding (regression)", () => {
    const mockColumn = createMockStringColumn();
    // Trailing whitespace would previously be consumed by the URL regex
    // (\S+). We render the middle only through parseContent to avoid that.
    const value = "go here: https://example.com/path  ";
    const result = renderCellValue({
      column: mockColumn,
      renderValue: () => value,
      getValue: () => value,
      selectCell: undefined,
      cellStyles: "",
    });

    const { container } = renderWithProviders(result);

    const link = container.querySelector("a");
    expect(link).toBeTruthy();
    // href is URL-normalized by the browser — should not include the
    // trailing spaces as part of the URL path.
    expect(link?.href).toBe("https://example.com/path");
    expect(link?.textContent?.trimEnd()).toBe("https://example.com/path");
  });

  it("renders no marker span when the string has no edge whitespace", () => {
    const mockColumn = createMockStringColumn();
    const value = "https://example.com";
    const result = renderCellValue({
      column: mockColumn,
      renderValue: () => value,
      getValue: () => value,
      selectCell: undefined,
      cellStyles: "",
    });

    const { container } = renderWithProviders(result);
    // No marker glyph leaked through.
    expect(container.textContent?.includes("\u2423")).toBe(false);
    // And no WhitespaceMarkers wrapper was rendered at all. The component
    // returns null for empty strings, and always sets an aria-label
    // generated by `describeWhitespace` when it does render (e.g.
    // "1 space", "2 spaces", "1 tab", "1 unicode whitespace").
    // Matching the "space"/"spaces" suffix is enough here because the
    // test value contains no whitespace, so no marker of any kind should
    // appear.
    const markerSpans = container.querySelectorAll(
      "span[aria-label$='space'], span[aria-label$='spaces']",
    );
    expect(markerSpans.length).toBe(0);
  });
});

describe("renderCellValue with boolean values", () => {
  const createMockColumn = () =>
    ({
      id: "active",
      columnDef: {
        meta: {
          dataType: "boolean" as const,
          dtype: "bool",
        },
      },
      getColumnFormatting: () => undefined,
      getColumnWrapping: () => undefined,
      applyColumnFormatting: (value: unknown) => value,
    }) as unknown as Column<unknown>;

  it("should render true as True", () => {
    const mockColumn = createMockColumn();
    const result = renderCellValue({
      column: mockColumn,
      renderValue: () => true,
      getValue: () => true,
      selectCell: undefined,
      cellStyles: "",
    });
    const { container } = render(result);
    expect(container.textContent).toBe("True");
  });

  it("should render false as False", () => {
    const mockColumn = createMockColumn();
    const result = renderCellValue({
      column: mockColumn,
      renderValue: () => false,
      getValue: () => false,
      selectCell: undefined,
      cellStyles: "",
    });
    const { container } = render(result);
    expect(container.textContent).toBe("False");
  });
});

describe("renderCellValue with datetime values", () => {
  const createMockColumn = () =>
    ({
      id: "created",
      columnDef: {
        meta: {
          dataType: "datetime" as const,
          dtype: "datetime64[ns]",
        },
      },
      getColumnFormatting: () => undefined,
      getColumnWrapping: () => undefined,
      applyColumnFormatting: (value: unknown) => value,
    }) as unknown as Column<unknown>;

  it("should handle null, empty string, and 'null' string datetime values without throwing RangeError", () => {
    const mockColumn = createMockColumn();

    // Test null, empty string, and "null" string (as they might come from SQL)
    const nullishValues = [null, "", "null"];

    nullishValues.forEach((value) => {
      const result = renderCellValue({
        column: mockColumn,
        renderValue: () => value,
        getValue: () => value,
        selectCell: undefined,
        cellStyles: "",
      });

      expect(result).toBeDefined();
      // Should not throw RangeError when rendering
      expect(() => {
        render(
          <I18nProvider locale="en-US">
            <TooltipProvider>{result}</TooltipProvider>
          </I18nProvider>,
        );
      }).not.toThrow();
    });
  });

  it("should handle invalid date strings without throwing RangeError", () => {
    const mockColumn = createMockColumn();

    const invalidDates = [
      "invalid-date",
      "2024-13-45", // Invalid month/day
      "not-a-date",
      "2024-06-14 12:34:20.665332",
    ];

    invalidDates.forEach((invalidDate) => {
      const result = renderCellValue({
        column: mockColumn,
        renderValue: () => invalidDate,
        getValue: () => invalidDate,
        selectCell: undefined,
        cellStyles: "",
      });
      expect(result).toBeDefined();
      // Should not throw RangeError when rendering
      expect(() => {
        render(
          <I18nProvider locale="en-US">
            <TooltipProvider>{result}</TooltipProvider>
          </I18nProvider>,
        );
      }).not.toThrow();
    });
  });

  it("should still render valid datetime strings correctly", () => {
    const mockColumn = createMockColumn();

    const validDates = [
      "2024-06-14T12:34:20Z",
      "2024-06-14 12:34:20",
      "2024-06-14",
    ];

    validDates.forEach((validDate) => {
      const result = renderCellValue({
        column: mockColumn,
        renderValue: () => validDate,
        getValue: () => validDate,
        selectCell: undefined,
        cellStyles: "",
      });
      expect(result).toBeDefined();
      // Should render as a date component, not as plain string
      expect(result).not.toBeNull();
      // Should not throw when rendering
      expect(() => {
        render(
          <I18nProvider locale="en-US">
            <TooltipProvider>{result}</TooltipProvider>
          </I18nProvider>,
        );
      }).not.toThrow();
    });
  });

  it("should handle invalid Date instances without throwing RangeError", () => {
    const mockColumn = createMockColumn();

    const invalidDate = new Date("invalid");

    const result = renderCellValue({
      column: mockColumn,
      renderValue: () => invalidDate,
      getValue: () => invalidDate,
      selectCell: undefined,
      cellStyles: "",
    });
    expect(result).toBeDefined();
    // Should not throw RangeError when rendering
    expect(() => {
      render(
        <I18nProvider locale="en-US">
          <TooltipProvider>{result}</TooltipProvider>
        </I18nProvider>,
      );
    }).not.toThrow();
  });

  it("should handle mixed valid and null datetime values in a column", () => {
    const mockColumn = createMockColumn();

    const values = [
      "2024-06-14T12:34:20Z", // Valid
      null,
      "2024-06-15T12:34:20Z", // Valid
      "",
      "2024-06-16T12:34:20Z", // Valid
    ];

    values.forEach((value) => {
      const result = renderCellValue({
        column: mockColumn,
        renderValue: () => value,
        getValue: () => value,
        selectCell: undefined,
        cellStyles: "",
      });
      expect(result).toBeDefined();
      // Should not throw RangeError when rendering
      expect(() => {
        render(
          <I18nProvider locale="en-US">
            <TooltipProvider>{result}</TooltipProvider>
          </I18nProvider>,
        );
      }).not.toThrow();
    });
  });
});
