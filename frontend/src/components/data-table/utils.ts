/* Copyright 2026 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import type { TableData } from "@/plugins/impl/DataTablePlugin";
import { vegaLoadData } from "@/plugins/impl/vega/loader";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { getMimeValues } from "./mime-cell";
import { INDEX_COLUMN_NAME, type CellValueSentinel } from "./types";

const WHITESPACE_ONLY_RE = /^[\s]+$/;

/**
 * Convenience function to load table data.
 *
 * This resolves to an array of objects, where each object represents a row.
 */
export async function loadTableData<T = object>(
  tableData: TableData<T>,
): Promise<T[]> {
  // If we already have the data, return it
  if (Array.isArray(tableData)) {
    return tableData;
  }

  // If it looks like json, parse it
  if (tableData.startsWith("{") || tableData.startsWith("[")) {
    return jsonParseWithSpecialChar(tableData);
  }

  // Otherwise, load the data from the URL
  tableData = await vegaLoadData(
    tableData,
    { type: "json" },
    { handleBigIntAndNumberLike: true },
  );
  return tableData;
}

/**
 * Load both table and raw table data. Raw table data is typically when
 * there is formatting applied to the table data.
 */
export async function loadTableAndRawData<T>(
  tableData: TableData<T>,
  rawTableData?: TableData<T> | null,
): Promise<[T[], T[] | undefined]> {
  if (rawTableData) {
    return Promise.all([loadTableData(tableData), loadTableData(rawTableData)]);
  }

  return [await loadTableData(tableData), undefined];
}

/**
 * Get the stable row ID for a row.
 *
 * This is the row ID that is used to identify a row in the table.
 * It is stable across renders and pagination. It may not exist.
 *
 */
export function getStableRowId<TData>(row: TData): string | undefined {
  if (row && typeof row === "object" && INDEX_COLUMN_NAME in row) {
    return String(row[INDEX_COLUMN_NAME]);
  }
}

/**
 * Calculate which page a given row index should be on.
 *
 * @param rowIdx - The row index to check
 * @param currentPageIndex - The current page index
 * @param pageSize - The number of rows per page
 * @returns The page index if pagination should change, or null if the row is on the current page
 */
export function getPageIndexForRow(
  rowIdx: number,
  currentPageIndex: number,
  pageSize: number,
): number | null {
  const currentPageStart = currentPageIndex * pageSize;
  const currentPageEnd = currentPageStart + pageSize - 1;

  if (rowIdx < currentPageStart || rowIdx > currentPageEnd) {
    return Math.floor(rowIdx / pageSize);
  }

  return null;
}

// String representations of numeric special values.
// Only matched when the caller indicates the column is numeric.
type StringValueSentinelType = Extract<
  CellValueSentinel,
  { value: number | string }
>["type"];

const NUMERIC_STRING_SPECIALS: Record<string, StringValueSentinelType> = {
  NaN: "nan",
  Infinity: "positive-infinity",
  "-Infinity": "negative-infinity",
  inf: "positive-infinity",
  "-inf": "negative-infinity",
};

/**
 * Detect if a cell value is a sentinel (null, empty string, whitespace,
 * NaN, infinity). String representations like "NaN" are only matched when
 * `opts.isNumericColumn` is true.
 *
 * @param value - value to detect
 * @param opts.isNumericColumn - flag if the column is of a numeric type
 * @returns
 */
export function detectSentinel(
  value: unknown,
  opts?: { isNumericColumn?: boolean },
): CellValueSentinel | null {
  if (value == null) {
    return { type: "null", value };
  }

  if (typeof value === "string") {
    if (value === "") {
      return { type: "empty-string", value };
    }
    if (WHITESPACE_ONLY_RE.test(value)) {
      return { type: "whitespace", value };
    }
    // String "NaN"/"Infinity" in a numeric column = actual special float value
    if (opts?.isNumericColumn) {
      const type = NUMERIC_STRING_SPECIALS[value];
      if (type) {
        return { type, value };
      }
    }
    return null;
  }

  if (typeof value === "number") {
    if (Number.isNaN(value)) {
      return { type: "nan", value };
    }
    if (value === Number.POSITIVE_INFINITY) {
      return { type: "positive-infinity", value };
    }
    if (value === Number.NEGATIVE_INFINITY) {
      return { type: "negative-infinity", value };
    }
    return null;
  }

  return null;
}

/**
 * Stringify an unknown value. Converts objects to JSON strings.
 * @param opts.value - The value to stringify.
 * @param opts.nullAsEmptyString - If true, null values will be "". Else, stringify.
 */
export function stringifyUnknownValue(opts: {
  value: unknown;
  nullAsEmptyString?: boolean;
}): string {
  const { value, nullAsEmptyString = false } = opts;

  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  if (value === null && nullAsEmptyString) {
    return "";
  }
  return String(value);
}

function stripHtml(html: string): string {
  const div = document.createElement("div");
  div.innerHTML = html;
  const text = (div.textContent || div.innerText || "").trim();
  return text || html;
}

const HTML_MIMETYPES = new Set(["text/html", "text/markdown"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/**
 * Get clipboard-ready text and optional HTML for a cell.
 *
 * @param rawValue - The raw (unformatted) value, or undefined if not available.
 * @param displayedValue - The displayed value (may be a mime bundle).
 */
export function getClipboardContent(
  rawValue: unknown,
  displayedValue: unknown,
): { text: string; html?: string } {
  const mimeValues =
    typeof displayedValue === "object" && displayedValue !== null
      ? getMimeValues(displayedValue)
      : undefined;

  let html: string | undefined;
  if (mimeValues) {
    // text/markdown from mo.md() contains rendered HTML
    const htmlParts = mimeValues
      .filter((v) => HTML_MIMETYPES.has(v.mimetype))
      .map((v) => v.data);
    html = htmlParts.length > 0 ? htmlParts.join("") : undefined;
  }

  let text: string;
  if (rawValue !== undefined && rawValue !== displayedValue) {
    text = stringifyUnknownValue({ value: rawValue });
  } else if (mimeValues) {
    text = mimeValues
      .map((v) => (HTML_MIMETYPES.has(v.mimetype) ? stripHtml(v.data) : v.data))
      .join(", ");
  } else {
    text = stringifyUnknownValue({ value: displayedValue });
  }

  return { text, html };
}

/**
 * Get the raw (unformatted) value for a row/column from the table,
 * or undefined if raw data is not available.
 */
export function getRawValue<TData>(
  table: Table<TData>,
  rowIndex: number,
  columnId: string,
): unknown {
  const rawData = table.options.meta?.rawData;
  if (rawData) {
    const rawRow = rawData[rowIndex];
    if (isRecord(rawRow)) {
      return rawRow[columnId];
    }
  }
  return undefined;
}
