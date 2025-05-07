/* Copyright 2024 Marimo. All rights reserved. */

import type { TableData } from "@/plugins/impl/DataTablePlugin";
import { vegaLoadData } from "@/plugins/impl/vega/loader";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { INDEX_COLUMN_NAME } from "./types";

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
