/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { datasetTablesAtom } from "@/core/datasets/state";
import type { DataTable, DataTableColumn } from "@/core/kernel/messages";

export interface DataFrameWithColumns {
  name: string;
  value: string | null | undefined;
  columns: DataTableColumn[];
}

/**
 * Hook to get all DataFrame variables with their columns
 *
 * @returns Array of DataFrames with their column information
 */
export function useDataFrameColumns(): DataFrameWithColumns[] {
  const tables = useAtomValue(datasetTablesAtom);

  return useMemo(() => {
    const dataframes: DataFrameWithColumns[] = [];

    for (const table of tables) {
      // Only include tables that are local Python variables (not SQL tables)
      if (table.source_type === "local" && table.variable_name) {
        dataframes.push({
          name: table.variable_name,
          value: getTableDescription(table),
          columns: table.columns || [],
        });
      }
    }

    // Sort by name for consistent ordering
    return dataframes.sort((a, b) => a.name.localeCompare(b.name));
  }, [tables]);
}

/**
 * Get a human-readable description of the table
 */
function getTableDescription(table: DataTable): string | null {
  const parts: string[] = [];

  if (table.num_rows != null) {
    parts.push(`${table.num_rows} rows`);
  }

  if (table.num_columns != null) {
    parts.push(`${table.num_columns} columns`);
  }

  return parts.length > 0 ? parts.join(" x ") : null;
}
