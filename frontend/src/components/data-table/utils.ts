/* Copyright 2024 Marimo. All rights reserved. */

import type { TableData } from "@/plugins/impl/DataTablePlugin";
import { vegaLoadData } from "@/plugins/impl/vega/loader";

export async function loadTableData<T>(data: TableData<T>): Promise<T[]> {
  // If we already have the data, return it
  if (Array.isArray(data)) {
    return data;
  }

  // Otherwise, load the data from the URL
  return await vegaLoadData(
    data,
    { type: "json" },
    { handleBigIntAndNumberLike: true },
  );
}
