/* Copyright 2024 Marimo. All rights reserved. */

import type { TableData } from "@/plugins/impl/DataTablePlugin";
import { vegaLoadData } from "@/plugins/impl/vega/loader";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";

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
